# 数据库设计

> 基于需求文档 (`data.md`) 设计，使用 MySQL + SQLAlchemy ORM。

---

## 1. 用户

### users

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BIGINT | PK, AUTO_INCREMENT | 主键 |
| `username` | VARCHAR(50) | UNIQUE, NOT NULL, INDEX | 用户名 |
| `password_hash` | VARCHAR(255) | NOT NULL | 密码哈希（bcrypt） |
| `email` | VARCHAR(255) | NULLABLE, UNIQUE, INDEX | 邮箱 |
| `email_verified` | BOOLEAN | NOT NULL, DEFAULT FALSE | 邮箱是否已验证 |
| `role` | ENUM('user','admin') | NOT NULL, DEFAULT 'user' | 角色 |
| `created_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 创建时间 |
| `updated_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP | 更新时间 |

---

## 2. 法规库

### countries

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | VARCHAR(10) | PK | 国家代码，如 `ZA`、`NG` |
| `name_zh` | VARCHAR(50) | NOT NULL | 中文名，如「南非」 |
| `name_en` | VARCHAR(100) | | 英文名 |
| `sort_order` | INT | DEFAULT 0 | 排序 |

### compliance_scenes

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | VARCHAR(20) | PK | 场景代码，如 `customs`、`labor` |
| `label_zh` | VARCHAR(30) | NOT NULL | 中文名，如「海关进出口」 |
| `icon_name` | VARCHAR(30) | | Lucide 图标名 |
| `sort_order` | INT | DEFAULT 0 | 排序 |

### laws

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BIGINT | PK, AUTO_INCREMENT | 主键 |
| `title` | VARCHAR(300) | NOT NULL | 法规标题 |
| `country_id` | VARCHAR(10) | FK → countries.id, NOT NULL | 所属国家 |
| `scene_id` | VARCHAR(20) | FK → compliance_scenes.id, NOT NULL | 适用场景 |
| `level` | VARCHAR(30) | | 效力层级 |
| `penalty` | TEXT | | 处罚条款描述 |
| `effective_date` | DATE | | 生效/修订日期 |
| `summary` | TEXT | | 法规要点摘要 |
| `full_text_url` | VARCHAR(500) | | 法规原文链接 |
| `created_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 创建时间 |

### company_sizes

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | VARCHAR(20) | PK | 如 `micro`、`small`、`medium`、`large` |
| `label_zh` | VARCHAR(50) | NOT NULL | 中文标签 |
| `min_employees` | INT | | 人数下限 |
| `max_employees` | INT | | 人数上限 |
| `sort_order` | INT | DEFAULT 0 | 排序 |

### budget_ranges

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | VARCHAR(20) | PK | 如 `lt100k`、`100k-500k` |
| `label_zh` | VARCHAR(50) | NOT NULL | 中文标签 |
| `min_amount` | INT | | 金额下限（万元） |
| `max_amount` | INT | | 金额上限（万元） |
| `sort_order` | INT | DEFAULT 0 | 排序 |

### diagnosis_records

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BIGINT | PK, AUTO_INCREMENT | 主键 |
| `user_id` | BIGINT | FK → users.id, NULLABLE | 操作用户 |
| `country_id` | VARCHAR(10) | FK → countries.id | 目的国 |
| `size_id` | VARCHAR(20) | FK → company_sizes.id | 企业规模 |
| `budget_id` | VARCHAR(20) | FK → budget_ranges.id | 预算区间 |
| `created_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 生成时间 |

### diagnosis_record_scenes

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `record_id` | BIGINT | PK, FK → diagnosis_records.id | 诊断记录 |
| `scene_id` | VARCHAR(20) | PK, FK → compliance_scenes.id | 选择的场景 |

### diagnosis_record_laws

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `record_id` | BIGINT | PK, FK → diagnosis_records.id | 诊断记录 |
| `law_id` | BIGINT | PK, FK → laws.id | 匹配到的法规 |

---

## 3. 资讯库

### news

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BIGINT | PK, AUTO_INCREMENT | 主键 |
| `type` | ENUM('cooperation','hotspot','update') | NOT NULL | 新闻类型 |
| `title` | VARCHAR(300) | NOT NULL | 标题 |
| `source` | VARCHAR(200) | | 来源 |
| `country_id` | VARCHAR(10) | FK → countries.id | 关联国家 |
| `date` | DATE | NOT NULL | 发布日期 |
| `summary` | TEXT | | 摘要 |
| `risk_level` | ENUM('high','medium','low') | | 风险等级 |
| `involved_laws` | TEXT | | 涉事法规 |
| `response` | TEXT | | 应对建议 |
| `update_type` | ENUM('修订','新增','废止') | | 更新类型 |
| `change_desc` | TEXT | | 核心更新内容 |
| `impact` | TEXT | | 对企业影响 |
| `advice` | TEXT | | 合规建议 |
| `created_at` | DATETIME | NOT NULL, DEFAULT CURRENT_TIMESTAMP | 创建时间 |

### news_tags

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BIGINT | PK, AUTO_INCREMENT | 主键 |
| `name_zh` | VARCHAR(30) | NOT NULL, UNIQUE | 标签名 |

### news_tag_relations

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `news_id` | BIGINT | PK, FK → news.id | 新闻 |
| `tag_id` | BIGINT | PK, FK → news_tags.id | 标签 |

---

## 4. 机构推荐

### agency_categories

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | VARCHAR(20) | PK | 如 `law`、`accounting`、`hr` |
| `label_zh` | VARCHAR(50) | NOT NULL | 中文名 |
| `icon_name` | VARCHAR(30) | | Lucide 图标名 |
| `sort_order` | INT | DEFAULT 0 | 排序 |

### agency_scenes

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | VARCHAR(30) | PK | 如 `law-labor`、`acct-tax` |
| `category_id` | VARCHAR(20) | FK → agency_categories.id, NOT NULL | 所属大类 |
| `label_zh` | VARCHAR(50) | NOT NULL | 中文名 |
| `sort_order` | INT | DEFAULT 0 | 排序 |

### agencies

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | BIGINT | PK, AUTO_INCREMENT | 主键 |
| `name_zh` | VARCHAR(200) | NOT NULL | 机构中文名 |
| `scene_id` | VARCHAR(30) | FK → agency_scenes.id, NOT NULL | 所属场景 |
| `region` | VARCHAR(300) | | 覆盖区域 |
| `phone` | VARCHAR(50) | | 联系电话 |
| `email` | VARCHAR(200) | | 联系邮箱 |
| `business` | TEXT | | 主攻业务描述 |
| `advantage` | TEXT | | 核心优势描述 |
| `highlight` | VARCHAR(50) | | 亮点标签 |
| `sort_order` | INT | DEFAULT 0 | 排序 |

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

## ER 关系概览

```
users ──< diagnosis_records >── diagnosis_record_scenes ──< compliance_scenes
                  │
                  └── diagnosis_record_laws ──< laws
                  │
countries ──< laws
countries ──< news
news >── news_tag_relations ──< news_tags

agency_categories ──< agency_scenes ──< agencies
```
