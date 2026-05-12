#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path


JOB_NAME = "鸣潮体力 1小时预满提醒"
WRAPPER_NAME = "wuwa_waveplate_alert.py"
JOB_PROMPT = "This cron job is handled entirely by its pre-run script. No agent response is required."
HERMES_HOME = Path(os.getenv("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
JOBS_FILE = HERMES_HOME / "cron" / "jobs.json"
WRAPPER_PATH = HERMES_HOME / "scripts" / WRAPPER_NAME
REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_SCRIPT = REPO_ROOT / "scripts" / "hermes_waveplate_alert.py"


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_wrapper() -> tuple[Path, bool]:
    ensure_parent(WRAPPER_PATH)
    content = (
        "#!/usr/bin/env python3\n"
        "import runpy\n"
        f"runpy.run_path({str(SOURCE_SCRIPT)!r}, run_name='__main__')\n"
    )
    changed = True
    if WRAPPER_PATH.exists() and WRAPPER_PATH.read_text(encoding="utf-8") == content:
        changed = False
    else:
        WRAPPER_PATH.write_text(content, encoding="utf-8")
        os.chmod(WRAPPER_PATH, 0o755)
    return WRAPPER_PATH, changed


def load_job_doc() -> dict:
    if not JOBS_FILE.exists():
        return {"jobs": [], "updated_at": None}
    return json.loads(JOBS_FILE.read_text(encoding="utf-8"))


def save_job_doc(doc: dict) -> None:
    ensure_parent(JOBS_FILE)
    doc["updated_at"] = datetime.now().astimezone().isoformat()
    tmp_path = JOBS_FILE.with_suffix(".tmp")
    tmp_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(JOBS_FILE)
    os.chmod(JOBS_FILE, 0o600)


def compute_next_run(interval_minutes: int = 5) -> str:
    now = datetime.now().astimezone()
    base = now.replace(second=0, microsecond=0)
    minute_offset = base.minute % interval_minutes
    if minute_offset == 0:
        next_run = base + timedelta(minutes=interval_minutes)
    else:
        next_run = base + timedelta(minutes=(interval_minutes - minute_offset))
    return next_run.isoformat()


def build_job(existing: dict | None) -> dict:
    now_iso = datetime.now().astimezone().isoformat()
    job_id = existing.get("id") if existing else secrets.token_hex(6)
    repeat_completed = (
        existing.get("repeat", {}).get("completed", 0)
        if existing and isinstance(existing.get("repeat"), dict)
        else 0
    )
    return {
        "id": job_id,
        "name": JOB_NAME,
        "prompt": JOB_PROMPT,
        "skills": [],
        "skill": None,
        "model": None,
        "provider": None,
        "base_url": None,
        "script": WRAPPER_NAME,
        "context_from": None,
        "schedule": {
            "kind": "interval",
            "minutes": 5,
            "display": "every 5m",
        },
        "schedule_display": "every 5m",
        "repeat": {
            "times": None,
            "completed": repeat_completed,
        },
        "enabled": True,
        "state": "scheduled",
        "paused_at": None,
        "paused_reason": None,
        "created_at": existing.get("created_at", now_iso) if existing else now_iso,
        "next_run_at": compute_next_run(5),
        "last_run_at": existing.get("last_run_at") if existing else None,
        "last_status": existing.get("last_status") if existing else None,
        "last_error": existing.get("last_error") if existing else None,
        "last_delivery_error": existing.get("last_delivery_error") if existing else None,
        "deliver": "local",
        "origin": None,
        "enabled_toolsets": None,
        "workdir": None,
    }


def install_job() -> tuple[str, bool, int]:
    doc = load_job_doc()
    jobs = doc.get("jobs", [])
    matched: list[dict] = []
    kept: list[dict] = []
    for job in jobs:
        if job.get("name") == JOB_NAME or job.get("script") == WRAPPER_NAME:
            matched.append(job)
            continue
        kept.append(job)

    existing = matched[0] if matched else None
    installed = build_job(existing)
    kept.append(installed)
    doc["jobs"] = kept
    save_job_doc(doc)
    return installed["id"], existing is None, max(0, len(matched) - 1)


def main() -> int:
    wrapper_path, wrapper_changed = write_wrapper()
    job_id, created, duplicates_removed = install_job()
    print(f"wrapper: {wrapper_path} ({'updated' if wrapper_changed else 'unchanged'})")
    print(f"job: {JOB_NAME} ({'created' if created else 'updated'})")
    print(f"job_id: {job_id}")
    if duplicates_removed:
        print(f"duplicates_removed: {duplicates_removed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
