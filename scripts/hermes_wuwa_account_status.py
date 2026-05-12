#!/usr/bin/env python3
from __future__ import annotations

import argparse
from difflib import SequenceMatcher
import json
import math
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo


DEFAULT_APP_TZ = "Asia/Shanghai"
DEFAULT_RESET_HOUR = 4
WAVEPLATE_CAP = 240
WAVEPLATE_RECOVER_SECONDS = 6 * 60
WAVEPLATE_CRYSTAL_CAP = 480
CRYSTAL_RECOVER_SECONDS = 12 * 60
HERMES_HOME = Path(os.getenv("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class AccountStatus:
    account_id: int
    game_id: str
    abbr: str
    nickname: str
    full_waveplate_at: datetime
    full_waveplate_crystal: int
    current_waveplate: int = 0
    current_waveplate_crystal: int = 0
    daily_task_status: str = "todo"
    daily_nest_status: str = "todo"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Query WuWa account waveplate and daily progress for Hermes."
    )
    parser.add_argument(
        "--account",
        action="append",
        default=[],
        help="Filter by game id / abbr / nickname substring. Repeatable.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of formatted text.",
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


def env_int(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def get_timezone() -> ZoneInfo:
    tz_name = os.getenv("APP_TZ", DEFAULT_APP_TZ).strip() or DEFAULT_APP_TZ
    return ZoneInfo(tz_name)


def now_in_app_tz() -> datetime:
    return datetime.now(get_timezone())


def reset_day(now: datetime, reset_hour: int) -> datetime:
    current = now.astimezone(get_timezone())
    day = datetime(current.year, current.month, current.day, tzinfo=current.tzinfo)
    if current.hour < reset_hour:
        return day - timedelta(days=1)
    return day


def normalize_database_url(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def database_url() -> str:
    raw = os.getenv("DATABASE_URL", "").strip()
    if not raw:
        raise RuntimeError("DATABASE_URL is not configured in environment, .env, or backend/.env")
    return normalize_database_url(raw)


def psql_query(query: str) -> list[list[str]]:
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
    rows: list[list[str]] = []
    for raw_line in result.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        rows.append(line.split("\t"))
    return rows


def fetch_active_accounts() -> list[AccountStatus]:
    query = """
SELECT
  account_id,
  id,
  abbr,
  nickname,
  EXTRACT(EPOCH FROM full_waveplate_at)::bigint AS full_waveplate_epoch,
  full_waveplate_crystal
FROM accounts
WHERE is_active IS TRUE
ORDER BY full_waveplate_at ASC, abbr ASC, account_id ASC;
""".strip()
    accounts: list[AccountStatus] = []
    for row in psql_query(query):
        if len(row) != 6:
            raise RuntimeError(f"unexpected accounts row format: {row!r}")
        full_at = datetime.fromtimestamp(int(row[4]), tz=timezone.utc).astimezone(get_timezone())
        accounts.append(
            AccountStatus(
                account_id=int(row[0]),
                game_id=row[1],
                abbr=row[2],
                nickname=row[3],
                full_waveplate_at=full_at,
                full_waveplate_crystal=int(row[5]),
            )
        )
    return accounts


def normalize_checkin_status(status: str, is_done: bool) -> str:
    normalized = status.strip().lower()
    if normalized in {"todo", "done", "skipped"}:
        return normalized
    if is_done:
        return "done"
    return "todo"


def fetch_daily_statuses(account_ids: list[int], business_day: datetime) -> dict[int, dict[str, str]]:
    if not account_ids:
        return {}
    joined_ids = ",".join(str(account_id) for account_id in sorted(account_ids))
    period_key = business_day.strftime("%Y-%m-%d")
    query = f"""
SELECT account_id, flag_key, COALESCE(status, ''), is_done
FROM account_checkins
WHERE account_id IN ({joined_ids})
  AND period_type = 'daily'
  AND period_key = '{period_key}'
  AND flag_key IN ('daily_task', 'daily_nest');
""".strip()
    statuses: dict[int, dict[str, str]] = {}
    for row in psql_query(query):
        if len(row) != 4:
            raise RuntimeError(f"unexpected checkins row format: {row!r}")
        account_id = int(row[0])
        flag_key = row[1]
        normalized = normalize_checkin_status(row[2], row[3].strip().lower() in {"t", "true", "1"})
        if account_id not in statuses:
            statuses[account_id] = {}
        statuses[account_id][flag_key] = normalized
    return statuses


def clamp_waveplate(value: int) -> int:
    return max(0, min(WAVEPLATE_CAP, value))


def clamp_waveplate_crystal(value: int) -> int:
    return max(0, min(WAVEPLATE_CRYSTAL_CAP, value))


def current_resources_from_full_time(full_at: datetime, full_crystal: int, now: datetime) -> tuple[int, int]:
    base_crystal = clamp_waveplate_crystal(full_crystal)
    delta_seconds = int((full_at - now).total_seconds())
    if delta_seconds > 0:
        missing = min(WAVEPLATE_CAP, int(math.ceil(delta_seconds / WAVEPLATE_RECOVER_SECONDS)))
        return WAVEPLATE_CAP - missing, base_crystal

    crystal_gained = max(0, int((now - full_at).total_seconds()) // CRYSTAL_RECOVER_SECONDS)
    return WAVEPLATE_CAP, clamp_waveplate_crystal(base_crystal + crystal_gained)


def seconds_to_waveplate_full(full_at: datetime, now: datetime) -> int:
    return max(0, int((full_at - now).total_seconds()))


def format_duration(seconds: int) -> str:
    if seconds <= 0:
        return "0 分钟"
    minutes = max(1, math.ceil(seconds / 60))
    if minutes < 60:
        return f"{minutes} 分钟"
    hours, mins = divmod(minutes, 60)
    if mins == 0:
        return f"{hours} 小时"
    return f"{hours} 小时 {mins} 分钟"


def format_full_at(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M")


def fuzzy_match_score(query: str, account: AccountStatus) -> float:
    normalized = query.casefold().strip()
    if not normalized:
        return 0.0
    candidates = [
        account.game_id.casefold(),
        account.abbr.casefold(),
        account.nickname.casefold(),
        f"{account.abbr} {account.game_id} {account.nickname}".casefold(),
    ]
    return max(SequenceMatcher(None, normalized, candidate).ratio() for candidate in candidates)


def fuzzy_match_threshold(query: str) -> float | None:
    normalized = query.strip()
    if not normalized or normalized.isdigit():
        return None
    length = len(normalized)
    if length <= 1:
        return None
    if length == 2:
        return 0.85
    if length == 3:
        return 0.60
    return 0.68


def matches_query(account: AccountStatus, queries: list[str]) -> bool:
    if not queries:
        return True
    haystack = " ".join([account.game_id, account.abbr, account.nickname]).casefold()
    cleaned_queries = [query.strip() for query in queries if query.strip()]
    if any(query.casefold() in haystack for query in cleaned_queries):
        return True
    for query in cleaned_queries:
        threshold = fuzzy_match_threshold(query)
        if threshold is None:
            continue
        if fuzzy_match_score(query, account) >= threshold:
            return True
    return False


def apply_daily_statuses(
    accounts: list[AccountStatus],
    statuses: dict[int, dict[str, str]],
    now: datetime,
) -> None:
    for account in accounts:
        account.current_waveplate, account.current_waveplate_crystal = current_resources_from_full_time(
            account.full_waveplate_at,
            account.full_waveplate_crystal,
            now,
        )
        account_flags = statuses.get(account.account_id, {})
        account.daily_task_status = account_flags.get("daily_task", "todo")
        account.daily_nest_status = account_flags.get("daily_nest", "todo")


def incomplete_items(account: AccountStatus) -> list[str]:
    items: list[str] = []
    if account.daily_task_status not in {"done", "skipped"}:
        items.append("日常")
    if account.daily_nest_status not in {"done", "skipped"}:
        items.append("聚落")
    return items


def format_account_block(index: int, account: AccountStatus, now: datetime) -> str:
    lines = [f"{index}. {account.abbr} / {account.game_id} / {account.nickname}"]
    lines.append(
        f"   体力 {clamp_waveplate(account.current_waveplate)}/{WAVEPLATE_CAP}，结晶 {clamp_waveplate_crystal(account.current_waveplate_crystal)}"
    )
    to_full_seconds = seconds_to_waveplate_full(account.full_waveplate_at, now)
    if to_full_seconds == 0:
        lines.append(f"   已满体，满体时间 {format_full_at(account.full_waveplate_at)}")
    else:
        lines.append(
            f"   满体还需 {format_duration(to_full_seconds)}，满体时间 {format_full_at(account.full_waveplate_at)}"
        )
    undone = incomplete_items(account)
    lines.append(f"   今日未完成：{' / '.join(undone) if undone else '无'}")
    return "\n".join(lines)


def build_text_output(
    accounts: list[AccountStatus],
    active_accounts: list[AccountStatus],
    queries: list[str],
    business_day: datetime,
    reset_hour: int,
    now: datetime,
) -> str:
    header = (
        f"【鸣潮账号状态】业务日 {business_day.strftime('%Y-%m-%d')}"
        f"（时区 {get_timezone().key}，重置 {reset_hour:02d}:00）"
    )
    if not accounts:
        if not queries:
            return header + "\n\n当前没有启用账号。"
        labels = [f"{item.abbr} / {item.game_id} / {item.nickname}" for item in active_accounts]
        suffix = "\n".join(labels) if labels else "当前没有启用账号。"
        return (
            header
            + "\n\n未匹配到启用账号："
            + "，".join(query for query in queries if query.strip())
            + "\n可用账号：\n"
            + suffix
        )
    blocks = [format_account_block(index, account, now) for index, account in enumerate(accounts, start=1)]
    return header + "\n\n" + "\n\n".join(blocks)


def build_json_output(accounts: list[AccountStatus], business_day: datetime, reset_hour: int) -> dict[str, Any]:
    now = now_in_app_tz()
    return {
        "timezone": get_timezone().key,
        "reset_hour": reset_hour,
        "business_date": business_day.strftime("%Y-%m-%d"),
        "generated_at": now.isoformat(),
        "accounts": [
            {
                "account_id": account.account_id,
                "id": account.game_id,
                "abbr": account.abbr,
                "nickname": account.nickname,
                "current_waveplate": clamp_waveplate(account.current_waveplate),
                "current_waveplate_crystal": clamp_waveplate_crystal(account.current_waveplate_crystal),
                "full_waveplate_at": account.full_waveplate_at.isoformat(),
                "waveplate_full_in_seconds": seconds_to_waveplate_full(account.full_waveplate_at, now),
                "daily_task_status": account.daily_task_status,
                "daily_nest_status": account.daily_nest_status,
                "unfinished_today": incomplete_items(account),
            }
            for account in accounts
        ],
    }


def run(args: argparse.Namespace) -> int:
    load_runtime_env()
    reset_hour = env_int("RESET_HOUR", DEFAULT_RESET_HOUR)
    now = now_in_app_tz()
    business_day = reset_day(now, reset_hour)
    queries = [value.strip() for value in args.account if value and value.strip()]

    active_accounts = fetch_active_accounts()
    matched_accounts = [account for account in active_accounts if matches_query(account, queries)]
    daily_statuses = fetch_daily_statuses([item.account_id for item in matched_accounts], business_day)
    apply_daily_statuses(matched_accounts, daily_statuses, now)

    if args.json:
        print(json.dumps(build_json_output(matched_accounts, business_day, reset_hour), ensure_ascii=False, indent=2))
        return 0

    print(build_text_output(matched_accounts, active_accounts, queries, business_day, reset_hour, now))
    return 0


def main() -> int:
    return run(parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
