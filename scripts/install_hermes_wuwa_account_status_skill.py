#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path


SKILL_CATEGORY = "gaming"
SKILL_NAME = "wuwa-account-status"
WRAPPER_NAME = "wuwa_account_status.py"
HERMES_HOME = Path(os.getenv("HERMES_HOME", str(Path.home() / ".hermes"))).expanduser()
SKILL_DIR = HERMES_HOME / "skills" / SKILL_CATEGORY / SKILL_NAME
WRAPPER_PATH = SKILL_DIR / "scripts" / WRAPPER_NAME
SKILL_MD_PATH = SKILL_DIR / "SKILL.md"
REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCE_SCRIPT = REPO_ROOT / "scripts" / "hermes_wuwa_account_status.py"

SKILL_MD_CONTENT = """---
name: wuwa-account-status
description: "Query live 鸣潮 / Wuthering Waves（including common typo references like 明朝）账号体力、满体时间、今日日常/聚落完成情况 from the local wuwa-mgt database when the user asks about waveplate, stamina, dailies, or nest progress."
version: 1.0.0
metadata:
  hermes:
    tags: [wuwa, wuthering-waves, 鸣潮, 明朝, waveplate, stamina, 体力, 满体, 日常, 聚落]
    related_skills: []
prerequisites:
  commands: [python3, psql]
---

# WuWa Account Status

Use this skill when the user asks about any of:

- 鸣潮 / WuWa 账号体力
- 明朝 / 鸣潮 账号体力（口误或手误）
- 当前有多少体力 / 什么时候满体 / 还要多久满
- 今天日常或聚落还有什么没做
- Specific account status by game id, abbr, or nickname

## Rule

Always fetch live data by running the bundled script. Do not answer from memory.

## Commands

All active accounts:

```bash
python3 "${HERMES_HOME:-$HOME/.hermes}/skills/gaming/wuwa-account-status/scripts/wuwa_account_status.py"
```

Filter to a specific account mentioned by the user:

```bash
python3 "${HERMES_HOME:-$HOME/.hermes}/skills/gaming/wuwa-account-status/scripts/wuwa_account_status.py" --account "黑兔佑我"
```

The `--account` value can be any substring of the game id, abbr, or nickname. Repeat the flag if the user mentioned multiple accounts.

## Response Style

- Preserve exact numbers and times from the script output.
- Keep the answer short and practical.
- Stay factual. Do not add strategy advice, urgency judgments, or farming suggestions unless the user explicitly asks for recommendations.
- If the script reports no matching account, tell the user no active account matched and show the available active account labels from the script output.
- `今日` means the business day after applying `RESET_HOUR` from the wuwa-mgt environment.
- Treat `done` and `skipped` as completed.
"""


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_if_changed(path: Path, content: str, executable: bool = False) -> bool:
    ensure_parent(path)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        if executable:
            os.chmod(path, 0o755)
        return False
    path.write_text(content, encoding="utf-8")
    if executable:
        os.chmod(path, 0o755)
    return True


def write_wrapper() -> bool:
    content = (
        "#!/usr/bin/env python3\n"
        "import runpy\n"
        f"runpy.run_path({str(SOURCE_SCRIPT)!r}, run_name='__main__')\n"
    )
    return write_if_changed(WRAPPER_PATH, content, executable=True)


def write_skill_markdown() -> bool:
    return write_if_changed(SKILL_MD_PATH, SKILL_MD_CONTENT)


def main() -> int:
    if not SOURCE_SCRIPT.exists():
        raise FileNotFoundError(f"missing source script: {SOURCE_SCRIPT}")
    wrapper_changed = write_wrapper()
    skill_changed = write_skill_markdown()
    print(f"skill_dir: {SKILL_DIR}")
    print(f"skill_md: {SKILL_MD_PATH} ({'updated' if skill_changed else 'unchanged'})")
    print(f"wrapper: {WRAPPER_PATH} ({'updated' if wrapper_changed else 'unchanged'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
