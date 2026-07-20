# 数据库设计

> 基于需求文档 (`data.md`) 设计，使用 MySQL + SQLAlchemy ORM。

---

## 1. 用户

### users

| 字段               | 类型                   | 约束                                                              | 说明           |
|------------------|----------------------|-----------------------------------------------------------------|--------------|
| `id`             | BIGINT               | PK, AUTO_INCREMENT                                              | 主键           |
| `username`       | VARCHAR(50)          | UNIQUE, NOT NULL, INDEX                                         | 用户名          |
| `password_hash`  | VARCHAR(255)         | NOT NULL                                                        | 密码哈希（bcrypt） |
| `email`          | VARCHAR(255)         | NULLABLE, UNIQUE, INDEX                                         | 邮箱           |
| `email_verified` | BOOLEAN              | NOT NULL, DEFAULT FALSE                                         | 邮箱是否已验证      |
| `role`           | ENUM('user','editor','admin') | NOT NULL, DEFAULT 'user'                                        | 角色           |
| `created_at`     | DATETIME             | NOT NULL, DEFAULT CURRENT_TIMESTAMP                             | 创建时间         |
| `updated_at`     | DATETIME             | NOT NULL, DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 更新时间         |

---

## 2. 法规库

### countries

| 字段           | 类型           | 约束        | 说明               |
|--------------|--------------|-----------|------------------|
| `id`         | VARCHAR(10)  | PK        | 国家代码，如 `ZA`、`NG` |
| `name_zh`    | VARCHAR(50)  | NOT NULL  | 中文名，如「南非」        |
| `name_en`    | VARCHAR(100) |           | 英文名              |
| `sort_order` | INT          | DEFAULT 0 | 排序               |

### compliance_scenes

| 字段           | 类型          | 约束        | 说明                       |
|--------------|-------------|-----------|--------------------------|
| `id`         | VARCHAR(20) | PK        | 场景代码，如 `customs`、`labor` |
| `label_zh`   | VARCHAR(30) | NOT NULL  | 中文名，如「海关进出口」             |
| `sort_order` | INT         | DEFAULT 0 | 排序                       |

### laws

| 字段               | 类型           | 约束                                  | 说明      |
|------------------|--------------|-------------------------------------|---------|
| `id`             | BIGINT       | PK, AUTO_INCREMENT                  | 主键      |
| `title_cn`       | VARCHAR(300) | NOT NULL                            | 中文标题    |
| `title_en`       | VARCHAR(300) |                                     | 英文标题    |
| `law_number`     | VARCHAR(100) |                                     | 法号/法令编号 |
| `country_id`     | VARCHAR(10)  | FK → countries.id, NOT NULL         | 所属国家    |
| `scene_id`       | VARCHAR(20)  | FK → compliance_scenes.id, NOT NULL | 适用场景    |
| `effective_date` | DATE         |                                     | 生效/修订日期 |
| `summary`        | TEXT         |                                     | 法规要点摘要  |
| `filename`       | VARCHAR(500) |                                     | 原始文件名  |
| `secure_name`    | VARCHAR(500) |                                     | 存储文件名（UUID.ext） |
| `status`         | ENUM('draft','published') | NOT NULL, DEFAULT 'published'       | 发布状态    |
| `created_at`     | DATETIME     | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 创建时间    |
| `updated_at`     | DATETIME     | NOT NULL, ON UPDATE CURRENT_TIMESTAMP | 更新时间    |

### laws_drafts

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BIGINT | PK, AUTO_INCREMENT | 主键 |
| `law_id` | BIGINT | UNIQUE, FK → laws.id ON DELETE CASCADE | 关联法规 |
| `data` | JSON | NOT NULL | 完整行数据（待审批） |
| `editor_id` | BIGINT | FK → users.id | 编辑者 |
| `created_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| `updated_at` | DATETIME | NOT NULL, ON UPDATE CURRENT_TIMESTAMP | 更新时间 |

### diagnosis_records

| 字段           | 类型          | 约束                                  | 说明   |
|--------------|-------------|-------------------------------------|------|
| `id`         | BIGINT      | PK, AUTO_INCREMENT                  | 主键   |
| `user_id`    | BIGINT      | FK → users.id, NULLABLE             | 操作用户 |
| `country`        | VARCHAR(30) |                                  | 目的国 |
| `company_size`   | VARCHAR(20) |                                  | 企业规模 |
| `budget_range`   | VARCHAR(20) |                                  | 预算区间 |
| `business_model` | VARCHAR(20) |                                  | 业务模式 |
| `task_id`        | VARCHAR(100) | UNIQUE, INDEX                   | 报告生成任务 ID |
| `status`         | VARCHAR(30)  | INDEX                           | 任务状态 |
| `param`          | JSON         | NOT NULL                        | 报告生成参数及创建时的 AI 版本、数据截止日期快照 |
| `deleted`        | BOOLEAN      | NOT NULL, DEFAULT FALSE, INDEX  | 软删除标记 |
| `created_at`     | DATETIME    | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 生成时间 |

### diagnosis_results

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `record_id` | BIGINT | PK, FK → diagnosis_records.id ON DELETE CASCADE | 关联诊断 |
| `result` | JSON | NOT NULL | 完整报告数据 |
| `created_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| `updated_at` | DATETIME | NOT NULL, ON UPDATE CURRENT_TIMESTAMP | 更新时间 |

> **迁移说明**：现有数据库需手动执行 ALTER TABLE 添加索引和约束，不可依赖 `db.create_all()` 修改旧表：
> ```sql
> ALTER TABLE diagnosis_records
>   ADD UNIQUE KEY `task_id` (`task_id`),
>   ADD KEY `status` (`status`),
>   MODIFY `param` json NOT NULL;
> ALTER TABLE diagnosis_results
>   MODIFY `result` json NOT NULL;
> ALTER TABLE diagnosis_records
>   ADD COLUMN `deleted` tinyint(1) NOT NULL DEFAULT 0 AFTER `param`,
>   ADD KEY `deleted` (`deleted`);
> ```

---

## 3. 资讯库

### news

| 字段              | 类型                                     | 约束                                  | 说明     |
|-----------------|----------------------------------------|-------------------------------------|--------|
| `id`            | BIGINT                                 | PK, AUTO_INCREMENT                  | 主键     |
| `type`          | ENUM('cooperation','hotspot','update') | NOT NULL                            | 新闻类型   |
| `title`         | VARCHAR(300)                           | NOT NULL                            | 标题     |
| `source`        | VARCHAR(200)                           |                                     | 来源     |
| `country_id`    | VARCHAR(10)                            | FK → countries.id                   | 关联国家   |
| `date`          | DATE                                   | NOT NULL                            | 发布日期   |
| `summary`       | TEXT                                   |                                     | 摘要     |
| `risk_level`    | ENUM('high','medium','low')            |                                     | 风险等级   |
| `involved_laws` | TEXT                                   |                                     | 涉事法规   |
| `response`      | TEXT                                   |                                     | 应对建议   |
| `update_type`   | ENUM('修订','新增','废止')                   |                                     | 更新类型   |
| `change_desc`   | TEXT                                   |                                     | 核心更新内容 |
| `impact`        | TEXT                                   |                                     | 对企业影响  |
| `advice`        | TEXT                                   |                                     | 合规建议   |
| `status`        | ENUM('draft','published')              | NOT NULL, DEFAULT 'published'        | 发布状态   |
| `created_at`    | DATETIME                               | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 创建时间   |
| `updated_at`    | DATETIME                               | NOT NULL, ON UPDATE CURRENT_TIMESTAMP | 更新时间   |

### news_drafts

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BIGINT | PK, AUTO_INCREMENT | 主键 |
| `news_id` | BIGINT | UNIQUE, FK → news.id ON DELETE CASCADE | 关联资讯 |
| `data` | JSON | NOT NULL | 完整行数据（待审批） |
| `editor_id` | BIGINT | FK → users.id | 编辑者 |
| `created_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| `updated_at` | DATETIME | NOT NULL, ON UPDATE CURRENT_TIMESTAMP | 更新时间 |

### news_tags

| 字段        | 类型          | 约束                 | 说明  |
|-----------|-------------|--------------------|-----|
| `id`      | BIGINT      | PK, AUTO_INCREMENT | 主键  |
| `name_zh` | VARCHAR(30) | NOT NULL, UNIQUE   | 标签名 |

### news_tag_relations

| 字段        | 类型     | 约束                    | 说明 |
|-----------|--------|-----------------------|----|
| `news_id` | BIGINT | PK, FK → news.id      | 新闻 |
| `tag_id`  | BIGINT | PK, FK → news_tags.id | 标签 |

---

## 4. 机构推荐

### agency_categories

| 字段           | 类型          | 约束        | 说明                        |
|--------------|-------------|-----------|---------------------------|
| `id`         | VARCHAR(20) | PK        | 如 `law`、`accounting`、`hr` |
| `label_zh`   | VARCHAR(50) | NOT NULL  | 中文名                       |
| `icon_name`  | VARCHAR(30) |           | Lucide 图标名                |
| `sort_order` | INT         | DEFAULT 0 | 排序                        |

### agency_scenes

| 字段            | 类型          | 约束                                  | 说明                       |
|---------------|-------------|-------------------------------------|--------------------------|
| `id`          | VARCHAR(30) | PK                                  | 如 `law-labor`、`acct-tax` |
| `category_id` | VARCHAR(20) | FK → agency_categories.id, NOT NULL | 所属大类                     |
| `label_zh`    | VARCHAR(50) | NOT NULL                            | 中文名                      |
| `sort_order`  | INT         | DEFAULT 0                           | 排序                       |

### agencies

| 字段           | 类型           | 约束                              | 说明     |
|--------------|--------------|---------------------------------|--------|
| `id`         | BIGINT       | PK, AUTO_INCREMENT              | 主键     |
| `name`       | VARCHAR(200) | NOT NULL                        | 机构名称  |
| `scene_id`   | VARCHAR(30)  | FK → agency_scenes.id, NOT NULL | 所属场景   |
| `region`     | VARCHAR(300) |                                 | 覆盖区域   |
| `phone`      | VARCHAR(50)  |                                 | 联系电话   |
| `email`      | VARCHAR(200) |                                 | 联系邮箱   |
| `business`   | TEXT         |                                 | 主攻业务描述 |
| `advantage`  | TEXT         |                                 | 核心优势描述 |
| `highlight`  | VARCHAR(50)  |                                 | 亮点标签   |
| `sort_order` | INT          | DEFAULT 0                       | 排序     |
| `status`     | ENUM('draft','published') | NOT NULL, DEFAULT 'published'       | 发布状态   |
| `created_at` | DATETIME     | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 创建时间   |
| `updated_at` | DATETIME     | NOT NULL, ON UPDATE CURRENT_TIMESTAMP | 更新时间   |

### agencies_drafts

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BIGINT | PK, AUTO_INCREMENT | 主键 |
| `agency_id` | BIGINT | UNIQUE, FK → agencies.id ON DELETE CASCADE | 关联机构 |
| `data` | JSON | NOT NULL | 完整行数据（待审批） |
| `editor_id` | BIGINT | FK → users.id | 编辑者 |
| `created_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| `updated_at` | DATETIME | NOT NULL, ON UPDATE CURRENT_TIMESTAMP | 更新时间 |

---

## 5. 平台统计

### platform_stats（VIEW）

> 数据库视图，实时统计各表行数，无需写入数据。

```sql
CREATE OR REPLACE VIEW platform_stats AS
SELECT 'countries' AS id, CAST(COUNT(*) AS CHAR) AS value, '覆盖国家（持续拓展中）' AS label_zh, 1 AS sort_order FROM countries
UNION ALL SELECT 'laws', CAST(COUNT(*) AS CHAR), '法规条文收录', 2 FROM laws
UNION ALL SELECT 'scenes', CAST(COUNT(*) AS CHAR), '高频合规场景', 3 FROM compliance_scenes
UNION ALL SELECT 'agencies', CAST(COUNT(*) AS CHAR), '合作合规机构', 4 FROM agencies
```

---

## 6. 正文存储

### news_text

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `news_id` | BIGINT | PK, FK → news.id ON DELETE CASCADE | 关联资讯 |
| `content` | MEDIUMTEXT | NOT NULL | 正文内容（上限 16MB） |
| `created_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| `updated_at` | DATETIME | NOT NULL, ON UPDATE CURRENT_TIMESTAMP | 更新时间 |

---

## ER 关系概览

```
users ──< diagnosis_records ── diagnosis_results
                  │
countries ──< laws
laws ── laws_drafts >── users
countries ──< news
news >── news_tag_relations ──< news_tags
news ── news_text
news ── news_drafts >── users

agency_categories ──< agency_scenes ──< agencies
agencies ── agencies_drafts >── users
```
