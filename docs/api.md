# API 文档

## 响应格式

所有接口统一返回 JSON，格式如下：

**成功响应：**
```json
{
    "success": true,
    "data": { ... },
    "message": "操作成功"
}
```

**错误响应：**
```json
{
    "success": false,
    "error": {
        "code": "ERROR_CODE",
        "message": "错误描述"
    }
}
```

---

## 1. 注册

**POST** `/api/auth/register`

### 请求参数

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `username` | string | 是 | 用户名，3-50 位字母、数字或下划线 |
| `password` | string | 是 | 密码，不少于 8 位，需包含字母和数字 |
| `email` | string | 否 | 邮箱地址 |

### 响应状态

| HTTP 状态码 | 错误码 | 消息 | 说明 |
|-------------|--------|------|------|
| 201 | - | 注册成功 | 注册成功，返回用户信息和 JWT |
| 400 | `VALIDATION_ERROR` | 用户名需为3-50位字母、数字或下划线 | 用户名格式不合法 |
| 400 | `VALIDATION_ERROR` | 密码长度不少于8位 | 密码过短 |
| 400 | `VALIDATION_ERROR` | 密码需包含字母 | 密码缺少字母 |
| 400 | `VALIDATION_ERROR` | 密码需包含数字 | 密码缺少数字 |
| 400 | `VALIDATION_ERROR` | 请输入正确的邮箱格式 | 邮箱格式不合法 |
| 409 | `CONFLICT` | 用户名已被注册 | 用户名重复 |
| 409 | `CONFLICT` | 邮箱已被注册 | 邮箱重复 |

### 请求示例

```bash
curl -X POST http://localhost:5000/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"username":"testuser","password":"Abc12345","email":"test@example.com"}'
```

### 响应示例（成功）

```json
{
    "success": true,
    "data": {
        "user": {
            "id": 1,
            "username": "testuser",
            "email": "test@example.com",
            "email_verified": false,
            "role": "user",
            "created_at": "2026-05-17T12:00:00"
        },
        "access_token": "eyJhbGciOiJIUzI1NiIs..."
    },
    "message": "注册成功"
}
```

### 响应示例（失败）

```json
{
    "success": false,
    "error": {
        "code": "CONFLICT",
        "message": "用户名已被注册"
    }
}
```

---

## 2. 登录

**POST** `/api/auth/login`

### 请求参数

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `login_id` | string | 是 | 用户名或邮箱 |
| `password` | string | 是 | 密码 |

### 响应状态

| HTTP 状态码 | 错误码 | 消息 | 说明 |
|-------------|--------|------|------|
| 200 | - | 登录成功 | 登录成功，返回用户信息和 JWT |
| 400 | `VALIDATION_ERROR` | 请填写登录账号和密码 | 缺少必填字段 |
| 401 | `AUTH_ERROR` | 用户名或密码错误 | 用户不存在或密码错误 |

### 请求示例

```bash
# 用户名登录
curl -X POST http://localhost:5000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"login_id":"testuser","password":"Abc12345"}'

# 邮箱登录
curl -X POST http://localhost:5000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"login_id":"test@example.com","password":"Abc12345"}'
```

### 响应示例（成功）

```json
{
    "success": true,
    "data": {
        "user": {
            "id": 1,
            "username": "testuser",
            "email": "test@example.com",
            "email_verified": true,
            "role": "user",
            "created_at": "2026-05-17T12:00:00"
        },
        "access_token": "eyJhbGciOiJIUzI1NiIs..."
    },
    "message": "登录成功"
}
```

---

## 3. 邮箱验证

用户点击邮件中的验证链接（格式：`{FRONTEND_URL}/verify-email/{token}`），前端页面提取路径中的 token 后调用此接口。

**POST** `/api/auth/verify-email`

### 请求参数

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `token` | string | 是 | 注册时通过邮件发送的验证 JWT |

### 响应状态

| HTTP 状态码 | 错误码 | 消息 | 说明 |
|-------------|--------|------|------|
| 200 | - | 邮箱验证成功 | 验证成功，邮箱标记为已验证 |
| 400 | `VALIDATION_ERROR` | 缺少验证令牌 | 未提供 token 参数 |
| 400 | `VALIDATION_ERROR` | 验证链接已过期 | JWT 已过期（30 分钟时限） |
| 400 | `VALIDATION_ERROR` | 无效的验证令牌 | JWT 解析失败或类型不匹配 |
| 404 | `NOT_FOUND` | 用户不存在 | 用户已被删除 |

### 请求示例

```bash
curl -X POST http://localhost:5000/api/auth/verify-email \
  -H 'Content-Type: application/json' \
  -d '{"token":"eyJhbGciOiJIUzI1NiIs..."}'
```

### 响应示例（成功）

```json
{
    "success": true,
    "data": null,
    "message": "邮箱验证成功"
}
```

---

## 4. 当前用户信息

需要携带 JWT access token。

**GET** `/api/user/profile`

### 请求头

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `Authorization` | string | 是 | `Bearer {access_token}` |

### 响应状态

| HTTP 状态码 | 错误码 | 消息 | 说明 |
|-------------|--------|------|------|
| 200 | - | 成功 | 返回当前用户信息 |
| 401 | `AUTH_ERROR` | 缺少认证令牌 | 未提供 Authorization 头 |
| 401 | `AUTH_ERROR` | 认证令牌已过期 | JWT 过期 |
| 401 | `AUTH_ERROR` | 无效的认证令牌 | JWT 解析失败 |
| 401 | `AUTH_ERROR` | 用户不存在 | 用户已删除 |

### 请求示例

```bash
curl -X GET http://localhost:5000/api/user/profile \
  -H 'Authorization: Bearer eyJhbGciOiJIUzI1NiIs...'
```

### 响应示例（成功）

```json
{
    "success": true,
    "data": {
        "user": {
            "id": 1,
            "username": "testuser",
            "email": "test@example.com",
            "email_verified": true,
            "role": "user",
            "created_at": "2026-05-17T12:00:00"
        }
    },
    "message": "成功"
}
```
