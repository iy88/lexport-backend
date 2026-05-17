# 律航出海 (LexPort) - 后端

基于 Flask 的 REST API 服务，为律航出海前端应用提供用户认证、法规库、资讯库等业务接口。

## 技术栈

| 组件 | 选型 |
|------|------|
| 语言 | Python 3.12 |
| 框架 | Flask 3.x |
| 数据库 | MySQL |
| ORM | SQLAlchemy (Flask-SQLAlchemy) |
| 认证 | JWT + bcrypt |
| 邮件 | Flask-Mail (SMTP) |
| 配置 | python-dotenv |

## 快速开始

```bash
cp .env.example .env   # 编辑 .env 填入数据库和 SMTP 配置
pip install -r requirements.txt
python run.py           # 默认监听 0.0.0.0:5000
```

## 项目结构

```
run.py                    # 入口
config.py                 # 配置类 (Dev / Prod / Test)，从环境变量读取
app/
  __init__.py             # create_app() 工厂函数，组装应用
  extensions.py           # SQLAlchemy、Mail 等扩展实例
  models/                 # 数据模型，一个文件对应一张表
  routes/                 # Blueprint 路由，按资源分组，有独立 URL 前缀
  services/               # 业务逻辑层，路由层只做 HTTP 解析和响应格式化
  utils/                  # 工具函数：校验、JWT、自定义异常
docs/
  db.md                   # 数据库表设计文档
  api.md                  # API 文档
```

## 架构设计

### App Factory

使用 `create_app()` 工厂函数创建 Flask 实例，便于在不同环境下注入不同配置，也方便测试。

### Service 层

路由 (`routes/`) 负责解析 HTTP 请求、调用 service、格式化 JSON 响应。所有业务逻辑（校验、数据库操作、邮件发送）集中在 `services/` 中，可以脱离 HTTP 上下文独立测试。

### Blueprint 路由

每个资源模块注册为一个 Blueprint，挂载独立 URL 前缀。例如：

- `/api/auth/*` → `routes/auth.py` (AuthBlueprint)

新增模块时只需创建对应的 Blueprint 并在 `routes/__init__.py` 中注册。

### 响应格式

所有接口采用统一 JSON 格式：

```json
// 成功
{ "success": true, "data": { ... }, "message": "..." }

// 失败
{ "success": false, "error": { "code": "...", "message": "..." } }
```

### JWT 设计

| 类型 | 用途 | 有效期 |
|------|------|--------|
| `access` | 登录会话 | 1 小时 |
| `verify_email` | 邮箱验证 | 30 分钟 |

JWT payload 中包含 `type` 字段，防止 token 类型混淆。

### 登录机制

- 单一 `login_id` 字段同时接受用户名和邮箱（通过是否含 `@` 判断）
- 认证失败时统一返回「用户名或密码错误」，不区分具体原因
- 邮箱可选，未提供邮箱的用户只能通过用户名登录

## API 文档

详见 [docs/api.md](docs/api.md)。

## 数据库设计

> 备份: `mysqldump --set-gtid-purged=OFF -u root -p lexport > initial.sql`
详见 [docs/db.md](docs/db.md)。
