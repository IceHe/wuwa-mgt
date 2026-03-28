from datetime import datetime

from app.database import SessionLocal
from app.models import TaskTemplate, TaskType

DEFAULT_TEMPLATES = [
    {"name": "清体力", "task_type": TaskType.daily, "default_priority": 1, "description": "优先避免体力溢出"},
    {"name": "打聚落（声骸）", "task_type": TaskType.daily, "default_priority": 2, "description": "获取声骸"},
    {"name": "打脆岩（贝币）", "task_type": TaskType.daily, "default_priority": 3, "description": "获取贝币"},
    {"name": "肉鸽周本", "task_type": TaskType.weekly, "default_priority": 2, "description": "每周挑战"},
    {"name": "周本Boss挑战", "task_type": TaskType.weekly, "default_priority": 1, "description": "技能突破材料"},
    {"name": "声骸定向合成", "task_type": TaskType.weekly, "default_priority": 3, "description": "指定套装限量"},
    {"name": "小珊瑚兑换限定抽数", "task_type": TaskType.half_version, "default_priority": 1, "description": "半版本检查"},
    {"name": "角色试用", "task_type": TaskType.version, "default_priority": 2, "description": "版本活动"},
    {"name": "限时活动", "task_type": TaskType.version, "default_priority": 1, "description": "限定奖励"},
    {"name": "深塔挑战", "task_type": TaskType.special, "default_priority": 1, "description": "包含兑换所"},
    {"name": "海墟挑战", "task_type": TaskType.special, "default_priority": 2, "description": "特定周期"},
    {"name": "矩阵挑战", "task_type": TaskType.special, "default_priority": 2, "description": "特定周期"},
]


def main() -> None:
    db = SessionLocal()
    try:
        created = 0
        for item in DEFAULT_TEMPLATES:
            exists = (
                db.query(TaskTemplate)
                .filter(TaskTemplate.name == item["name"], TaskTemplate.task_type == item["task_type"])
                .first()
            )
            if exists:
                continue
            db.add(TaskTemplate(**item, is_active=True))
            created += 1
        db.commit()
        print(f"seed completed at {datetime.now().isoformat()} created={created}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
