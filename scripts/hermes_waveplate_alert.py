#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


DEFAULT_APP_TZ = "Asia/Shanghai"
DEFAULT_ALERT_THRESHOLD_MINUTES = 60
DEFAULT_FINAL_ALERT_THRESHOLD_MINUTES = 1
DEFAULT_NTFY_URL = "https://ntfy.icehe.life/wuwa"
DEFAULT_NTFY_PRIORITY = "high"
DEFAULT_NTFY_ALERT_TITLE = "WuWa waveplate alert"
DEFAULT_NTFY_STATUS_TITLE = "WuWa account status"
STATE_VERSION = 2
HERMES_HOME = Path(os.getenv("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
STATE_FILE = HERMES_HOME / "scripts" / ".wuwa_waveplate_alert_state.json"
LOG_FILE = HERMES_HOME / "scripts" / ".wuwa_waveplate_alert.log"
REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class AccountAlert:
    account_id: int
    game_id: str
    abbr: str
    nickname: str
    full_waveplate_at: datetime
    remaining_seconds: int

    @property
    def dedupe_key(self) -> str:
        return self.full_waveplate_at.astimezone(timezone.utc).isoformat()


@dataclass
class NtfyNotification:
    title: str
    message: str
    priority: str


@dataclass
class NtfySendResult:
    title: str
    account_id: int | None = None
    threshold_minutes: int | None = None
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send WuWa waveplate alerts via ntfy.")
    parser.add_argument("--dry-run", action="store_true", help="Print the message without sending or updating state.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on errors instead of swallowing them.")
    parser.add_argument(
        "--send-current",
        action="store_true",
        help="Send the current WuWa account status instead of only accounts entering the alert window.",
    )
    return parser.parse_args()


def load_dotenv_if_missing(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        os.environ[key] = value.strip().strip("\"'")


def load_runtime_env() -> None:
    load_dotenv_if_missing(HERMES_HOME / ".env")
    load_dotenv_if_missing(REPO_ROOT / ".env")
    load_dotenv_if_missing(REPO_ROOT / "backend" / ".env")


def get_timezone() -> ZoneInfo:
    tz_name = os.getenv("APP_TZ", DEFAULT_APP_TZ).strip() or DEFAULT_APP_TZ
    return ZoneInfo(tz_name)


def now_in_app_tz() -> datetime:
    return datetime.now(get_timezone())


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def log(message: str) -> None:
    ts = now_in_app_tz().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {message}"
    ensure_parent(LOG_FILE)
    with LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    print(line)


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def env_str(name: str, default: str) -> str:
    value = os.getenv(name, "").strip()
    return value or default


def alert_threshold_minutes() -> list[int]:
    raw = os.getenv("WUWA_WAVEPLATE_ALERT_THRESHOLDS_MINUTES", "").strip()
    if raw:
        values: list[int] = []
        for part in raw.replace(";", ",").split(","):
            text = part.strip()
            if not text:
                continue
            try:
                value = int(text)
            except ValueError as exc:
                raise RuntimeError(f"invalid WUWA_WAVEPLATE_ALERT_THRESHOLDS_MINUTES value: {text!r}") from exc
            if value <= 0:
                raise RuntimeError("WUWA_WAVEPLATE_ALERT_THRESHOLDS_MINUTES must contain positive minutes")
            values.append(value)
    else:
        values = [
            env_int("WUWA_WAVEPLATE_ALERT_THRESHOLD_MINUTES", DEFAULT_ALERT_THRESHOLD_MINUTES),
            DEFAULT_FINAL_ALERT_THRESHOLD_MINUTES,
        ]

    unique_values = sorted(set(values), reverse=True)
    if not unique_values:
        raise RuntimeError("at least one waveplate alert threshold must be configured")
    return unique_values


def format_thresholds(thresholds: list[int]) -> str:
    return ", ".join(f"{threshold}m" for threshold in thresholds)


def normalize_database_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def database_url() -> str:
    raw = os.getenv("DATABASE_URL", "").strip()
    if not raw:
        raise RuntimeError("DATABASE_URL is not configured in environment, .env, or backend/.env")
    return normalize_database_url(raw)


def ntfy_url() -> str:
    return env_str("WUWA_WAVEPLATE_ALERT_NTFY_URL", DEFAULT_NTFY_URL)


def ntfy_authorization() -> str:
    authorization = os.getenv("WUWA_WAVEPLATE_ALERT_NTFY_AUTHORIZATION", "").strip()
    if authorization:
        return authorization

    token = os.getenv("WUWA_WAVEPLATE_ALERT_NTFY_TOKEN", "").strip()
    if token:
        if token.lower().startswith("bearer "):
            return token
        return f"Bearer {token}"

    raise RuntimeError(
        "ntfy authorization is not configured. Set WUWA_WAVEPLATE_ALERT_NTFY_TOKEN "
        "or WUWA_WAVEPLATE_ALERT_NTFY_AUTHORIZATION."
    )


def ntfy_priority() -> str:
    return env_str("WUWA_WAVEPLATE_ALERT_NTFY_PRIORITY", DEFAULT_NTFY_PRIORITY)


def load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {"version": STATE_VERSION, "alerts": {}}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        log(f"state file is invalid, resetting it: {exc}")
        return {"version": STATE_VERSION, "alerts": {}}


def save_state(state: dict[str, Any]) -> None:
    ensure_parent(STATE_FILE)
    payload = dict(state)
    payload["version"] = STATE_VERSION
    payload["updated_at"] = now_in_app_tz().isoformat()
    tmp_path = STATE_FILE.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(STATE_FILE)


def alert_state_buckets(state: dict[str, Any]) -> dict[str, dict[str, str]]:
    alerts = state.get("alerts", {})
    if not isinstance(alerts, dict) or not alerts:
        return {}

    if all(isinstance(value, str) for value in alerts.values()):
        return {str(DEFAULT_ALERT_THRESHOLD_MINUTES): {str(k): v for k, v in alerts.items()}}

    buckets: dict[str, dict[str, str]] = {}
    for threshold, entries in alerts.items():
        if not isinstance(entries, dict):
            continue
        bucket = {str(account_id): dedupe for account_id, dedupe in entries.items() if isinstance(dedupe, str)}
        if bucket:
            buckets[str(threshold)] = bucket
    return buckets


def fetch_active_accounts() -> list[AccountAlert]:
    query = """
SELECT
  account_id,
  id,
  abbr,
  nickname,
  EXTRACT(EPOCH FROM full_waveplate_at)::bigint AS full_waveplate_epoch
FROM accounts
WHERE is_active IS TRUE
ORDER BY full_waveplate_at ASC, abbr ASC, account_id ASC;
""".strip()
    result = subprocess.run(
        [
            "psql",
            database_url(),
            "-X",
            "-v",
            "ON_ERROR_STOP=1",
            "-t",
            "-A",
            "-F",
            "\t",
            "-P",
            "pager=off",
            "-c",
            query,
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    accounts: list[AccountAlert] = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) != 5:
            raise RuntimeError(f"unexpected psql row format: {raw_line!r}")
        epoch = int(parts[4])
        full_at = datetime.fromtimestamp(epoch, tz=timezone.utc).astimezone(get_timezone())
        accounts.append(
            AccountAlert(
                account_id=int(parts[0]),
                game_id=parts[1],
                abbr=parts[2],
                nickname=parts[3],
                full_waveplate_at=full_at,
                remaining_seconds=0,
            )
        )
    return accounts


def select_alerts(
    accounts: list[AccountAlert],
    state: dict[str, Any],
    threshold_minutes: int,
) -> list[AccountAlert]:
    now = now_in_app_tz()
    threshold_seconds = threshold_minutes * 60
    alerts = alert_state_buckets(state).get(str(threshold_minutes), {})

    candidates: list[AccountAlert] = []
    for account in accounts:
        remaining_seconds = int((account.full_waveplate_at - now).total_seconds())
        if remaining_seconds < 1 or remaining_seconds > threshold_seconds:
            continue
        account.remaining_seconds = remaining_seconds
        if alerts.get(str(account.account_id)) == account.dedupe_key:
            continue
        candidates.append(account)
    return candidates


def format_remaining(seconds: int) -> str:
    minutes = max(1, round(seconds / 60))
    if minutes < 60:
        return f"{minutes} 分钟"
    hours, mins = divmod(minutes, 60)
    if mins == 0:
        return f"{hours} 小时"
    return f"{hours} 小时 {mins} 分钟"


def account_label(account: AccountAlert) -> str:
    parts = [account.abbr, account.game_id, account.nickname]
    return " / ".join(part for part in parts if part)


def build_alert_notification(account: AccountAlert, threshold_minutes: int) -> NtfyNotification:
    full_at = account.full_waveplate_at.strftime("%m-%d %H:%M")
    title = env_str("WUWA_WAVEPLATE_ALERT_NTFY_ALERT_TITLE", DEFAULT_NTFY_ALERT_TITLE)
    message = "\n".join(
        [
            "【鸣潮体力提醒】",
            account_label(account),
            f"将在 {threshold_minutes} 分钟内满体。",
            f"剩余：{format_remaining(account.remaining_seconds)}",
            f"满体时间：{full_at}",
        ]
    )
    return NtfyNotification(title=title, message=message, priority=ntfy_priority())


def build_current_status_message() -> str:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "hermes_wuwa_account_status.py")],
        check=True,
        capture_output=True,
        text=True,
    )
    message = result.stdout.strip()
    if not message:
        raise RuntimeError("current account status output is empty")
    return message


def build_current_status_notification() -> NtfyNotification:
    title = env_str("WUWA_WAVEPLATE_ALERT_NTFY_STATUS_TITLE", DEFAULT_NTFY_STATUS_TITLE)
    return NtfyNotification(title=title, message=build_current_status_message(), priority=ntfy_priority())


def send_ntfy_notification(notification: NtfyNotification) -> None:
    request = urllib.request.Request(
        ntfy_url(),
        data=notification.message.encode("utf-8"),
        headers={
            "Authorization": ntfy_authorization(),
            "Title": notification.title,
            "Priority": notification.priority,
            "Content-Type": "text/plain; charset=utf-8",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"ntfy API error ({exc.code}): {error_body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"ntfy API request failed: {exc.reason}") from exc


def send_alert_notifications(alerts: list[AccountAlert], threshold_minutes: int) -> list[NtfySendResult]:
    results: list[NtfySendResult] = []
    for account in alerts:
        notification = build_alert_notification(account, threshold_minutes)
        try:
            send_ntfy_notification(notification)
            results.append(
                NtfySendResult(
                    title=notification.title,
                    account_id=account.account_id,
                    threshold_minutes=threshold_minutes,
                )
            )
        except Exception as exc:
            results.append(
                NtfySendResult(
                    title=notification.title,
                    account_id=account.account_id,
                    threshold_minutes=threshold_minutes,
                    error=str(exc),
                )
            )
    return results


def send_result_label(result: NtfySendResult) -> str:
    parts: list[str] = []
    if result.threshold_minutes is not None:
        parts.append(f"{result.threshold_minutes}m")
    if result.account_id is not None:
        parts.append(f"account_id={result.account_id}")
    if not parts:
        parts.append(result.title)
    return ":".join(parts)


def summarize_send_results(results: list[NtfySendResult]) -> str:
    parts: list[str] = []
    for result in results:
        label = send_result_label(result)
        if result.success:
            parts.append(f"ntfy:{label}")
        else:
            parts.append(f"ntfy:{label}:failed({result.error})")
    return ", ".join(parts)


def require_any_success(results: list[NtfySendResult]) -> None:
    if any(result.success for result in results):
        return
    errors = "; ".join(f"{send_result_label(result)}: {result.error}" for result in results)
    raise RuntimeError(f"all ntfy sends failed: {errors}")


def require_all_success(results: list[NtfySendResult]) -> None:
    failures = [result for result in results if not result.success]
    if not failures:
        return
    errors = "; ".join(f"{send_result_label(result)}: {result.error}" for result in failures)
    raise RuntimeError(f"some ntfy sends failed: {errors}")


def update_state_with_alerts(state: dict[str, Any], alerts: list[AccountAlert], threshold_minutes: int) -> dict[str, Any]:
    updated = dict(state)
    alerts_by_threshold = alert_state_buckets(updated)
    alerts_map = dict(alerts_by_threshold.get(str(threshold_minutes), {}))
    for account in alerts:
        alerts_map[str(account.account_id)] = account.dedupe_key
    alerts_by_threshold[str(threshold_minutes)] = alerts_map
    updated["alerts"] = alerts_by_threshold
    return updated


def successful_alerts(alerts: list[AccountAlert], results: list[NtfySendResult]) -> list[AccountAlert]:
    succeeded_account_ids = {result.account_id for result in results if result.success}
    return [account for account in alerts if account.account_id in succeeded_account_ids]


def print_alert_summary(alerts: list[AccountAlert], threshold_minutes: int) -> None:
    print(f"{len(alerts)} account(s) entered the pre-full window:")
    for index, account in enumerate(alerts, start=1):
        notification = build_alert_notification(account, threshold_minutes)
        print(f"\n--- alert {index} ---")
        print(f"Title: {notification.title}")
        print(notification.message)


def run(args: argparse.Namespace) -> int:
    load_runtime_env()
    thresholds = alert_threshold_minutes()

    if args.send_current:
        notification = build_current_status_notification()
        summary = f"current account status:\n{notification.message}"
        if args.dry_run:
            print(summary)
            log("current status dry run completed without sending")
            return 0
        try:
            send_ntfy_notification(notification)
        except Exception as exc:
            result = NtfySendResult(title=notification.title, error=str(exc))
            require_any_success([result])
        print(summary)
        log(f"sent current status via ntfy:{notification.title}")
        return 0

    state = load_state()
    accounts = fetch_active_accounts()
    alert_runs = [
        (threshold_minutes, alerts)
        for threshold_minutes in thresholds
        if (alerts := select_alerts(accounts, state, threshold_minutes))
    ]

    if not alert_runs:
        log(
            "no alert sent: "
            f"{len(accounts)} active accounts checked, no unnotified account is within thresholds {format_thresholds(thresholds)}"
        )
        return 0

    if args.dry_run:
        for threshold_minutes, alerts in alert_runs:
            print_alert_summary(alerts, threshold_minutes)
        log("dry run completed without sending")
        return 0

    all_results: list[NtfySendResult] = []
    sent_count = 0
    for threshold_minutes, alerts in alert_runs:
        results = send_alert_notifications(alerts, threshold_minutes)
        all_results.extend(results)
        sent_alerts = successful_alerts(alerts, results)
        if sent_alerts:
            state = update_state_with_alerts(state, sent_alerts, threshold_minutes)
            sent_count += len(sent_alerts)
            print_alert_summary(sent_alerts, threshold_minutes)

    if sent_count == 0:
        require_any_success(all_results)

    save_state(state)
    log(f"sent alert for {sent_count} account notification(s) via {summarize_send_results(all_results)}")
    if args.strict:
        require_all_success(all_results)
    return 0


def main() -> int:
    args = parse_args()
    try:
        exit_code = run(args)
    except Exception as exc:
        if args.strict:
            raise
        log(f"waveplate alert script swallowed error: {exc}")
        exit_code = 0
    print(json.dumps({"wakeAgent": False}, ensure_ascii=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
