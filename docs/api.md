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

| 字段         | 类型     | 必填 | 说明                  |
|------------|--------|----|---------------------|
| `username` | string | 是  | 用户名，3-50 位字母、数字或下划线 |
| `password` | string | 是  | 密码，不少于 8 位，需包含字母和数字 |
| `email`    | string | 否  | 邮箱地址                |

### 响应状态

| HTTP 状态码 | 错误码                | 消息                  | 说明               |
|----------|--------------------|---------------------|------------------|
| 201      | -                  | 注册成功                | 注册成功，返回用户信息和 JWT |
| 400      | `VALIDATION_ERROR` | 用户名需为3-50位字母、数字或下划线 | 用户名格式不合法         |
| 400      | `VALIDATION_ERROR` | 密码长度不少于8位           | 密码过短             |
| 400      | `VALIDATION_ERROR` | 密码需包含字母             | 密码缺少字母           |
| 400      | `VALIDATION_ERROR` | 密码需包含数字             | 密码缺少数字           |
| 400      | `VALIDATION_ERROR` | 请输入正确的邮箱格式          | 邮箱格式不合法          |
| 409      | `CONFLICT`         | 用户名已被注册             | 用户名重复            |
| 409      | `CONFLICT`         | 邮箱已被注册              | 邮箱重复             |

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

| 字段         | 类型     | 必填 | 说明     |
|------------|--------|----|--------|
| `login_id` | string | 是  | 用户名或邮箱 |
| `password` | string | 是  | 密码     |

### 响应状态

| HTTP 状态码 | 错误码                | 消息         | 说明               |
|----------|--------------------|------------|------------------|
| 200      | -                  | 登录成功       | 登录成功，返回用户信息和 JWT |
| 400      | `VALIDATION_ERROR` | 请填写登录账号和密码 | 缺少必填字段           |
| 401      | `AUTH_ERROR`       | 用户名或密码错误   | 用户不存在或密码错误       |

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

| 字段      | 类型     | 必填 | 说明               |
|---------|--------|----|------------------|
| `token` | string | 是  | 注册时通过邮件发送的验证 JWT |

### 响应状态

| HTTP 状态码 | 错误码                | 消息      | 说明               |
|----------|--------------------|---------|------------------|
| 200      | -                  | 邮箱验证成功  | 验证成功，邮箱标记为已验证    |
| 400      | `VALIDATION_ERROR` | 缺少验证令牌  | 未提供 token 参数     |
| 400      | `VALIDATION_ERROR` | 验证链接已过期 | JWT 已过期（30 分钟时限） |
| 400      | `VALIDATION_ERROR` | 无效的验证令牌 | JWT 解析失败或类型不匹配   |
| 404      | `NOT_FOUND`        | 用户不存在   | 用户已被删除           |

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

| 字段              | 类型     | 必填 | 说明                      |
|-----------------|--------|----|-------------------------|
| `Authorization` | string | 是  | `Bearer {access_token}` |

### 响应状态

| HTTP 状态码 | 错误码          | 消息      | 说明                  |
|----------|--------------|---------|---------------------|
| 200      | -            | 成功      | 返回当前用户信息            |
| 401      | `AUTH_ERROR` | 缺少认证令牌  | 未提供 Authorization 头 |
| 401      | `AUTH_ERROR` | 认证令牌已过期 | JWT 过期              |
| 401      | `AUTH_ERROR` | 无效的认证令牌 | JWT 解析失败            |
| 401      | `AUTH_ERROR` | 用户不存在   | 用户已删除               |

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

| 字段           | 类型     | 必填 | 说明              |
|--------------|--------|----|-----------------|
| `page`       | int    | 否  | 页码，默认 1         |
| `per_page`   | int    | 否  | 每页条数，默认 20      |
| `country_id` | string | 否  | 按国家筛选，如 `ZA`    |
| `scene_id`   | string | 否  | 按场景筛选，如 `labor` |
| `keyword`    | string | 否  | 按中英文标题模糊搜索                |

### 响应状态

| HTTP 状态码 | 说明            |
|----------|---------------|
| 200      | 成功，返回法规列表和元数据 |

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
                "title_cn": "南非海关管理法（修订版）",
                "title_en": null,
                "law_number": null,
                "country_id": "ZA",
                "scene_id": "customs",
                "effective_date": "2024-01-15",
                "summary": "制造业进口原材料需提前30天备案...",
                "has_file": true,
                "created_at": "2026-05-17T12:00:00"
            }
        ],
        "meta": {
            "page": 1,
            "per_page": 5,
            "total": 12,
            "countries": [
                {"id": "ZA", "name": "南非"}
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

### 法规文件下载

**GET** `/api/laws/{id}/download`

仅返回已发布法规的文件。以原始文件名作为下载名。

```bash
curl -O -J http://localhost:6768/api/laws/1/download
```

| HTTP 状态码 | 错误码         | 说明        |
|----------|-------------|-----------|
| 200      | -           | 文件下载      |
| 404      | `NOT_FOUND` | 法规或文件不存在 |

---

## 6. 机构列表

**GET** `/api/agencies`

### 请求参数（Query）

| 字段            | 类型     | 必填 | 说明                           |
|---------------|--------|----|------------------------------|
| `page`        | int    | 否  | 页码，默认 1                      |
| `per_page`    | int    | 否  | 每页条数，默认 20                   |
| `scene_id`    | string | 否  | 按服务场景筛选，如 `law-labor`        |
| `category_id` | string | 否  | 按机构大类筛选，如 `law`、`accounting` |
| `region`      | string | 否  | 按覆盖区域筛选                    |
| `keyword`     | string | 否  | 按机构名称或覆盖区域模糊搜索               |

### 响应状态

| HTTP 状态码 | 说明            |
|----------|---------------|
| 200      | 成功，返回机构列表和元数据 |

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
                "name": "Webber Wentzel",
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

| 字段           | 类型     | 必填 | 说明                                         |
|--------------|--------|----|--------------------------------------------|
| `page`       | int    | 否  | 页码，默认 1                                    |
| `per_page`   | int    | 否  | 每页条数，默认 20                                 |
| `type`       | string | 否  | 按类型筛选：`cooperation` / `hotspot` / `update` |
| `country_id` | string | 否  | 按国家筛选                                      |
| `tag_id`     | int    | 否  | 按标签筛选                                      |
| `date_from`  | string | 否  | 发布日期起始 (YYYY-MM-DD)                       |
| `date_to`    | string | 否  | 发布日期截止 (YYYY-MM-DD)                       |
| `keyword`    | string | 否  | 按标题模糊搜索                                    |

> `meta.tags` 为当前筛选条件下所有匹配结果的标签集合。

### 响应状态

| HTTP 状态码 | 说明            |
|----------|---------------|
| 200      | 成功，返回资讯列表和元数据 |

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
                    {"id": 7, "name": "数据安全"},
                    {"id": 8, "name": "行政处罚"}
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
            "countries": [{"id": "ZA", "name": "南非"}],
            "tags": [{"id": 7, "name": "数据安全"}]
        }
    },
    "message": "成功"
}
```

---

### 资讯详情

**GET** `/api/news/{id}`

返回资讯所有字段及正文内容。

#### 请求示例

```bash
curl http://localhost:6768/api/news/4
```

#### 响应示例（成功）

```json
{
    "success": true,
    "data": {
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
        "content": "南非信息监管机构（Information Regulator）于 2026 年 4 月对多家未履行数据跨境传输评估义务的企业...",
        "tags": [
            {"id": 7, "name": "数据安全"},
            {"id": 8, "name": "行政处罚"}
        ],
        "created_at": "2026-05-17T12:00:00"
    },
    "message": "成功"
}
```

#### 响应示例（无正文）

```json
{
    "success": true,
    "data": {
        "id": 5,
        "type": "cooperation",
        "title": "中非经贸合作新进展",
        "source": "商务部",
        "country_id": "ZA",
        "date": "2026-05-01",
        "summary": "中非经贸合作持续深化...",
        "risk_level": "low",
        "involved_laws": null,
        "response": null,
        "update_type": null,
        "change_desc": null,
        "impact": null,
        "advice": null,
        "content": null,
        "tags": [],
        "created_at": "2026-05-17T12:00:00"
    },
    "message": "成功"
}
```

| HTTP 状态码 | 错误码         | 说明    |
|----------|-------------|-------|
| 200      | -           | 成功    |
| 404      | `NOT_FOUND` | 记录不存在 |

---

## 8. 平台统计

**GET** `/api/stats`

实时统计各表行数（数据库 VIEW），无需参数。

### 响应状态

| HTTP 状态码 | 说明        |
|----------|-----------|
| 200      | 成功，返回统计数值 |

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

## 9. 后台管理（通用：agencies）

所有接口需携带 JWT。`{resource}` 仅支持：`agencies`。

> **news** 和 **laws** 已拆分为独立路由，详见 [第 11 节](#11-资讯后台管理news支持正文编辑--draft) 和 [第 12 节](#12-法规后台管理laws支持文件上传--draft)。

`admin` 创建/更新直接生效（`published`），`editor` 创建/更新自动进入待审核（`draft`）。

---

### 列表

**GET** `/api/admin/agencies?page=1&per_page=20&status=draft`

| 参数         | 类型     | 必填 | 说明                                     |
|------------|--------|----|----------------------------------------|
| `page`     | int    | 否  | 页码，默认 1                                |
| `per_page` | int    | 否  | 每页条数，默认 20                             |
| `status`      | string | 否  | `draft` 待审核 / `published` 已发布 / 不传返回全部 |
| `scene_id`    | string | 否  | 按服务场景筛选，如 `law-labor` |
| `category_id` | string | 否  | 按机构大类筛选，如 `law`、`accounting` |
| `region`      | string | 否  | 按覆盖区域筛选 |
| `keyword`     | string | 否  | 按机构名称模糊搜索 |

```bash
curl -H 'Authorization: Bearer {token}' \
  'http://localhost:6768/api/admin/agencies?status=published&scene_id=law-labor&page=1'
```

**响应：**

```json
{
    "success": true,
    "data": {
        "items": [
            {
                "id": 6,
                "name": "Webber Wentzel",
                "status": "published",
                "created_at": "2026-05-17T12:00:00",
                "updated_at": "2026-05-17T12:00:00"
            }
        ],
        "meta": {"page": 1, "per_page": 20, "total": 68}
    },
    "message": "成功"
}
```

---

### 创建

**POST** `/api/admin/agencies`

Content-Type: `application/json`。Body 为 Agency 字段（无需传 `status`，由 role 自动决定）。

```bash
# admin 创建（直接 published）
curl -X POST http://localhost:6768/api/admin/agencies \
  -H 'Authorization: Bearer {admin_token}' \
  -H 'Content-Type: application/json' \
  -d '{"name":"新机构","scene_id":"law-labor","region":"南非"}'

# editor 创建（自动 draft）
curl -X POST http://localhost:6768/api/admin/agencies \
  -H 'Authorization: Bearer {editor_token}' \
  -H 'Content-Type: application/json' \
  -d '{"name":"新机构","scene_id":"law-labor"}'
```

**admin 创建响应（201）：**

```json
{
    "success": true,
    "data": {
        "item": { "id": 69, "name": "新机构", "scene_id": "law-labor", "status": "published", "created_at": "2026-05-17T12:00:00", "updated_at": "2026-05-17T12:00:00" }
    },
    "message": "创建成功"
}
```

---

### 详情

**GET** `/api/admin/agencies/{id}`

```bash
curl -H 'Authorization: Bearer {token}' \
  http://localhost:6768/api/admin/agencies/6
```

**响应：**

```json
{
    "success": true,
    "data": {
        "item": { "id": 6, "name": "Webber Wentzel", "status": "published", "created_at": "2026-05-17T12:00:00", "updated_at": "2026-05-17T12:00:00" }
    },
    "message": "成功"
}
```

---

### 更新

**PUT** `/api/admin/agencies/{id}`

Content-Type: `application/json`。

```bash
curl -X PUT http://localhost:6768/api/admin/agencies/6 \
  -H 'Authorization: Bearer {admin_token}' \
  -H 'Content-Type: application/json' \
  -d '{"name":"修改后的名称"}'
```

**响应：**

```json
{
    "success": true,
    "data": {
        "item": { "id": 6, "name": "修改后的名称", "status": "published" }
    },
    "message": "更新成功"
}
```

---

### 删除

**DELETE** `/api/admin/agencies/{id}`

admin 可删除任意记录，editor 仅可删除 `draft` 状态的记录。

```bash
# admin 删除
curl -X DELETE http://localhost:6768/api/admin/agencies/69 \
  -H 'Authorization: Bearer {admin_token}'

# editor 删除自己的草稿
curl -X DELETE http://localhost:6768/api/admin/agencies/70 \
  -H 'Authorization: Bearer {editor_token}'
```

**响应：**

```json
{ "success": true, "data": null, "message": "删除成功" }
```

**editor 删除已发布记录（403）：**

```json
{ "success": false, "error": { "code": "AUTH_ERROR", "message": "权限不足" } }
```

---

### 审核通过（仅 admin）

**POST** `/api/admin/agencies/{id}/approve`

```bash
curl -X POST http://localhost:6768/api/admin/agencies/70/approve \
  -H 'Authorization: Bearer {admin_token}'
```

**响应：**

```json
{
    "success": true,
    "data": {
        "item": { "id": 70, "status": "published" }
    },
    "message": "审核通过"
}
```

---

### 批量审核（仅 admin）

**POST** `/api/admin/agencies/approve-batch`

单事务，全部成功或全部 rollback。

```bash
curl -X POST http://localhost:6768/api/admin/agencies/approve-batch \
  -H 'Authorization: Bearer {admin_token}' \
  -H 'Content-Type: application/json' \
  -d '{"ids": [1, 3, 7]}'
```

**响应：**

```json
{
    "success": true,
    "data": {"approved": [1, 3, 7]},
    "message": "批量审核完成"
}
```

---

### 挂起（仅 admin）

**POST** `/api/admin/agencies/{id}/suspend`

将已发布记录调回 `draft` 状态，同时清除关联的 draft 行。

```bash
curl -X POST http://localhost:6768/api/admin/agencies/6/suspend \
  -H 'Authorization: Bearer {admin_token}'
```

**响应：**

```json
{
    "success": true,
    "data": {
        "item": { "id": 6, "status": "draft" }
    },
    "message": "已挂起"
}
```

---

## 10. 参考表后台管理

6 张静态参考表，无 `status` / 无 draft，创建即生效。复用 `{resource}` 通用路由。

### 权限矩阵

| 表 | resource key | admin | editor |
|---|---|---|---|
| `countries` | `countries` | CRUD | CRUD |
| `compliance_scenes` | `compliance-scenes` | CRUD | CRUD |
| `agency_categories` | `agency-categories` | CRUD | CRUD |
| `agency_scenes` | `agency-scenes` | CRUD | CRUD |
| `news_tags` | `news-tags` | CRUD | CRUD |

### 列表

**GET** `/api/admin/{resource}`

无分页（参考表数据量小），返回全量。

```bash
curl -H 'Authorization: Bearer {token}' \
  http://localhost:6768/api/admin/countries
```

**响应：**

```json
{
    "success": true,
    "data": {
        "items": [
            {"id": "ZA", "name": "南非", "name_en": "South Africa", "sort_order": 1},
            {"id": "NG", "name": "尼日利亚", "name_en": "Nigeria", "sort_order": 3}
        ]
    },
    "message": "成功"
}
```

### 详情

**GET** `/api/admin/{resource}/{id}`

```bash
curl -H 'Authorization: Bearer {token}' \
  http://localhost:6768/api/admin/countries/ZA
```

### 创建

**POST** `/api/admin/{resource}`

Content-Type: `application/json`。

```bash
curl -X POST http://localhost:6768/api/admin/countries \
  -H 'Authorization: Bearer {admin_token}' \
  -H 'Content-Type: application/json' \
  -d '{"id":"KE","name":"肯尼亚","name_en":"Kenya","sort_order":7}'
```

**响应（201）：**

```json
{
    "success": true,
    "data": {
        "item": {"id": "KE", "name": "肯尼亚", "name_en": "Kenya", "sort_order": 7}
    },
    "message": "创建成功"
}
```

### 修改

**PUT** `/api/admin/{resource}/{id}`

```bash
curl -X PUT http://localhost:6768/api/admin/countries/KE \
  -H 'Authorization: Bearer {admin_token}' \
  -H 'Content-Type: application/json' \
  -d '{"name":"肯尼亚共和国"}'
```

### 删除（仅 admin）

`DELETE /api/admin/{resource}/{id}` 对所有参考表仅 admin 可操作。

```bash
curl -X DELETE http://localhost:6768/api/admin/countries/KE \
  -H 'Authorization: Bearer {admin_token}'
```

**editor 调用受限表（403）：**

```json
{ "success": false, "error": { "code": "AUTH_ERROR", "message": "权限不足" } }
```

---

## 11. 资讯后台管理（news，支持正文编辑 + Draft）

news 接口独立于通用后台，**支持正文 content 字段的读写**。正文存储在 `news_text` 表，创建/修改时作为可选字段传入。

### Draft 机制

| 操作 | 行为 |
|------|------|
| editor CREATE | INSERT news (status='draft')，无 draft 行 |
| editor UPDATE 已发布 | news 行不变（public 可见旧数据），INSERT/UPDATE `news_drafts.data`（存完整行数据） |
| editor UPDATE 自己 draft | 直接 UPDATE news 行 |
| admin APPROVE | `news_drafts.data` 覆盖 news 行所有列 → DELETE draft 行 → status='published' |
| admin 直接修改 | UPDATE news，无 draft 行，status='published' |

> `admin` 创建/更新直接 `published`，`editor` 创建/更新自动 `draft`。

---

### 11.1 资讯列表

**GET** `/api/admin/news?page=1&per_page=20&status=draft`

| 参数         | 类型     | 必填 | 说明                                     |
|------------|--------|----|----------------------------------------|
| `page`     | int    | 否  | 页码，默认 1                                |
| `per_page` | int    | 否  | 每页条数，默认 20                             |
| `status`     | string | 否  | `draft` / `published` / 不传返回全部          |
| `type`       | string | 否  | `cooperation` / `hotspot` / `update` |
| `country_id` | string | 否  | 按国家筛选 |
| `tag_id`     | int    | 否  | 按标签筛选 |
| `date_from`  | string | 否  | 发布日期起始 (YYYY-MM-DD) |
| `date_to`    | string | 否  | 发布日期截止 (YYYY-MM-DD) |
| `keyword`    | string | 否  | 按标题模糊搜索 |

```bash
curl -H 'Authorization: Bearer {token}' \
  'http://localhost:6768/api/admin/news?status=draft&type=hotspot&country_id=ZA'
```

**响应（列表不含正文）：**

```json
{
    "success": true,
    "data": {
        "items": [
            {
                "id": 3,
                "type": "cooperation",
                "title": "待审资讯",
                "source": "商务部",
                "country_id": "ZA",
                "date": "2026-05-01",
                "summary": "中非经贸合作新进展...",
                "risk_level": "low",
                "status": "draft",
                "created_at": "2026-05-17T12:00:00",
                "updated_at": "2026-05-17T12:00:00"
            }
        ],
        "meta": {
            "page": 1,
            "per_page": 20,
            "total": 1,
            "types": [
                {"value": "cooperation", "label_zh": "中非合作"},
                {"value": "hotspot", "label_zh": "合规热点"},
                {"value": "update", "label_zh": "法规更新"}
            ],
            "countries": [{"id": "ZA", "name": "南非"}],
            "tags": [{"id": 7, "name": "数据安全"}]
        }
    },
    "message": "成功"
}
```

---

### 11.2 资讯详情（含正文 + Draft 预览）

**GET** `/api/admin/news/{id}`

```bash
curl -H 'Authorization: Bearer {token}' \
  http://localhost:6768/api/admin/news/4
```

**响应（含 content 字段）：**

```json
{
    "success": true,
    "data": {
        "item": {
            "id": 4,
            "type": "hotspot",
            "title": "南非数据跨境传输合规风波",
            "source": "合规追踪",
            "country_id": "ZA",
            "date": "2026-04-30",
            "summary": "南非信息监管机构对未履行数据跨境传输评估义务的企业开出罚单...",
            "risk_level": "high",
            "involved_laws": "南非数据保护法（POPIA）",
            "response": "立即注册信息官",
            "update_type": null,
            "change_desc": null,
            "impact": null,
            "advice": null,
            "content": "南非信息监管机构（Information Regulator）于 2026 年 4 月对多家企业...",
            "status": "published",
            "created_at": "2026-05-17T12:00:00",
            "updated_at": "2026-05-17T12:00:00"
        }
    },
    "message": "成功"
}
```

---

### 11.3 创建资讯（含可选正文）

**POST** `/api/admin/news`

Content-Type: `application/json`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `type` | string | 是 | `cooperation` / `hotspot` / `update` |
| `title` | string | 是 | 标题 |
| `source` | string | 否 | 来源 |
| `country_id` | string | 否 | 国家代码 |
| `date` | string | 是 | 发布日期 (YYYY-MM-DD) |
| `summary` | string | 否 | 摘要 |
| `risk_level` | string | 否 | `high` / `medium` / `low` |
| `involved_laws` | string | 否 | 涉事法规 |
| `response` | string | 否 | 应对建议 |
| `update_type` | string | 否 | `修订` / `新增` / `废止` |
| `change_desc` | string | 否 | 核心更新内容 |
| `impact` | string | 否 | 对企业影响 |
| `advice` | string | 否 | 合规建议 |
| `content` | string | 否 | **正文内容**（写入 `news_text` 表） |
| `tag_ids` | int[] | 否 | 标签 ID 列表 |

```bash
curl -X POST http://localhost:6768/api/admin/news \
  -H 'Authorization: Bearer {admin_token}' \
  -H 'Content-Type: application/json' \
  -d '{
    "type": "hotspot",
    "title": "新法规动态",
    "country_id": "ZA",
    "date": "2026-07-15",
    "summary": "南非发布新法规...",
    "content": "详细正文内容..."
  }'
```

**admin 创建响应（201）：**

```json
{
    "success": true,
    "data": {
        "item": {
            "id": 13,
            "type": "hotspot",
            "title": "新法规动态",
            "content": "详细正文内容...",
            "status": "published",
            "created_at": "2026-07-15T10:00:00",
            "updated_at": "2026-07-15T10:00:00"
        }
    },
    "message": "创建成功"
}
```

---

### 11.4 修改资讯（含可选正文更新）

**PUT** `/api/admin/news/{id}`

Content-Type: `application/json`

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| (所有 News 字段) | | 否 | 仅传需要修改的字段 |
| `content` | string | 否 | **正文内容**（传入则 upsert `news_text` 行） |

```bash
# 仅修改标题
curl -X PUT http://localhost:6768/api/admin/news/4 \
  -H 'Authorization: Bearer {admin_token}' \
  -H 'Content-Type: application/json' \
  -d '{"title":"修改后的标题"}'

# 修改正文内容
curl -X PUT http://localhost:6768/api/admin/news/4 \
  -H 'Authorization: Bearer {admin_token}' \
  -H 'Content-Type: application/json' \
  -d '{"content":"更新后的正文内容..."}'
```

**响应（200）：**

```json
{
    "success": true,
    "data": {
        "item": { "id": 4, "title": "修改后的标题", "content": "更新后的正文内容...", "status": "published", "updated_at": "2026-07-15T10:30:00" }
    },
    "message": "更新成功"
}
```

---

### 11.5 删除资讯

**DELETE** `/api/admin/news/{id}`

admin 可删除任意记录，editor 仅可删除 `draft` 状态的记录。CASCADE 删除关联的 `news_text` 和 `news_tag_relations`。

```bash
# admin 删除
curl -X DELETE http://localhost:6768/api/admin/news/13 \
  -H 'Authorization: Bearer {admin_token}'

# editor 删除自己的草稿
curl -X DELETE http://localhost:6768/api/admin/news/13 \
  -H 'Authorization: Bearer {editor_token}'
```

**响应（200）：**

```json
{ "success": true, "data": null, "message": "删除成功" }
```

---

### 11.6 审核通过（仅 admin）

读取 `news_drafts.data` 覆盖 news 行所有列 → DELETE draft 行 → status='published'。

**POST** `/api/admin/news/{id}/approve`

审核通过后，正文 content 随主记录一同对外可见。

```bash
curl -X POST http://localhost:6768/api/admin/news/13/approve \
  -H 'Authorization: Bearer {admin_token}'
```

**响应：**

```json
{
    "success": true,
    "data": {
        "item": { "id": 13, "status": "published" }
    },
    "message": "审核通过"
}
```

---

### 11.7 批量审核（仅 admin）

**POST** `/api/admin/news/approve-batch`

单事务，全部成功或全部 rollback。

```bash
curl -X POST http://localhost:6768/api/admin/news/approve-batch \
  -H 'Authorization: Bearer {admin_token}' \
  -H 'Content-Type: application/json' \
  -d '{"ids": [1, 3, 7]}'
```

**响应：**

```json
{
    "success": true,
    "data": {"approved": [1, 3, 7]},
    "message": "批量审核完成"
}
```

---

### 11.8 挂起（仅 admin）

**POST** `/api/admin/news/{id}/suspend`

将已发布记录调回 `draft` 状态，同时清除关联的 draft 行。

```bash
curl -X POST http://localhost:6768/api/admin/news/13/suspend \
  -H 'Authorization: Bearer {admin_token}'
```

**响应：**

```json
{
    "success": true,
    "data": {
        "item": { "id": 13, "status": "draft" }
    },
    "message": "已挂起"
}
```

---

## 12. 法规后台管理（laws，支持文件上传 + Draft）

laws 接口独立于通用后台，**创建和更新使用 `multipart/form-data`** 以支持法规文件上传。

### Draft 机制

| 操作 | 行为 |
|------|------|
| editor CREATE | INSERT laws (status='draft')，无 draft 行 |
| editor UPDATE 已发布 | laws 行不变（public 可见旧数据），INSERT/UPDATE `laws_drafts.data`（存完整行数据） |
| editor UPDATE 自己 draft | 直接 UPDATE laws 行 |
| admin APPROVE | `laws_drafts.data` 覆盖 laws 行所有列 → DELETE draft 行 → status='published' |
| admin 直接修改 | UPDATE laws，无 draft 行，status='published' |

> `admin` 创建/更新直接 `published`，`editor` 创建/更新自动 `draft`。

---

### 12.1 法规列表

**GET** `/api/admin/laws?page=1&per_page=20&status=draft`

| 参数         | 类型     | 必填 | 说明                                     |
|------------|--------|----|----------------------------------------|
| `page`     | int    | 否  | 页码，默认 1                                |
| `per_page` | int    | 否  | 每页条数，默认 20                             |
| `status`     | string | 否  | `draft` / `published` / 不传返回全部          |
| `country_id` | string | 否  | 按国家筛选，如 `ZA` |
| `scene_id`   | string | 否  | 按场景筛选，如 `customs` |
| `keyword`    | string | 否  | 按中英文标题模糊搜索 |

```bash
curl -H 'Authorization: Bearer {token}' \
  'http://localhost:6768/api/admin/laws?status=draft&country_id=ZA&scene_id=customs'
```

**响应：**

```json
{
    "success": true,
    "data": {
        "items": [
            {
                "id": 3,
                "title_cn": "待审法规",
                "title_en": null,
                "law_number": null,
                "country_id": "ZA",
                "scene_id": "customs",
                "effective_date": null,
                "summary": null,
                "filename": "南非海关法.pdf",
                "has_file": true,
                "status": "draft",
                "created_at": "2026-05-17T12:00:00",
                "updated_at": "2026-05-17T12:00:00"
            }
        ],
        "meta": {
            "page": 1,
            "per_page": 20,
            "total": 1,
            "countries": [{"id": "ZA", "name": "南非"}],
            "scenes": [{"id": "customs", "label_zh": "海关进出口"}]
        }
    },
    "message": "成功"
}
```

---

### 12.2 法规详情（含 Draft 预览）

**GET** `/api/admin/laws/{id}`

```bash
curl -H 'Authorization: Bearer {token}' \
  http://localhost:6768/api/admin/laws/1
```

**响应：**

```json
{
    "success": true,
    "data": {
        "item": {
            "id": 1,
            "title_cn": "南非海关管理法（修订版）",
            "title_en": null,
            "law_number": null,
            "country_id": "ZA",
            "scene_id": "customs",
            "effective_date": "2024-01-15",
            "summary": "制造业进口原材料需提前30天备案...",
            "filename": "南非海关法.pdf",
            "has_file": true,
            "status": "published",
            "created_at": "2026-05-17T12:00:00",
            "updated_at": "2026-05-17T12:00:00"
        }
    },
    "message": "成功"
}
```

---

### 12.3 创建法规（含文件上传）

**POST** `/api/admin/laws`

Content-Type: **`multipart/form-data`**（非 JSON）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `title_cn` | string | 是 | 中文标题 |
| `title_en` | string | 否 | 英文标题 |
| `law_number` | string | 否 | 法号 |
| `country_id` | string | 是 | 国家代码，如 `ZA` |
| `scene_id` | string | 是 | 场景代码，如 `customs` |
| `effective_date` | string | 否 | 生效日期 (YYYY-MM-DD) |
| `summary` | string | 否 | 法规摘要 |
| `file` | file | 否 | 法规文件（PDF/Word 等） |

**处理逻辑：**
1. 从 `request.form` 提取文本字段，`request.files` 提取文件
2. 若提供了 `file`：提取原始扩展名，生成 `{uuid}.{ext}` 格式文件名，保存至 `{UPLOAD_PATH}/laws/`
3. 创建 Law 记录，`secure_name` 存储生成的文件名，`filename` 存储原始文件名
4. 若用户非 admin，`status` 自动设为 `draft`

```bash
# admin 创建（含文件）
curl -X POST http://localhost:6768/api/admin/laws \
  -H 'Authorization: Bearer {admin_token}' \
  -F 'title_cn=南非海关管理法' \
  -F 'title_en=South Africa Customs Act' \
  -F 'law_number=Act No. 91 of 2004' \
  -F 'country_id=ZA' \
  -F 'scene_id=customs' \
  -F 'effective_date=2024-01-15' \
  -F 'summary=制造业进口原材料需提前30天备案' \
  -F 'file=@/path/to/document.pdf'
```

**admin 创建响应（201）：**

```json
{
    "success": true,
    "data": {
        "item": {
            "id": 13,
            "title_cn": "南非海关管理法",
            "title_en": "South Africa Customs Act",
            "law_number": "Act No. 91 of 2004",
            "country_id": "ZA",
            "scene_id": "customs",
            "effective_date": "2024-01-15",
            "summary": "制造业进口原材料需提前30天备案",
            "filename": "南非海关法.pdf",
            "has_file": true,
            "status": "published",
            "created_at": "2026-05-17T12:00:00",
            "updated_at": "2026-05-17T12:00:00"
        }
    },
    "message": "创建成功"
}
```

---

### 12.4 修改法规（可选替换文件）

**PUT** `/api/admin/laws/{id}`

Content-Type: **`multipart/form-data`**（非 JSON）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `title_cn` | string | 否 | 中文标题 |
| `title_en` | string | 否 | 英文标题 |
| `law_number` | string | 否 | 法号 |
| `country_id` | string | 否 | 国家代码 |
| `scene_id` | string | 否 | 场景代码 |
| `effective_date` | string | 否 | 生效日期 |
| `summary` | string | 否 | 法规摘要 |
| `file` | file | 否 | 替换文件（若提供则删除旧文件并保存新文件） |

**处理逻辑：**
1. 查找已有 Law 记录
2. 若提供了 `file`：
   - 删除旧文件：`os.remove({UPLOAD_PATH}/laws/{旧secure_name})`（如旧文件存在）
   - 保存新文件，生成新 UUID 文件名，更新 `secure_name` 和 `filename`
3. 更新其他字段
4. 若用户非 admin，`status` 自动设为 `draft`

```bash
# 替换文件
curl -X PUT http://localhost:6768/api/admin/laws/1 \
  -H 'Authorization: Bearer {admin_token}' \
  -F 'title_cn=修改后的标题' \
  -F 'file=@/path/to/new_document.pdf'

# 仅修改文本字段（不替换文件）
curl -X PUT http://localhost:6768/api/admin/laws/1 \
  -H 'Authorization: Bearer {admin_token}' \
  -F 'title_cn=修改后的标题' \
  -F 'effective_date=2025-01-01'
```

**响应（200）：**

```json
{
    "success": true,
    "data": {
        "item": {
            "id": 1,
            "title_cn": "修改后的标题",
            "filename": "新法规文件.pdf",
            "has_file": true,
            "status": "published",
            "updated_at": "2026-07-15T10:30:00"
        }
    },
    "message": "更新成功"
}
```

---

### 12.5 删除法规（含文件清理）

**DELETE** `/api/admin/laws/{id}`

admin 可删除任意记录，editor 仅可删除 `draft` 状态的记录。

**处理逻辑：**
1. 查找 Law 记录，非 admin 且 status ≠ draft 则返回 403
2. 若 `secure_name` 非空：删除本地文件 `{UPLOAD_PATH}/laws/{secure_name}`（删除失败不阻塞，仅记录日志）
3. 删除数据库记录

```bash
# admin 删除
curl -X DELETE http://localhost:6768/api/admin/laws/1 \
  -H 'Authorization: Bearer {admin_token}'

# editor 删除自己的草稿
curl -X DELETE http://localhost:6768/api/admin/laws/13 \
  -H 'Authorization: Bearer {editor_token}'
```

**响应（200）：**

```json
{ "success": true, "data": null, "message": "删除成功" }
```

**权限不足（403）：**

```json
{ "success": false, "error": { "code": "AUTH_ERROR", "message": "权限不足" } }
```

---

### 12.6 审核通过（仅 admin）

读取 `laws_drafts.data` 覆盖 laws 行所有列 → DELETE draft 行 → status='published'。

**POST** `/api/admin/laws/{id}/approve`

```bash
curl -X POST http://localhost:6768/api/admin/laws/13/approve \
  -H 'Authorization: Bearer {admin_token}'
```

**响应：**

```json
{
    "success": true,
    "data": {
        "item": { "id": 13, "status": "published" }
    },
    "message": "审核通过"
}
```

---

### 12.7 批量审核（仅 admin）

**POST** `/api/admin/laws/approve-batch`

单事务，全部成功或全部 rollback。事务提交后统一清理旧文件。

```bash
curl -X POST http://localhost:6768/api/admin/laws/approve-batch \
  -H 'Authorization: Bearer {admin_token}' \
  -H 'Content-Type: application/json' \
  -d '{"ids": [1, 3, 7]}'
```

**响应：**

```json
{
    "success": true,
    "data": {"approved": [1, 3, 7]},
    "message": "批量审核完成"
}
```

---

### 12.8 挂起（仅 admin）

**POST** `/api/admin/laws/{id}/suspend`

将已发布记录调回 `draft` 状态，同时清除关联的 draft 行。

```bash
curl -X POST http://localhost:6768/api/admin/laws/13/suspend \
  -H 'Authorization: Bearer {admin_token}'
```

**响应：**

```json
{
    "success": true,
    "data": {
        "item": { "id": 13, "status": "draft" }
    },
    "message": "已挂起"
}
```

---

## 13. 用户管理（仅 admin）

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

| HTTP 状态码 | 错误码                | 说明            |
|----------|--------------------|---------------|
| 201      | -                  | 创建成功          |
| 200      | -                  | 操作成功          |
| 400      | `VALIDATION_ERROR` | 参数不合法         |
| 401      | `AUTH_ERROR`       | 未登录或 token 无效 |
| 403      | `AUTH_ERROR`       | 权限不足          |
| 404      | `NOT_FOUND`        | 记录不存在         |

---

## 14. 合规报告

> 异步生成合规报告：上传企业信息 + 可选附件，通过百炼 AI 生成诊断报告，轮询获取结果。

### 14.1 创建报告任务

**POST** `/api/compliance-reports`

需要携带 JWT access token。Content-Type: `multipart/form-data`。

#### 请求参数

| 字段              | 类型     | 必填 | 说明            |
|-----------------|--------|----|---------------|
| `query`         | string | 是  | 诊断需求/企业概况描述   |
| `company_name`  | string | 是  | 公司名称          |
| `industry`      | string | 是  | 所属行业          |
| `company_size`  | string | 是  | 企业规模          |
| `target_country` | string | 是  | 目标出海国家        |
| `business_model` | string | 是  | 业务模式          |
| `budget_range`  | string | 是  | 预算区间          |
| `documents`     | file   | 否  | 附件（可多选，最多 5 个） |

**文件限制**：单个文件 ≤ 20MB，支持 PDF、DOC、DOCX、TXT、HTML。

#### 响应状态

| HTTP 状态码 | 错误码                | 消息                | 说明               |
|----------|--------------------|--------------------|------------------|
| 202      | -                  | 报告生成任务已创建        | 创建成功，后台生成中      |
| 400      | `VALIDATION_ERROR` | 缺少必填字段 / 不支持的文件类型 | 参数或文件不合法        |
| 413      | `FILE_TOO_LARGE`   | 上传文件总大小超过限制       | 请求体超过 105MB      |
| 401      | `AUTH_ERROR`       | 缺少认证令牌            | 未登录或 token 无效   |
| 502      | `OSS_UPLOAD_FAILED` | 文件上传至 OSS 失败      | OSS 不可用          |
| 502      | `BAILIAN_ERROR`    | 调用百炼失败            | 百炼 API 不可用或调用失败 |
| 500      | `CONFIG_ERROR`     | 报告生成服务未配置         | `REPORT_GENERATOR_APPID`、`BAILIAN_API_KEY`、`REPORT_AI_VERSION` 或 `REPORT_DATA_CUTOFF_DATE` 未配置 |

#### 请求示例

```bash
curl -X POST http://localhost:5000/api/compliance-reports \
  -H 'Authorization: Bearer <token>' \
  -F 'query=我公司计划在南非设立制造工厂，请分析合规要求' \
  -F 'company_name=示例制造有限公司' \
  -F 'industry=家电制造' \
  -F 'company_size=中型' \
  -F 'target_country=南非' \
  -F 'business_model=合资' \
  -F 'budget_range=100-500万' \
  -F 'documents=@business_plan.pdf'
```

#### 响应示例（成功 202）

```json
{
    "success": true,
    "data": {
        "id": 1,
        "task_id": "resp_abc123def456",
        "status": "in_progress",
        "company_name": "示例制造有限公司",
        "industry": "家电制造",
        "country": "南非",
        "company_size": "中型",
        "budget_range": "100-500万",
        "business_model": "合资",
        "doc_count": 1,
        "deleted": false,
        "created_at": "2026-07-21T10:00:00"
    },
    "message": "报告生成任务已创建"
}
```

### 14.2 报告列表

**GET** `/api/compliance-reports?page=1&per_page=20`

需要携带 JWT access token。返回当前用户自己的未删除记录。

#### 查询参数

| 字段        | 类型  | 必填 | 默认值 | 说明   |
|-----------|-----|----|-----|------|
| `page`    | int | 否  | 1   | 页码   |
| `per_page` | int | 否  | 20  | 每页数量 |

#### 响应示例（成功 200）

```json
{
    "success": true,
    "data": {
        "reports": [
            {
                "id": 1,
                "company_name": "示例制造有限公司",
                "industry": "家电制造",
                "country": "南非",
                "company_size": "中型",
                "budget_range": "100-500万",
                "business_model": "合资",
                "doc_count": 1,
                "status": "completed",
                "deleted": false,
                "created_at": "2026-07-21T10:00:00"
            }
        ],
        "meta": {
            "page": 1,
            "per_page": 20,
            "total": 1
        }
    },
    "message": "成功"
}
```

### 14.3 报告详情

**GET** `/api/compliance-reports/{id}`

需要携带 JWT access token。只能访问自己的未删除记录，无权限或已删除按 404 处理。

管理员查看任意记录（含已删除）请使用 `GET /api/admin/compliance-reports/{id}`。

`result_text` 是符合前端报告 schema 的 JSON 字符串。

#### 响应示例（成功 200，已完成）

```json
{
    "success": true,
    "data": {
        "id": 1,
        "company_name": "示例制造有限公司",
        "industry": "家电制造",
        "country": "南非",
        "company_size": "中型",
        "budget_range": "100-500万",
        "business_model": "合资",
        "doc_count": 1,
        "status": "completed",
        "deleted": false,
        "result_text": "<符合前端 report.json schema 的完整 JSON 字符串>",
        "created_at": "2026-07-21T10:00:00"
    },
    "message": "成功"
}
```

#### 响应示例（成功 200，处理中）

```json
{
    "success": true,
    "data": {
        "id": 2,
        "company_name": "示例科技有限公司",
        "industry": "数字基础设施",
        "country": "尼日利亚",
        "company_size": "大型",
        "budget_range": "500万以上",
        "business_model": "独资",
        "doc_count": 0,
        "status": "in_progress",
        "deleted": false,
        "result_text": null,
        "created_at": "2026-07-21T10:05:00"
    },
    "message": "成功"
}
```

#### 响应状态

| HTTP 状态码 | 错误码          | 消息      | 说明         |
|----------|--------------|---------|------------|
| 200      | -            | 成功      | 返回报告详情     |
| 401      | `AUTH_ERROR` | 缺少认证令牌  | 未登录        |
| 404      | `NOT_FOUND`  | 报告不存在   | 记录不存在或无权限  |

### 14.4 删除报告

**DELETE** `/api/compliance-reports/{id}`

需要携带 JWT access token。仅可软删除自己的报告。不会物理删除 `diagnosis_records`
或 `diagnosis_results`，也不取消正在执行的百炼任务。重复删除同一记录仍返回成功。

管理员删除任意报告请使用 `DELETE /api/admin/compliance-reports/{id}`。

#### 响应示例（成功 200）

```json
{
    "success": true,
    "data": {
        "id": 1,
        "company_name": "示例制造有限公司",
        "industry": "家电制造",
        "country": "南非",
        "company_size": "中型",
        "budget_range": "100-500万",
        "business_model": "合资",
        "doc_count": 1,
        "status": "completed",
        "deleted": true,
        "created_at": "2026-07-21T10:00:00"
    },
    "message": "报告已删除"
}
```

#### 响应状态

| HTTP 状态码 | 错误码          | 说明                    |
|----------|--------------|-----------------------|
| 200      | -            | 删除成功或记录已经处于删除状态      |
| 401      | `AUTH_ERROR` | 未登录                   |
| 404      | `NOT_FOUND`  | 记录不存在，或普通用户并非记录所有者 |

---

## 15. 合规报告后台管理

所有接口需要 JWT，仅 `admin` 角色可访问（`editor` 返回 403）。可查看和删除所有用户的记录，包括已软删除记录。

### 15.1 全部报告列表

**GET** `/api/admin/compliance-reports?page=1&per_page=20`

返回所有用户的全部记录，含已软删除记录。

#### 查询参数

| 字段        | 类型  | 必填 | 默认值 | 说明   |
|-----------|-----|----|-----|------|
| `page`    | int | 否  | 1   | 页码   |
| `per_page` | int | 否  | 20  | 每页数量 |

#### 响应示例（成功 200）

```json
{
    "success": true,
    "data": {
        "reports": [
            {
                "id": 1,
                "company_name": "示例制造有限公司",
                "industry": "家电制造",
                "country": "南非",
                "company_size": "中型",
                "budget_range": "100-500万",
                "business_model": "合资",
                "doc_count": 1,
                "status": "completed",
                "deleted": false,
                "created_at": "2026-07-21T10:00:00"
            }
        ],
        "meta": {
            "page": 1,
            "per_page": 20,
            "total": 1
        }
    },
    "message": "成功"
}
```

### 15.2 任意报告详情

**GET** `/api/admin/compliance-reports/{id}`

返回任意报告详情（含已删除记录），无需权限校验。

#### 响应示例（成功 200）

```json
{
    "success": true,
    "data": {
        "id": 1,
        "company_name": "示例制造有限公司",
        "industry": "家电制造",
        "country": "南非",
        "company_size": "中型",
        "budget_range": "100-500万",
        "business_model": "合资",
        "doc_count": 1,
        "status": "completed",
        "deleted": false,
        "result_text": "<符合前端 report.json schema 的完整 JSON 字符串>",
        "created_at": "2026-07-21T10:00:00"
    },
    "message": "成功"
}
```

#### 响应状态

| HTTP 状态码 | 错误码          | 消息    | 说明          |
|----------|--------------|-------|-------------|
| 200      | -            | 成功    |              |
| 401      | `AUTH_ERROR` | 缺少认证令牌 | 未登录         |
| 403      | `AUTH_ERROR` | 权限不足  | 非 admin 角色 |
| 404      | `NOT_FOUND`  | 报告不存在  |              |

### 15.3 删除任意报告

**DELETE** `/api/admin/compliance-reports/{id}`

软删除任意用户的报告。

```bash
curl -X DELETE http://localhost:6768/api/admin/compliance-reports/1 \
  -H 'Authorization: Bearer {admin_token}'
```

#### 响应示例（成功 200）

```json
{
    "success": true,
    "data": {
        "id": 1,
        "company_name": "示例制造有限公司",
        "industry": "家电制造",
        "country": "南非",
        "company_size": "中型",
        "budget_range": "100-500万",
        "business_model": "合资",
        "doc_count": 1,
        "status": "completed",
        "deleted": true,
        "created_at": "2026-07-21T10:00:00"
    },
    "message": "报告已删除"
}
```

#### 响应状态

| HTTP 状态码 | 错误码          | 说明          |
|----------|--------------|-------------|
| 200      | -            | 删除成功        |
| 401      | `AUTH_ERROR` | 未登录         |
| 403      | `AUTH_ERROR` | 非 admin 角色 |
| 404      | `NOT_FOUND`  | 记录不存在       |
