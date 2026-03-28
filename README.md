# 鸣潮账号代肝管理系统

## 技术栈
- 前端: Vue 3 + Vite
- 后端: FastAPI + SQLAlchemy + PostgreSQL

## 体力模型
账号保存字段：
- `id`（游戏账号 ID）
- `phone_number`、`nickname`、`abbr`、`remark`
- `last_waveplate`（上次更新体力）
- `last_waveplate_updated_at`（上次更新时间）
- `waveplate_crystal`（体力结晶）

实时恢复规则：
- 正常体力 `0~240`：每 6 分钟 +1
- 体力达到 240 后开始恢复体力结晶：每 12 分钟 +1
- 体力结晶上限 480

主页面支持快捷操作：
- 快速扣减 `-40 / -60 / -80 / -120`（体力不够时自动扣体力结晶）
- 快速增加 `+60`
- 手动输入并校准当前体力（未输入时按 0 保存）
- 排序方式切换（最先满体 / 结晶最多）

数据库说明：
- 账号表字段统一为 `id / abbr / nickname / phone_number / remark`
- 服务启动时会自动把旧字段重命名为新字段，并清理旧体力锚点列

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
- `POST /accounts/by-id/{id}/update` 更新账号
- `POST /accounts/by-id/{id}/delete` 删除账号
- `GET /accounts/{account_id}/energy` / `GET /accounts/by-id/{id}/energy` 当前体力与预警
- `POST /accounts/by-id/{id}/energy/set` 手动校准当前体力
- `POST /accounts/by-id/{id}/energy/spend` 一键扣体力（40/60/80/120）
- `POST /accounts/by-id/{id}/energy/gain` 快速加体力（+60）
- `GET /dashboard/accounts` 主页面聚合数据
- `POST /task-templates` / `GET /task-templates`
- `POST /task-instances` / `GET /task-instances` / `PATCH /task-instances/{id}`
- `POST /task-instances/generate` 按周期批量生成任务
