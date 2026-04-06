# 鸣潮账号管理系统

用于管理多个鸣潮账号的体力、每日每周打卡、周期活动状态、清日常计时，以及可复用的周期任务模板。

## 技术栈

- 前端：Vue 3 + Vue Router + Vite
- 后端：Go + `net/http` + `database/sql` + `pgx` + PostgreSQL
- 部署：systemd + Nginx

## 功能概览

### `每日每周总览`

- 账号体力、溢出结晶、满体力时间、下次恢复倒计时
- 快捷体力操作：`+40 / +60 / -40 / -60`
- 支持直接修改当前体力、当前结晶，或按目标满体力时间反推
- 无音区目标记录：`爱弥斯 / 西格莉卡 / 旧暗 / 旧雷 / 达妮娅`
- 每日每周检查项：`日常 / 聚落 / 门扉 / 周本 / 定向合成`
- 清日常计时：支持开始/暂停，并在总览页直接展示累计时长

### `周期活动`

- 每版本：`终焉矩阵 / 小珊瑚兑换 / 全息挑战 / 声骸模板`
- 每半版本：`角色试用`
- 每月：`深塔兑换所`
- 每四周：`深塔 / 海墟`
- 限时活动：`填方块 / 音游`
- 检查项状态支持三态切换：`todo / done / skipped`

### `清日常计时明细`

- 查看近 `7 / 14 / 30` 天统计
- 按天汇总总时长
- 按账号汇总总时长
- 查看所有计时明细
- 支持手动补录：
  - 按时长补录
  - 按起止时间补录

### `周期任务`

- 管理任务模板：`daily / weekly / version / half_version / special`
- 按 `period_key` 批量生成当前周期任务实例
- 查询任务实例并更新状态：`todo / done / skipped`

### `账号管理`

- 新建、编辑、删除账号
- 手机号默认掩码显示，支持复制完整号码
- 支持账号启停状态管理

## 体力规则

- 当前体力范围：`0 ~ 240`
- 体力恢复速度：每 `6` 分钟 `+1`
- 到达 `240` 后开始恢复体力结晶：每 `12` 分钟 `+1`
- 体力结晶上限：`480`

## 数据模型

- `accounts`
  - 核心字段：`account_id / id / abbr / nickname / phone_number / remark / tacet / is_active`
  - 体力字段：`full_waveplate_at / full_waveplate_crystal`
- `account_checkins`
  - 字段：`account_id / status_date / period_type / period_key / flag_key / status / is_done`
  - 唯一键：`(account_id, period_type, period_key, flag_key)`
- `account_cleanup_sessions`
  - 字段：`account_id / biz_date / started_at / ended_at / duration_sec / status`
- `task_templates`
  - 字段：`name / task_type / default_priority / description / is_active`
- `task_instances`
  - 字段：`account_id / template_id / period_key / status / start_at / deadline_at / priority / note`
  - 唯一键：`(account_id, template_id, period_key)`

服务启动时会自动补齐当前版本依赖的表和列，并统一检查项状态字段。

## `period_key` 规则

- `daily`：`YYYY-MM-DD`
- `weekly`：`YYYY-MM-DDW`，其中日期为该业务周周一
- `monthly`：`YYYY-MM`
- `fv`：`fv-YYYY-MM-DD`
- `hv`：`hv-YYYY-MM-DD`
- `four_week`：`YYYY-MM-DD_YYYY-MM-DD`
- `range`：`YYYY-MM-DD_YYYY-MM-DD`

## 环境变量

后端使用 [backend/.env.example](backend/.env.example) 作为基础配置：

```env
DATABASE_URL=postgresql://<user>:<password>@<host>:5432/<database>
APP_TZ=Asia/Shanghai
RESET_HOUR=4
AUTH_BASE_URL=http://127.0.0.1:8080
AUTH_REQUIRED_PERMISSION=manage
AUTH_VALIDATE_TIMEOUT_SECONDS=3
FOUR_WEEK_TOWER_ANCHOR=2026-03-30
FOUR_WEEK_RUINS_ANCHOR=2026-03-16
CURRENT_FV_START=2026-03-26
CURRENT_HV_START=2026-03-26
```

说明：

- `RESET_HOUR`：业务日切换时间，默认凌晨 `4` 点
- `FOUR_WEEK_*_ANCHOR`：四周周期锚点
- `CURRENT_FV_START`：当前整版本起始日
- `CURRENT_HV_START`：当前半版本起始日

## 鉴权

- 除 `/healthz` 外，其余接口都要求带 token
- 后端会调用 `AUTH_BASE_URL/api/validate`
- 必须具备 `AUTH_REQUIRED_PERMISSION` 指定权限，默认 `manage`
- 前端默认将 token 存在浏览器本地存储，使用请求头 `X-Token`
- 也支持 `Authorization: Bearer <token>`

## 目录结构

- `backend/cmd/server`：Go 服务入口
- `backend/internal/app`：Go 业务逻辑、HTTP 路由、迁移与测试
- `frontend/`：Vue 前端源码
- `scripts/`：构建、启动与服务重启脚本
- `deploy/nginx/`：Nginx 配置

## 本地开发

### 后端

```bash
cd backend
cp .env.example .env
go run ./cmd/server 8765
```

也可以先构建再运行：

```bash
./scripts/build_backend.sh
./scripts/start_backend.sh
```

服务默认监听 `8765` 端口，并同时兼容 `/api/*` 前缀。

### 后端测试

```bash
cd backend
go test ./...
```

### 后端构建产物

- `scripts/build_backend.sh` 会在 `backend/` 目录执行 `go build`
- 输出文件为 `backend/bin/wuwa-mgt-backend`
- `backend/bin/` 只是本地构建产物目录，不纳入版本控制
- `scripts/start_backend.sh` 直接启动这个二进制
- `scripts/restart_services.sh` 会先重新构建后端，再重启 `wuwa-mgt-backend.service`

因此只要改了 Go 后端代码，生产更新流程就是：

```bash
./scripts/restart_services.sh
```

### 前端开发

```bash
cd frontend
npm install
npm run dev
```

默认前端请求 `/api`。如需直连后端：

```bash
VITE_API_BASE=http://127.0.0.1:8765 npm run dev
```

### 前端构建产物

生产启动脚本 [scripts/start_frontend.sh](scripts/start_frontend.sh) 不运行 Vite dev server，而是：

- 读取 `frontend/dist`
- 在本机 `3001` 端口启动静态文件服务
- 将 `/api/*` 代理到 `http://127.0.0.1:8765`

因此更新前端后需要先构建：

```bash
cd frontend
npm run build
```

## 服务重启

```bash
./scripts/restart_services.sh
```

该脚本会：

- 重启 `wuwa-mgt-backend.service`
- 重启 `wuwa-mgt-frontend.service`
- 检查后端 `http://127.0.0.1:8765/healthz`
- 检查前端 `http://127.0.0.1:3001/`

## 主要接口

### 健康检查与鉴权

- `GET /healthz`
- `GET /auth/ping`

### 账号

- `POST /accounts`
- `GET /accounts`
- `GET /accounts/by-id/{id}`
- `PATCH /accounts/{account_id}`
- `POST /accounts/by-id/{id}/update`
- `POST /accounts/by-id/{id}/delete`

### 体力

- `GET /accounts/by-id/{id}/energy`
- `POST /accounts/by-id/{id}/energy/set`
- `POST /accounts/by-id/{id}/energy/spend`
- `POST /accounts/by-id/{id}/energy/gain`

### 每日每周与周期活动

- `GET /dashboard/accounts`
- `GET /periodic/accounts`
- `POST /accounts/by-id/{id}/checkins`
- `POST /accounts/by-id/{id}/tacet`

### 清日常计时

- `POST /accounts/by-id/{id}/cleanup-timer/start`
- `POST /accounts/by-id/{id}/cleanup-timer/pause`
- `GET /accounts/by-id/{id}/cleanup-timer/today`
- `GET /cleanup-timer/weekly-summary`
- `GET /cleanup-timer/sessions`
- `POST /cleanup-timer/sessions/manual`
- `DELETE /cleanup-timer/sessions/{session_id}`

### 周期任务

- `POST /task-templates`
- `GET /task-templates`
- `PATCH /task-templates/{template_id}`
- `POST /task-instances`
- `GET /task-instances`
- `PATCH /task-instances/{instance_id}`
- `POST /task-instances/generate`
