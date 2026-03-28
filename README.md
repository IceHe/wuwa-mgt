# 鸣潮账号体力管理系统

## 技术栈
- 前端：Vue 3 + Vite
- 后端：FastAPI + SQLAlchemy + PostgreSQL

## 页面说明
- `每日每周`
  - 账号体力总览、满体力时间、体力快捷操作
  - 每日清单（`日常`、`聚落`）
  - 每周清单（`门扉`、`周本`）
- `周期活动`
  - 每版本：`矩阵叠兵`、`小珊瑚兑换`、`全息挑战`、`声骸模板调整`
  - 每半版本：`角色试用`
  - 每月：`深塔兑换所`
  - 每四周：`深塔`、`海墟`
  - 限时：`填方块`（3/26~4/13）、`音游`（3/19~4/29）
- `账号管理`
  - 新建账号、编辑账号、删除账号
  - 手机号默认掩码，支持复制完整号码

## 体力规则
- 正常体力 `0~240`：每 6 分钟 +1
- 体力达到 240 后恢复体力结晶：每 12 分钟 +1
- 体力结晶上限 480

支持操作：
- 快捷扣减：`-40 / -60 / -80 / -120`（不足会失败提示）
- 快捷增加：`+40 / +60`
- 输入框直接修改当前体力和体力结晶（回车或失焦保存）

## 数据模型
- 账号表：`accounts`
  - 核心字段：`id / abbr / nickname / phone_number / remark / tacet`
  - 体力字段：`last_waveplate / last_waveplate_updated_at / waveplate_crystal`
- 打卡表：`account_checkins`
  - 字段：`account_id / period_type / period_key / flag_key / is_done`
  - 唯一键：`(account_id, period_type, period_key, flag_key)`

服务启动时会自动执行兼容迁移：
- 旧账号字段自动重命名
- `account_daily_flags` 自动迁移为 `account_checkins`

## period_key 规则
- `daily`：`YYYY-MM-DD`
- `weekly`：`YYYY-MM-DDW`（该周周一日期 + `W`）
- `monthly`：`YYYY-MM`
- `fv`：`fv-YYYY-MM-DD`
- `hv`：`hv-YYYY-MM-DD`
- `four_week`：`YYYY-MM-DD_YYYY-MM-DD`（固定 28 天窗口）
- `range`：`YYYY-MM-DD_YYYY-MM-DD`（指定起止日期）

## 目录
- `backend/` FastAPI 服务
- `frontend/` Vue 页面
- `scripts/` 常用启动与重启脚本

## 本地开发

后端：
```bash
cd backend
cp .env.example .env
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8765
```

`.env` 示例：
```env
DATABASE_URL=postgresql://<user>:<password>@<host>:5432/<database>
APP_TZ=Asia/Shanghai
AUTH_BASE_URL=http://127.0.0.1:8080
AUTH_REQUIRED_PERMISSION=manage
```

鉴权说明：
- 后端会调用 `AUTH_BASE_URL/api/validate`
- 必须具备 `manage` 权限才能访问业务接口
- 前端请求会自动携带浏览器本地 token（`X-Token`），首次缺失会提示输入

前端：
```bash
cd frontend
npm install
npm run dev
```

默认前端请求 `/api`，如需直连后端：
```bash
VITE_API_BASE=http://127.0.0.1:8765 npm run dev
```

## 服务重启
```bash
./scripts/restart_services.sh
```

## 主要接口
- 账号
  - `POST /accounts`
  - `GET /accounts`
  - `POST /accounts/by-id/{id}/update`
  - `POST /accounts/by-id/{id}/delete`
- 体力
  - `GET /accounts/by-id/{id}/energy`
  - `POST /accounts/by-id/{id}/energy/set`
  - `POST /accounts/by-id/{id}/energy/spend`
  - `POST /accounts/by-id/{id}/energy/gain`
- 每日每周总览
  - `GET /dashboard/accounts`
  - `POST /accounts/by-id/{id}/daily-flags`（兼容）
  - `POST /accounts/by-id/{id}/checkins`（推荐）
- 周期活动
  - `GET /periodic/accounts`
