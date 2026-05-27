#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
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
DEFAULT_ALERT_WINDOW_MINUTES = 5
DEFAULT_ALERT_CHANNELS = "telegram"
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


@dataclass
class ChannelSendResult:
    channel: str
    target: str
    error: str | None = None

    @property
    def success(self) -> bool:
        return self.error is None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send WuWa waveplate alerts via Hermes messaging channels.")
    parser.add_argument("--dry-run", action="store_true", help="Print the message without sending or updating state.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on errors instead of swallowing them.")
    parser.add_argument(
        "--channels",
        default=None,
        help="Comma-separated Hermes channels to send to. Default: WUWA_WAVEPLATE_ALERT_CHANNELS or telegram.",
    )
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


def hermes_imports() -> tuple[Any, ...]:
    package_root = str(HERMES_PACKAGE_ROOT)
    if package_root not in sys.path:
        sys.path.insert(0, package_root)
    from gateway.config import HomeChannel, Platform, PlatformConfig, load_gateway_config
    from tools.send_message_tool import _send_to_platform

    return HomeChannel, Platform, PlatformConfig, load_gateway_config, _send_to_platform


def parse_channels(raw: str | None) -> list[str]:
    value = (raw or os.getenv("WUWA_WAVEPLATE_ALERT_CHANNELS", DEFAULT_ALERT_CHANNELS)).strip()
    aliases = {
        "weixin": "weixin",
        "wechat": "weixin",
        "wx": "weixin",
        "telegram": "telegram",
        "tg": "telegram",
    }
    channels: list[str] = []
    for item in value.replace(";", ",").split(","):
        name = item.strip().lower()
        if not name:
            continue
        channel = aliases.get(name)
        if not channel:
            raise RuntimeError(f"unsupported alert channel: {item}")
        if channel not in channels:
            channels.append(channel)
    if not channels:
        raise RuntimeError("no alert channels configured")
    return channels


def resolve_targets(channels: list[str]) -> dict[str, str]:
    targets: dict[str, str] = {}
    for channel in channels:
        if channel == "weixin":
            targets[channel] = (
                os.getenv("WUWA_WAVEPLATE_ALERT_WEIXIN_TARGET", "").strip()
                or os.getenv("WUWA_WAVEPLATE_ALERT_TARGET", "").strip()
                or os.getenv("WEIXIN_HOME_CHANNEL", "").strip()
                or DEFAULT_WEIXIN_TARGET
            )
        elif channel == "telegram":
            targets[channel] = (
                os.getenv("WUWA_WAVEPLATE_ALERT_TELEGRAM_TARGET", "").strip()
                or os.getenv("TELEGRAM_HOME_CHANNEL", "").strip()
            )
        else:
            raise RuntimeError(f"unsupported alert channel: {channel}")
    return targets


def configured_home_target(pconfig: Any) -> str:
    if not pconfig:
        return ""
    home_channel = getattr(pconfig, "home_channel", None)
    return str(getattr(home_channel, "chat_id", "") or "").strip()


def telegram_token_from_config(pconfig: Any) -> str:
    return str(getattr(pconfig, "token", "") or os.getenv("TELEGRAM_BOT_TOKEN", "")).strip()


def telegram_chunks(message: str, limit: int = 3900) -> list[str]:
    if len(message) <= limit:
        return [message]

    chunks: list[str] = []
    current: list[str] = []
    current_size = 0
    for line in message.splitlines(keepends=True):
        if len(line) > limit:
            if current:
                chunks.append("".join(current).rstrip())
                current = []
                current_size = 0
            for start in range(0, len(line), limit):
                chunks.append(line[start : start + limit].rstrip())
            continue
        if current and current_size + len(line) > limit:
            chunks.append("".join(current).rstrip())
            current = []
            current_size = 0
        current.append(line)
        current_size += len(line)
    if current:
        chunks.append("".join(current).rstrip())
    return [chunk for chunk in chunks if chunk]


def send_telegram_via_bot_api(token: str, target: str, message: str) -> None:
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured for Hermes")
    telegram_proxy = os.getenv("TELEGRAM_PROXY", "").strip()
    proxy_handler = (
        urllib.request.ProxyHandler({"http": telegram_proxy, "https": telegram_proxy})
        if telegram_proxy
        else urllib.request.ProxyHandler()
    )
    opener = urllib.request.build_opener(proxy_handler)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for chunk in telegram_chunks(message):
        payload = json.dumps(
            {
                "chat_id": target,
                "text": chunk,
                "disable_web_page_preview": True,
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with opener.open(request, timeout=30) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")[:500]
            raise RuntimeError(f"Telegram API error ({exc.code}): {error_body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Telegram API request failed: {exc.reason}") from exc
        if not body.get("ok"):
            raise RuntimeError(f"Telegram API error: {body.get('description', 'unknown error')}")


async def _send_channel_message(message: str, channel: str, target: str) -> str:
    HomeChannel, Platform, PlatformConfig, load_gateway_config, send_to_platform = hermes_imports()
    config = load_gateway_config()
    platform_by_channel = {
        "weixin": Platform.WEIXIN,
        "telegram": Platform.TELEGRAM,
    }
    platform = platform_by_channel.get(channel)
    if not platform:
        raise RuntimeError(f"unsupported alert channel: {channel}")

    pconfig = config.platforms.get(platform)
    target = target.strip() or configured_home_target(pconfig)

    if channel == "weixin" and (not pconfig or not pconfig.enabled):
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
    elif channel == "telegram" and (not pconfig or not pconfig.enabled):
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured for Hermes")
        pconfig = PlatformConfig(
            enabled=True,
            token=token,
            home_channel=HomeChannel(platform=Platform.TELEGRAM, chat_id=target, name="Telegram Alert Target")
            if target
            else None,
        )

    target = target.strip() or configured_home_target(pconfig)
    if not target:
        raise RuntimeError(
            f"{channel} target is not configured. Set WUWA_WAVEPLATE_ALERT_{channel.upper()}_TARGET "
            f"or {channel.upper()}_HOME_CHANNEL."
        )

    result = await send_to_platform(platform, pconfig, target, message)
    if isinstance(result, dict) and result.get("error"):
        if channel == "telegram":
            token = telegram_token_from_config(pconfig)
            try:
                await asyncio.to_thread(send_telegram_via_bot_api, token, target, message)
                return target
            except Exception as fallback_exc:
                raise RuntimeError(
                    f"{result['error']}; Telegram HTTP fallback failed: {fallback_exc}"
                ) from fallback_exc
        raise RuntimeError(result["error"])
    return target


async def _send_message_to_channels(message: str, targets: dict[str, str]) -> list[ChannelSendResult]:
    results: list[ChannelSendResult] = []
    for channel, target in targets.items():
        try:
            resolved_target = await _send_channel_message(message, channel, target)
            results.append(ChannelSendResult(channel=channel, target=resolved_target))
        except Exception as exc:
            results.append(ChannelSendResult(channel=channel, target=target, error=str(exc)))
    return results


def send_message_to_channels(message: str, targets: dict[str, str]) -> list[ChannelSendResult]:
    return asyncio.run(_send_message_to_channels(message, targets))


def summarize_send_results(results: list[ChannelSendResult]) -> str:
    parts: list[str] = []
    for result in results:
        if result.success:
            parts.append(f"{result.channel}:{result.target}")
        else:
            parts.append(f"{result.channel}:failed({result.error})")
    return ", ".join(parts)


def require_any_success(results: list[ChannelSendResult]) -> None:
    if any(result.success for result in results):
        return
    errors = "; ".join(f"{result.channel}: {result.error}" for result in results)
    raise RuntimeError(f"all alert channel sends failed: {errors}")


def require_all_success(results: list[ChannelSendResult]) -> None:
    failures = [result for result in results if not result.success]
    if not failures:
        return
    errors = "; ".join(f"{result.channel}: {result.error}" for result in failures)
    raise RuntimeError(f"some alert channel sends failed: {errors}")


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
    channels = parse_channels(args.channels)
    targets = resolve_targets(channels)

    if args.send_current:
        message = build_current_status_message()
        summary = f"current account status:\n{message}"
        if args.dry_run:
            print(summary)
            log("current status dry run completed without sending")
            return 0
        results = send_message_to_channels(message, targets)
        require_any_success(results)
        print(summary)
        log(f"sent current status via {summarize_send_results(results)}")
        if args.strict:
            require_all_success(results)
        return 0

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

    results = send_message_to_channels(message, targets)
    require_any_success(results)
    save_state(update_state_with_alerts(state, alerts))
    print(summary)
    log(f"sent alert for {len(alerts)} account(s) via {summarize_send_results(results)}")
    if args.strict:
        require_all_success(results)
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
