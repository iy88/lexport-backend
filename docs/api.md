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

---

## 5. 法规列表

**GET** `/api/laws`

### 请求参数（Query）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `page` | int | 否 | 页码，默认 1 |
| `per_page` | int | 否 | 每页条数，默认 20 |
| `country_id` | string | 否 | 按国家筛选，如 `ZA` |
| `scene_id` | string | 否 | 按场景筛选，如 `labor` |
| `keyword` | string | 否 | 按标题模糊搜索 |

### 响应状态

| HTTP 状态码 | 说明 |
|-------------|------|
| 200 | 成功，返回法规列表和元数据 |

### 请求示例

```bash
curl "http://localhost:5000/api/laws?country_id=ZA&page=1&per_page=5"
```

### 响应示例（成功）

```json
{
    "success": true,
    "data": {
        "laws": [
            {
                "id": 1,
                "title": "南非海关管理法（修订版）",
                "country_id": "ZA",
                "scene_id": "customs",
                "level": "国家级",
                "penalty": "货物扣押 + 罚款20-50%货值",
                "effective_date": "2024-01-15",
                "summary": "制造业进口原材料需提前30天备案...",
                "full_text_url": null,
                "created_at": "2026-05-17T12:00:00"
            }
        ],
        "meta": {
            "page": 1,
            "per_page": 5,
            "total": 12,
            "countries": [
                {"id": "ZA", "name_zh": "南非"}
            ],
            "scenes": [
                {"id": "customs", "label_zh": "海关进出口"}
            ]
        }
    },
    "message": "成功"
}
```

---

## 6. 机构列表

**GET** `/api/agencies`

### 请求参数（Query）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `page` | int | 否 | 页码，默认 1 |
| `per_page` | int | 否 | 每页条数，默认 20 |
| `scene_id` | string | 否 | 按服务场景筛选，如 `law-labor` |
| `category_id` | string | 否 | 按机构大类筛选，如 `law`、`accounting` |
| `keyword` | string | 否 | 按机构名称或覆盖区域模糊搜索 |

### 响应状态

| HTTP 状态码 | 说明 |
|-------------|------|
| 200 | 成功，返回机构列表和元数据 |

### 请求示例

```bash
curl "http://localhost:5000/api/agencies?scene_id=law-labor&page=1&per_page=5"
```

### 响应示例（成功）

```json
{
    "success": true,
    "data": {
        "agencies": [
            {
                "id": 6,
                "name_zh": "Webber Wentzel",
                "scene_id": "law-labor",
                "region": "南非",
                "phone": "+27 10 800 3000",
                "email": "info@webberwentzel.com",
                "business": "劳工纠纷、罢工谈判、大规模用工合规",
                "advantage": "南非劳工法第一，服务大型制造企业",
                "highlight": "劳工第一",
                "sort_order": 0
            }
        ],
        "meta": {
            "page": 1,
            "per_page": 5,
            "total": 68,
            "categories": [
                {
                    "id": "law",
                    "label_zh": "律师事务所",
                    "icon_name": "Scale",
                    "scenes": [
                        {"id": "law-labor", "label_zh": "劳工用工 / 雇佣合规"}
                    ]
                }
            ]
        }
    },
    "message": "成功"
}
```

---

## 7. 资讯列表

**GET** `/api/news`

### 请求参数（Query）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `page` | int | 否 | 页码，默认 1 |
| `per_page` | int | 否 | 每页条数，默认 20 |
| `type` | string | 否 | 按类型筛选：`cooperation` / `hotspot` / `update` |
| `country_id` | string | 否 | 按国家筛选 |
| `keyword` | string | 否 | 按标题模糊搜索 |

### 响应状态

| HTTP 状态码 | 说明 |
|-------------|------|
| 200 | 成功，返回资讯列表和元数据 |

### 请求示例

```bash
curl "http://localhost:5000/api/news?type=hotspot&page=1&per_page=5"
```

### 响应示例（成功）

```json
{
    "success": true,
    "data": {
        "news": [
            {
                "id": 4,
                "type": "hotspot",
                "title": "南非数据跨境传输合规风波",
                "source": "合规追踪",
                "country_id": "ZA",
                "date": "2026-04-30",
                "summary": "南非信息监管机构对未履行数据跨境传输评估义务的企业开出罚单...",
                "risk_level": "high",
                "involved_laws": "南非数据保护法（POPIA）",
                "response": "立即注册信息官，完成数据跨境传输影响评估",
                "update_type": null,
                "change_desc": null,
                "impact": null,
                "advice": null,
                "tags": [
                    {"id": 7, "name_zh": "数据安全"},
                    {"id": 8, "name_zh": "行政处罚"}
                ],
                "created_at": "2026-05-17T12:00:00"
            }
        ],
        "meta": {
            "page": 1,
            "per_page": 5,
            "total": 9,
            "types": [
                {"value": "cooperation", "label_zh": "中非合作"},
                {"value": "hotspot", "label_zh": "合规热点"},
                {"value": "update", "label_zh": "法规更新"}
            ],
            "countries": [{"id": "ZA", "name_zh": "南非"}],
            "tags": [{"id": 7, "name_zh": "数据安全"}]
        }
    },
    "message": "成功"
}
```

---

## 8. 平台统计

**GET** `/api/stats`

实时统计各表行数（数据库 VIEW），无需参数。

### 响应状态

| HTTP 状态码 | 说明 |
|-------------|------|
| 200 | 成功，返回统计数值 |

### 请求示例

```bash
curl http://localhost:5000/api/stats
```

### 响应示例（成功）

```json
{
    "success": true,
    "data": {
        "stats": [
            {"id": "countries", "value": "8", "label_zh": "覆盖国家（持续拓展中）"},
            {"id": "laws", "value": "12", "label_zh": "法规条文收录"},
            {"id": "scenes", "value": "7", "label_zh": "高频合规场景"},
            {"id": "agencies", "value": "68", "label_zh": "合作合规机构"}
        ]
    },
    "message": "成功"
}
```

---

## 9. 后台管理

所有接口需携带 JWT。`{resource}` 可选值：`laws` / `news` / `agencies`。

`admin` 创建/更新直接生效（`published`），`editor` 创建/更新自动进入待审核（`draft`）。

---

### 列表

**GET** `/api/admin/{resource}?page=1&per_page=20&status=draft`

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `page` | int | 否 | 页码，默认 1 |
| `per_page` | int | 否 | 每页条数，默认 20 |
| `status` | string | 否 | `draft` 待审核 / `published` 已发布 / 不传返回全部 |

```bash
# 待审核列表
curl -H 'Authorization: Bearer {token}' \
  'http://localhost:5000/api/admin/laws?status=draft'

# 已发布列表
curl -H 'Authorization: Bearer {token}' \
  'http://localhost:5000/api/admin/news?status=published&page=1'
```

**响应：**
```json
{
    "success": true,
    "data": {
        "items": [
            {
                "id": 3,
                "title": "待审法规",
                "status": "draft",
                "created_at": "2026-05-17T12:00:00"
            }
        ],
        "meta": {"page": 1, "per_page": 20, "total": 1}
    },
    "message": "成功"
}
```

---

### 创建

**POST** `/api/admin/{resource}`

Body 为对应资源的字段（无需传 `status`，由 role 自动决定）。

```bash
# admin 创建（直接 published）
curl -X POST http://localhost:5000/api/admin/laws \
  -H 'Authorization: Bearer {admin_token}' \
  -H 'Content-Type: application/json' \
  -d '{"title":"新法规","country_id":"ZA","scene_id":"labor"}'

# editor 创建（自动 draft）
curl -X POST http://localhost:5000/api/admin/news \
  -H 'Authorization: Bearer {editor_token}' \
  -H 'Content-Type: application/json' \
  -d '{"type":"cooperation","title":"新资讯","date":"2026-05-01"}'
```

**admin 创建响应（201）：**
```json
{
    "success": true,
    "data": {
        "item": { "id": 12, "title": "新法规", "status": "published" }
    },
    "message": "创建成功"
}
```

**editor 创建响应（201）：**
```json
{
    "success": true,
    "data": {
        "item": { "id": 10, "type": "cooperation", "title": "新资讯", "status": "draft" }
    },
    "message": "创建成功"
}
```

---

### 详情

**GET** `/api/admin/{resource}/{id}`

```bash
curl -H 'Authorization: Bearer {token}' \
  http://localhost:5000/api/admin/laws/1
```

**响应：**
```json
{
    "success": true,
    "data": {
        "item": { "id": 1, "title": "南非海关法", "status": "published" }
    },
    "message": "成功"
}
```

---

### 更新

**PUT** `/api/admin/{resource}/{id}`

```bash
curl -X PUT http://localhost:5000/api/admin/laws/1 \
  -H 'Authorization: Bearer {admin_token}' \
  -H 'Content-Type: application/json' \
  -d '{"title":"修改后的标题"}'
```

**响应：**
```json
{
    "success": true,
    "data": {
        "item": { "id": 1, "title": "修改后的标题", "status": "published" }
    },
    "message": "更新成功"
}
```

---

### 删除（仅 admin）

**DELETE** `/api/admin/{resource}/{id}`

```bash
curl -X DELETE http://localhost:5000/api/admin/laws/1 \
  -H 'Authorization: Bearer {admin_token}'
```

**响应：**
```json
{ "success": true, "data": null, "message": "删除成功" }
```

**editor 调用（403）：**
```json
{ "success": false, "error": { "code": "AUTH_ERROR", "message": "权限不足" } }
```

---

### 审核通过（仅 admin）

**POST** `/api/admin/{resource}/{id}/approve`

```bash
curl -X POST http://localhost:5000/api/admin/news/10/approve \
  -H 'Authorization: Bearer {admin_token}'
```

**响应：**
```json
{
    "success": true,
    "data": {
        "item": { "id": 10, "status": "published" }
    },
    "message": "审核通过"
}
```

---

### 用户管理（仅 admin）

**GET** `/api/admin/users?page=1&per_page=20`

```bash
curl -H 'Authorization: Bearer {admin_token}' \
  http://localhost:5000/api/admin/users
```

**响应：**
```json
{
    "success": true,
    "data": {
        "items": [
            {
                "id": 1, "username": "admin", "email": "admin@lexport.cn",
                "email_verified": true, "role": "admin",
                "created_at": "2026-05-17T12:00:00"
            }
        ],
        "meta": { "page": 1, "per_page": 20, "total": 1 }
    },
    "message": "成功"
}
```

**PUT** `/api/admin/users/{id}` — 修改角色（不能改管理员）

```bash
curl -X PUT http://localhost:5000/api/admin/users/2 \
  -H 'Authorization: Bearer {admin_token}' \
  -H 'Content-Type: application/json' \
  -d '{"role":"editor"}'
```

**响应：**
```json
{
    "success": true,
    "data": { "item": { "id": 2, "username": "editor1", "role": "editor" } },
    "message": "更新成功"
}
```

**修改管理员（403）：**
```json
{ "success": false, "error": { "code": "AUTH_ERROR", "message": "不能修改管理员权限" } }
```

### 响应状态汇总

| HTTP 状态码 | 错误码 | 说明 |
|-------------|--------|------|
| 201 | - | 创建成功 |
| 200 | - | 操作成功 |
| 400 | `VALIDATION_ERROR` | 参数不合法 |
| 401 | `AUTH_ERROR` | 未登录或 token 无效 |
| 403 | `AUTH_ERROR` | 权限不足 |
| 404 | `NOT_FOUND` | 记录不存在 |
