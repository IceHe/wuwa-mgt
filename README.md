# 鸣潮账号代肝管理系统

## 技术栈
- 前端: Vue 3 + Vite
- 后端: FastAPI + SQLAlchemy + PostgreSQL

## 体力模型（最简版）
账号只保留两个体力锚点字段：
- `energy_at_prev_4am`: 前一个已过去 4:00 的体力
- `prev_4am_at`: 这个前一个 4:00 的时间戳

当前体力实时计算规则：
- 0~240: 每 6 分钟 +1
- 240~480: 每 12 分钟 +1
- 上限 480

支持一键扣体力按钮：`40 / 60 / 80 / 120`。
主页面按“最先达到 240 体力”排序，并显示倒计时。

## 目录
- `backend/` FastAPI 服务
- `frontend/` Vue 页面

## 后端启动
```bash
cd backend
cp .env.example .env
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

初始化默认任务模板（每日/每周/版本/特定周期）：
```bash
cd backend
python scripts/seed_task_templates.py
```

`.env` 默认数据库：
```env
DATABASE_URL=postgresql://<user>:<password>@<host>:5432/<database>
APP_TZ=Asia/Shanghai
```

## 前端启动
```bash
cd frontend
npm install
npm run dev
```

默认前端请求 `http://127.0.0.1:8000`，如需修改：
```bash
VITE_API_BASE=http://127.0.0.1:8000 npm run dev
```

## 主要接口
- `POST /accounts` 创建账号
- `GET /accounts` 账号列表
- `PATCH /accounts/{id}` 更新账号
- `DELETE /accounts/{id}` 删除账号
- `GET /accounts/{id}/energy` 当前体力与预警
- `POST /accounts/{id}/energy/set` 手动校准当前体力
- `POST /accounts/{id}/energy/spend` 一键扣体力（40/60/80/120）
- `GET /dashboard/accounts` 主页面聚合数据
- `POST /task-templates` / `GET /task-templates`
- `POST /task-instances` / `GET /task-instances` / `PATCH /task-instances/{id}`
- `POST /task-instances/generate` 按周期批量生成任务
