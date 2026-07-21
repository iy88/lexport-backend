# 律航出海 (LexPort) - 后端

基于 Flask 的 REST API 服务，为律航出海前端应用提供用户认证、法规库、资讯库、合规报告生成等业务接口。

## 技术栈

| 组件    | 选型                            |
|-------|-------------------------------|
| 语言    | Python 3.12                   |
| 框架    | Flask 3.x                     |
| 数据库   | MySQL                         |
| ORM   | SQLAlchemy (Flask-SQLAlchemy) |
| 认证    | JWT + bcrypt                  |
| 邮件    | Flask-Mail (SMTP)             |
| 对象存储  | Alibaba Cloud OSS             |
| AI 平台 | 百炼 (Bailian)                  |
| 任务队列  | Celery + Redis                |
| 配置    | python-dotenv                 |

## 快速开始

```bash
# 1. 克隆项目
git clone <repo-url> && cd lexport-backend

# 2. 创建虚拟环境
python -m venv .venv && source .venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env   # 编辑 .env 填入各项配置（详见下方配置说明）

# 5. 初始化数据库（首次运行自动建表）
python run.py           # 默认监听 0.0.0.0:6768
```

## 环境变量配置

编辑 `.env` 文件，所有配置项说明如下：

### 基础配置

| 变量名          | 必填 | 默认值          | 说明        |
|---------------|----|--------------|-----------|
| `FLASK_ENV`   | 否  | `development` | 运行环境      |
| `SECRET_KEY`  | 是  | -            | Flask 密钥  |
| `FRONTEND_URL` | 否  | `https://lexport.cn` | 前端地址（用于邮件链接） |

### JWT

| 变量名                          | 必填 | 默认值    | 说明               |
|-------------------------------|----|--------|------------------|
| `JWT_SECRET_KEY`              | 是  | -      | JWT 签名密钥         |
| `JWT_ACCESS_TOKEN_EXPIRES`    | 否  | `3600` | access token 有效期（秒） |
| `JWT_VERIFY_TOKEN_EXPIRES`    | 否  | `1800` | 邮箱验证 token 有效期（秒） |

### MySQL 数据库

| 变量名          | 必填 | 默认值       | 说明     |
|---------------|----|-----------|--------|
| `DB_HOST`     | 否  | `127.0.0.1` | 数据库主机  |
| `DB_PORT`     | 否  | `3306`    | 数据库端口  |
| `DB_NAME`     | 否  | `lexport` | 数据库名   |
| `DB_USER`     | 否  | `root`    | 数据库用户  |
| `DB_PASSWORD` | 否  | (空)       | 数据库密码  |

### 邮件 (SMTP)

| 变量名                   | 必填 | 默认值                         | 说明                          |
|------------------------|----|-----------------------------|-----------------------------|
| `MAIL_SERVER`          | 否  | `smtp.example.com`          | SMTP 服务器                    |
| `MAIL_PORT`            | 否  | `587`                       | SMTP 端口（587=TLS, 465=SSL）   |
| `MAIL_USE_TLS`         | 否  | `true`                      | 启用 TLS                      |
| `MAIL_USE_SSL`         | 否  | `false`                     | 启用 SSL                      |
| `MAIL_USERNAME`        | 否  | (空)                         | SMTP 用户名                    |
| `MAIL_PASSWORD`        | 否  | (空)                         | SMTP 密码                     |
| `MAIL_DEFAULT_SENDER`  | 否  | `LexPort <noreply@lexport.cn>` | 默认发件人                       |

### 文件上传

| 变量名          | 必填 | 默认值        | 说明               |
|---------------|----|------------|------------------|
| `UPLOAD_PATH` | 否  | `./uploads` | 文件存储目录（自动转为绝对路径） |

### Alibaba Cloud OSS

> 合规报告附件使用 `OSS_BUCKET_NAME`，法律原件使用独立的 `LAW_OSS_BUCKET_NAME` 知识库 Bucket。
> 需要 RAM 用户具有 OSS 读写权限。

| 变量名                                | 必填 | 默认值                                           | 说明               |
|-------------------------------------|----|-----------------------------------------------|------------------|
| `ALIBABA_CLOUD_ACCESS_KEY_ID`       | 是  | (空)                                           | RAM 用户 AccessKey |
| `ALIBABA_CLOUD_ACCESS_KEY_SECRET`   | 是  | (空)                                           | RAM 用户 Secret    |
| `OSS_REGION`                        | 否  | `cn-beijing`                                  | OSS 地域           |
| `OSS_ENDPOINT`                      | 否  | `https://oss-cn-beijing.aliyuncs.com`         | OSS Endpoint     |
| `OSS_BUCKET_NAME`                   | 是  | (空)                                           | 合规报告附件 Bucket   |
| `LAW_OSS_BUCKET_NAME`               | 是  | (空)                                           | 法律知识库 Bucket     |
| `OSS_SIGN_URL_EXPIRES`              | 否  | `7200`                                        | 签名 URL 有效期（秒）    |

### 百炼 (Bailian) AI 平台

| 变量名                      | 必填 | 默认值                                                          | 说明       |
|---------------------------|----|--------------------------------------------------------------|----------|
| `BAILIAN_API_KEY`         | 是  | (空)                                                          | API Key  |
| `BAILIAN_BASE_URL`        | 否  | `https://dashscope.aliyuncs.com`                             | 百炼 API 根地址或完整应用地址 |
| `REPORT_GENERATOR_APPID`  | 是  | (空)                                                          | 报告生成应用 ID |
| `REPORT_AI_VERSION`       | 是  | (空)                                                          | 写入报告元数据的 AI 版本 |
| `REPORT_DATA_CUTOFF_DATE` | 是  | (空)                                                          | 写入报告及数据来源说明的截止日期 |

### Redis / Celery

| 变量名                            | 必填 | 默认值                        | 说明                |
|---------------------------------|----|----------------------------|-------------------|
| `REDIS_URL`                     | 否  | `redis://127.0.0.1:6379/0` | Redis 连接地址（Broker） |
| `REPORT_POLL_INTERVAL_SECONDS`  | 否  | `10`                       | 报告轮询间隔（秒）         |
| `REPORT_TASK_TIMEOUT_SECONDS`   | 否  | `7200`                     | 报告任务超时时间（秒）       |
| `CELERY_AUTO_START`             | 否  | `false`                    | 开发环境随 Flask 启停 worker/beat |
| `CELERY_AUTO_STARTUP_GRACE_SECONDS` | 否 | `1.0`                    | 子进程启动失败检查等待时间（秒） |

## 启动服务

### Flask API

```bash
python run.py                    # 开发模式，监听 0.0.0.0:6768
```

> 默认使用 `FLASK_ENV=development` 配置，可通过环境变量切换：`FLASK_ENV=production python run.py`。

### Celery 启动

以下四种启动方式任选其一。

#### 自动启停（推荐开发用）

在 `.env` 中设置 `CELERY_AUTO_START=true`，`python run.py` 会自动在后台拉起 Worker + Beat，并注册 `atexit` 和信号处理器。Ctrl+C 停止 Flask 时自动终止 Celery 子进程。

```bash
# .env
CELERY_AUTO_START=true

# 一行启动全部
python run.py
```

```
[celery-runner] worker started  (pid=12345)
[celery-runner] beat started    (pid=12346)
 * Serving Flask app ...
```

> 原理：`app/utils/celery_runner.py` 使用独立进程组启动 Celery，启动后检查子进程是否立即退出；Flask 退出时按进程组发送 TERM，超时后发送 KILL。

#### 开发环境 — 多终端

```bash
# 终端 1: Flask API
python run.py

# 终端 2: Celery Worker（执行轮询任务）
celery -A celery_app:celery_app worker --loglevel=INFO

# 终端 3: Celery Beat（定时调度，只需一个实例）
celery -A celery_app:celery_app beat --loglevel=INFO
```

#### 开发环境 — 单终端后台运行

```bash
# Worker 后台运行，日志写入文件
celery -A celery_app:celery_app worker --loglevel=INFO --logfile=./logs/worker.log --pidfile=./logs/worker.pid --detach

# Beat 后台运行
celery -A celery_app:celery_app beat --loglevel=INFO --logfile=./logs/beat.log --pidfile=./logs/beat.pid --detach
```

> 首次运行前确保 `./logs/` 目录存在：`mkdir -p logs`

#### 生产环境 — Supervisor

```ini
[program:lexport-api]
command=/path/to/.venv/bin/python run.py
directory=/path/to/lexport-backend
environment=FLASK_ENV=production
autostart=true
autorestart=true
stderr_logfile=/var/log/lexport/api.err.log
stdout_logfile=/var/log/lexport/api.out.log

[program:lexport-worker]
command=/path/to/.venv/bin/celery -A celery_app:celery_app worker --loglevel=WARNING --concurrency=2
directory=/path/to/lexport-backend
autostart=true
autorestart=true
stderr_logfile=/var/log/lexport/worker.err.log
stdout_logfile=/var/log/lexport/worker.out.log
stopwaitsecs=30
stopsignal=TERM

[program:lexport-beat]
command=/path/to/.venv/bin/celery -A celery_app:celery_app beat --loglevel=WARNING
directory=/path/to/lexport-backend
autostart=true
autorestart=true
stderr_logfile=/var/log/lexport/beat.err.log
stdout_logfile=/var/log/lexport/beat.out.log
stopwaitsecs=10
stopsignal=TERM
```

### Celery 停止

| 场景 | 命令 |
|------|------|
| 前台运行 | `Ctrl+C`（等待正在执行的任务完成，约 2-5 秒） |
| 后台运行（detach） | `kill -TERM $(cat ./logs/worker.pid)` |
| 强制立即终止 | `kill -KILL $(cat ./logs/worker.pid)` |
| Supervisor | `supervisorctl stop lexport-worker lexport-beat` |

> `--pidfile` 指定的文件记录了进程 PID，停止时直接读取即可。Worker 收到 `TERM` 信号后会等待当前任务完成再退出（默认 `stopwaitsecs` 内完成）。

### Celery 常用管理命令

```bash
# 查看 Worker 状态
celery -A celery_app:celery_app status

# 查看已注册任务
celery -A celery_app:celery_app inspect registered

# 查看活跃任务
celery -A celery_app:celery_app inspect active

# 查看调度中的 Beat 任务
celery -A celery_app:celery_app inspect scheduled

# Worker 重启后重新处理未确认任务
celery -A celery_app:celery_app worker --loglevel=INFO -E
```

### Celery 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| Beat 不触发轮询 | `beat_schedule` 未加载 | 确认 `celery_app.py` 中 `beat_schedule` 配置正确 |
| 多个 Worker 重复轮询 | Redis 锁未获取 | 正常行为 — 只有一个 Worker 获取锁，其余跳过 |
| Worker 启动报 `ModuleNotFoundError` | 未在项目根目录启动 | `cd` 到 `lexport-backend/` 后再执行 celery 命令 |
| 任务一直 `in_progress` | 百炼未返回终态 | 超过 2 小时自动标记 `failed`（由 `REPORT_TASK_TIMEOUT_SECONDS` 控制） |
| Redis 连接失败 | Redis 未启动或 URL 错误 | 检查 `REDIS_URL` 配置，确认 `redis-server` 正在运行 |
| Beat 报 `beat_schedule_pidfile` 冲突 | 已有 Beat 进程运行 | `kill $(cat ./logs/beat.pid)` 或删除 pid 文件 |

## 项目结构

```
run.py                    # 入口
config.py                 # 配置类 (Dev / Prod / Test + CeleryConfig)，从环境变量读取
celery_app.py             # Celery 应用定义 + Beat 调度配置
app/
  __init__.py             # create_app() 工厂函数，组装应用
  extensions.py           # SQLAlchemy、Mail 等扩展实例
  models/                 # 数据模型，一个文件对应一张表
  routes/                 # Blueprint 路由，按资源分组，有独立 URL 前缀
  services/               # 业务逻辑层，路由层只做 HTTP 解析和响应格式化
  tasks/                  # Celery 异步任务（轮询合规报告状态等）
  utils/                  # 工具函数：校验、JWT、OSS、自定义异常
docs/
  db.md                   # 数据库表设计文档
  api.md                  # API 文档
  PLAN.md                 # 合规报告异步生成设计文档
bits/                     # 随手脚本（OSS 测试、种子数据、悬垂文件检查等）
sql/                      # 数据库备份 SQL
```

## 架构设计

### App Factory

使用 `create_app()` 工厂函数创建 Flask 实例，便于在不同环境下注入不同配置，也方便测试。

### Service 层

路由 (`routes/`) 负责解析 HTTP 请求、调用 service、格式化 JSON 响应。所有业务逻辑（校验、数据库操作、OSS 上传、百炼调用）集中在
`services/` 中，可以脱离 HTTP 上下文独立测试。

### Blueprint 路由

每个资源模块注册为一个 Blueprint，挂载独立 URL 前缀：

| URL 前缀                     | Blueprint 文件            | 说明        |
|-----------------------------|--------------------------|-----------|
| `/api/auth/*`               | `routes/auth.py`         | 注册、登录、验证  |
| `/api/user/*`               | `routes/user.py`         | 用户信息      |
| `/api/laws/*`               | `routes/law.py`          | 法规库（公开）   |
| `/api/agencies/*`           | `routes/agency.py`       | 机构推荐（公开）  |
| `/api/news/*`               | `routes/news.py`         | 资讯库（公开）   |
| `/api/stats/*`              | `routes/stat.py`         | 平台统计（公开）  |
| `/api/admin/*`              | `routes/admin.py`        | 后台管理      |
| `/api/compliance-reports/*` | `routes/compliance.py`   | 合规报告      |

新增模块时只需创建对应的 Blueprint 并在 `routes/__init__.py` 中注册。

### 响应格式

所有接口采用统一 JSON 格式：

成功响应：

```json
{ "success": true, "data": { ... }, "message": "..." }
```

失败响应：

```json
{ "success": false, "error": { "code": "...", "message": "..." } }
```

### JWT 设计

| 类型             | 用途   | 有效期   |
|----------------|------|-------|
| `access`       | 登录会话 | 1 天   |
| `verify_email` | 邮箱验证 | 30 分钟 |

JWT payload 中包含 `type` 字段，防止 token 类型混淆。

### 登录机制

- 单一 `login_id` 字段同时接受用户名和邮箱（通过是否含 `@` 判断）
- 认证失败时统一返回「用户名或密码错误」，不区分具体原因
- 邮箱可选，未提供邮箱的用户只能通过用户名登录

### 合规报告异步流程

```
POST /api/compliance-reports (表单 + 可选文件)
  │
  ├─ 文件保存到本地 tmp → 逐一上传 OSS → 生成签名 URL
  ├─ 查询匹配机构 (Agency.region.contains)
  ├─ 调用百炼 responses.create(background=True) → 获得 task_id
  └─ 写入 DiagnosisRecord (status=in_progress) → 返回 202

Celery Beat (每 10s)
  └─ poll_reports task
       ├─ Redis 所有权锁（防重复）
       ├─ 扫描 in_progress 记录
       ├─ 调用百炼 responses.retrieve(task_id)
       ├─ completed → 写入 DiagnosisResult (同一事务)
       ├─ failed/cancelled → 标记失败
       └─ 超过 2h → 自动标记 failed

GET /api/compliance-reports/{id}
  └─ completed → 返回 result_text；否则 result_text=null

DELETE /api/compliance-reports/{id}
  └─ 用户删除本人报告；管理员删除任意报告（均为软删除）
```

报告完成写库前，服务会解析百炼返回的 JSON，并替换前端报告模板中的
`{{REPORT_ID}}`、`{{GENERATED_AT}}`、`{{AI_VERSION}}` 和
`{{DATA_CUTOFF_DATE}}`。报告编号由记录 ID 确定性生成，完成时间使用百炼
`completed_at` 并格式化为 Asia/Shanghai ISO 时间。
若 `output_text` 不是合法 JSON，或缺少前端 schema 要求的四个报告元数据字段，
记录会标记为 `failed`，且不会创建结果记录。
软删除后的报告不会出现在普通用户列表和详情中，但管理员仍可查看记录及其结果。

## API 文档

详见 [docs/api.md](docs/api.md)。

## 数据库设计

> 备份: `mysqldump --set-gtid-purged=OFF -u root -p lexport > sql/bkup.sql`
> 详见 [docs/db.md](docs/db.md)。
