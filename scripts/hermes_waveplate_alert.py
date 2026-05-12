#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


DEFAULT_APP_TZ = "Asia/Shanghai"
DEFAULT_ALERT_THRESHOLD_MINUTES = 60
DEFAULT_ALERT_WINDOW_MINUTES = 5
DEFAULT_WEIXIN_TARGET = "o9cq80_73zR-7gvWT-K8drIA_4WA@im.wechat"
HERMES_PACKAGE_ROOT = Path("/usr/local/lib/hermes-agent")
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send WuWa waveplate alerts via Hermes Weixin.")
    parser.add_argument("--dry-run", action="store_true", help="Print the message without sending or updating state.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on errors instead of swallowing them.")
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
        os.environ[key] = value.strip()


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


def normalize_database_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def database_url() -> str:
    raw = os.getenv("DATABASE_URL", "").strip()
    if not raw:
        raise RuntimeError("DATABASE_URL is not configured in environment, .env, or backend/.env")
    return normalize_database_url(raw)


def load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {"version": 1, "alerts": {}}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        log(f"state file is invalid, resetting it: {exc}")
        return {"version": 1, "alerts": {}}


def save_state(state: dict[str, Any]) -> None:
    ensure_parent(STATE_FILE)
    payload = dict(state)
    payload["version"] = 1
    payload["updated_at"] = now_in_app_tz().isoformat()
    tmp_path = STATE_FILE.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(STATE_FILE)


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
    window_minutes: int,
) -> list[AccountAlert]:
    now = now_in_app_tz()
    threshold_seconds = threshold_minutes * 60
    window_seconds = window_minutes * 60
    lower_bound = max(1, threshold_seconds - window_seconds)
    alerts = state.get("alerts", {})

    candidates: list[AccountAlert] = []
    for account in accounts:
        remaining_seconds = int((account.full_waveplate_at - now).total_seconds())
        if remaining_seconds < lower_bound or remaining_seconds > threshold_seconds:
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


def build_message(alerts: list[AccountAlert], threshold_minutes: int) -> str:
    header = f"【鸣潮体力提醒】以下账号将在 {threshold_minutes} 分钟内满体："
    lines = [header, ""]
    for index, account in enumerate(alerts, start=1):
        full_at = account.full_waveplate_at.strftime("%m-%d %H:%M")
        lines.append(
            f"{index}. {account.abbr} / {account.game_id} / {account.nickname}"
        )
        lines.append(
            f"   剩余 {format_remaining(account.remaining_seconds)}，满体时间 {full_at}"
        )
    return "\n".join(lines)


def hermes_imports() -> tuple[Any, ...]:
    package_root = str(HERMES_PACKAGE_ROOT)
    if package_root not in sys.path:
        sys.path.insert(0, package_root)
    from gateway.config import HomeChannel, Platform, PlatformConfig, load_gateway_config
    from tools.send_message_tool import _send_to_platform

    return HomeChannel, Platform, PlatformConfig, load_gateway_config, _send_to_platform


async def _send_weixin_message(message: str, target: str) -> None:
    HomeChannel, Platform, PlatformConfig, load_gateway_config, send_to_platform = hermes_imports()
    config = load_gateway_config()
    pconfig = config.platforms.get(Platform.WEIXIN)

    if not pconfig or not pconfig.enabled:
        token = os.getenv("WEIXIN_TOKEN", "").strip()
        account_id = os.getenv("WEIXIN_ACCOUNT_ID", "").strip()
        if not token or not account_id:
            raise RuntimeError("WEIXIN token/account is not configured for Hermes")
        pconfig = PlatformConfig(
            enabled=True,
            token=token,
            home_channel=HomeChannel(platform=Platform.WEIXIN, chat_id=target, name="Weixin Alert Target"),
            extra={
                "account_id": account_id,
                "base_url": os.getenv("WEIXIN_BASE_URL", "").strip(),
                "cdn_base_url": os.getenv("WEIXIN_CDN_BASE_URL", "").strip(),
            },
        )

    result = await send_to_platform(Platform.WEIXIN, pconfig, target, message)
    if result and result.get("error"):
        raise RuntimeError(result["error"])


def send_weixin_message(message: str, target: str) -> None:
    asyncio.run(_send_weixin_message(message, target))


def update_state_with_alerts(state: dict[str, Any], alerts: list[AccountAlert]) -> dict[str, Any]:
    updated = dict(state)
    alerts_map = dict(updated.get("alerts", {}))
    for account in alerts:
        alerts_map[str(account.account_id)] = account.dedupe_key
    updated["alerts"] = alerts_map
    return updated


def run(args: argparse.Namespace) -> int:
    load_runtime_env()
    threshold_minutes = env_int("WUWA_WAVEPLATE_ALERT_THRESHOLD_MINUTES", DEFAULT_ALERT_THRESHOLD_MINUTES)
    window_minutes = env_int("WUWA_WAVEPLATE_ALERT_WINDOW_MINUTES", DEFAULT_ALERT_WINDOW_MINUTES)
    target = os.getenv("WUWA_WAVEPLATE_ALERT_TARGET", DEFAULT_WEIXIN_TARGET).strip() or DEFAULT_WEIXIN_TARGET

    state = load_state()
    accounts = fetch_active_accounts()
    alerts = select_alerts(accounts, state, threshold_minutes, window_minutes)

    if not alerts:
        log(
            "no alert sent: "
            f"{len(accounts)} active accounts checked, no account entered the {threshold_minutes}m window"
        )
        return 0

    message = build_message(alerts, threshold_minutes)
    summary = f"{len(alerts)} account(s) entered the pre-full window:\n{message}"

    if args.dry_run:
        print(summary)
        log("dry run completed without sending")
        return 0

    send_weixin_message(message, target)
    save_state(update_state_with_alerts(state, alerts))
    print(summary)
    log(f"sent alert for {len(alerts)} account(s) to {target}")
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
