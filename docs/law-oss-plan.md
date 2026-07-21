# 法律原件迁移 OSS 与 Draft 生命周期改造计划

## 1. 目标与核心设计

将法律原件从本地 `uploads/laws/` 迁移到独立的知识库 OSS Bucket。数据库只保存正式 OSS 对象名；待审核、挂起状态的文件保存在 `<UPLOAD_PATH>/tmp/laws/`，批准后才进入 OSS。

核心约束：

- `laws.status` 仅表示发布状态：`draft` 或 `published`。
- 已发布法规的 editor 修改只写入 `laws_drafts`，主表和旧 OSS 对象继续生效。
- `laws_drafts` 是否存在表示待审核修改，避免再用主表 `status` 表示审核状态。
- 文件可以为空，因此允许 `published` 法规没有 `object_name`。
- 不限制扩展名类型和文件大小；仍受 Flask 当前约 105 MB 请求上限约束，但文件必须带后缀。
- 知识库同步延迟与解析状态不在本次范围内；OSS PUT/DELETE 成功即视为新增/删除完成。

## 2. 表结构、配置与 API

### 数据库最终结构

`laws`：

- 删除 `filename`。
- 将 `secure_name` 重命名为 `pending_file_name VARCHAR(500) NULL`，仅保存 `<UPLOAD_PATH>/tmp/laws/` 中的 UUID 文件名。
- 新增 `object_name VARCHAR(500) NULL`，保存正式 OSS key。
- 为 `object_name` 添加唯一约束；NULL 可以重复。

`laws_drafts`：

- 新增 `pending_file_name VARCHAR(500) NULL`。
- `data` JSON 只保存待审业务字段，不再保存 `filename`、`secure_name`、`object_name` 或临时路径。

### Object Name 生成规则

统一实现一个生成函数：

```text
<title_cn>[-<title_en>]<lowercase-extension>
```

例如：

```text
《南非海关管理法》-South Africa Customs Act.pdf
《加纳劳动法》.pdf
```

规则：

- `title_cn.strip()` 必须非空。
- `title_en` 为空或仅空白时，连同前置 `-` 一起省略。
- 保留 Unicode 标题，进行 NFC 规范化，不使用 `secure_filename`，避免中文丢失。
- 拒绝包含控制字符、`/`、`\` 的标题。
- 后缀取上传文件最后一个扩展名并转小写；无后缀返回 400，并明确提示前端。
- 最终名称不得超过数据库 500 字符或 OSS 1023 UTF-8 字节限制。
- 数据库或 OSS 已存在同名对象且不属于当前 Law 时返回 409，不追加 ID、不覆盖其他法规。

### 配置

在 `config.py` 和 `.env.example` 增加：

```dotenv
LAW_OSS_BUCKET_NAME=your-law-knowledge-base-bucket
```

继续共用：

- `ALIBABA_CLOUD_ACCESS_KEY_ID`
- `ALIBABA_CLOUD_ACCESS_KEY_SECRET`
- `OSS_REGION`
- `OSS_ENDPOINT`
- `OSS_SIGN_URL_EXPIRES`

现有 `OSS_BUCKET_NAME` 继续供合规报告使用，不得被法律库配置替代。

### API 变化

- Admin Law 响应删除 `filename`，增加：
  - `object_name`：当前正式 OSS key。
  - `has_file`：是否存在正式或待审文件。
  - `has_draft`：是否存在 `LawDraft`。
  - `review_status`：`pending` 或 `none`。
  - `has_pending_file`。
  - `pending_object_name`：根据待审标题和文件后缀计算的目标名称。
- 绝不返回 `pending_file_name` 或本地绝对路径。
- Admin 列表新增 `review_status=pending|none`；原 `status` 仍只筛选发布状态。
- `GET /api/laws/{id}/download` 保持原路径，校验 published 和对象存在后返回 302，重定向至法律 Bucket 的签名 URL。
- Law 批量审核改为逐条事务，HTTP 200 返回：
  - `approved: [id...]`
  - `failed: [{id, code, message}...]`
- 新增 admin-only `DELETE /api/admin/laws/{id}/draft`，丢弃 editor 待审修改并删除对应临时文件，保留线上主版本。
- 已存在 LawDraft 时，admin 直接 PUT 主版本返回 409，要求先 approve 或 discard。

## 3. 文件与 Draft 生命周期

将 Laws 文件逻辑从通用 `admin_service` 中拆到专用 Law service；路由只负责解析 multipart、权限和响应。扩展 OSS 工具以显式选择法律 Bucket，并让 upload/copy/delete/download/head 返回状态或抛出明确异常，不能继续吞掉所有异常返回 `False`。

### 创建

- 所有上传先写入 `<UPLOAD_PATH>/tmp/laws/<uuid><ext>`。
- Admin 创建：
  - 无文件：直接创建 published、`object_name=NULL`。
  - 有文件：生成并检查 object name，上传成功且状态 200 后写数据库；数据库失败则删除刚上传对象；最终删除临时文件。
- Editor 创建：
  - 创建 `status=draft` 的 Law。
  - 文件只写 `laws.pending_file_name`，不操作 OSS。
  - 数据库失败时清理临时文件。

### 修改

- 使用数据库行锁防止同一法规并发重命名、替换或审核。
- Admin 修改 published：
  - 仅普通元数据变化：直接提交数据库。
  - 仅名称变化且有正式文件：`copy_object(old, new)` 成功后删除旧对象，再提交新 `object_name`；任一步失败执行反向补偿。
  - 替换文件且 object name 改变：保存新临时文件，上传新对象，删除旧对象，再提交数据库；失败时恢复旧对象并删除新对象。
  - 替换文件且 object name 不变：先把旧对象下载到本地回滚临时文件，再直接 PUT 覆盖；数据库失败则重新上传旧文件恢复。
- Admin 修改 draft：只更新主表草稿和 `pending_file_name`，不发布、不操作 OSS，必须显式 approve。
- Editor 修改 published：
  - 主表保持 published。
  - 业务字段写入或更新 `LawDraft.data`。
  - 新文件写入 `LawDraft.pending_file_name`；替换旧待审文件时，数据库提交成功后清理旧临时文件。
- Editor 修改未发布 draft：直接更新 Law 和 `Law.pending_file_name`，保持 draft。

### 审核、挂起与删除

- Approve：
  - 合并 draft 业务数据。
  - 有待审文件时上传新原件；名称变化但无新文件时执行 OSS copy+delete。
  - OSS 操作全部成功后更新主表、清空 pending 字段、删除 LawDraft、设为 published。
  - 数据库提交成功后清理待审临时文件。
- Batch approve：对每个 ID调用完整单条 approve，各自提交；一项失败不回滚已成功项。
- Suspend：
  - 丢弃已有 LawDraft 及其待审文件。
  - 有正式对象时先下载到本地 UUID 临时文件并校验，再删除 OSS 对象。
  - 数据库改为 draft、`object_name=NULL`、设置 `pending_file_name`；提交失败则重新上传恢复旧对象。
- Delete：
  - draft：删除数据库记录及所有被引用的本地临时文件。
  - published：先下载回滚副本，再删除 OSS，随后删除数据库记录；数据库失败则重新上传恢复。
  - OSS 删除失败时数据库不得删除。
- 所有 OSS 错误使用统一 `OSS_ERROR`/502；名称冲突为 409；标题或后缀错误为 400。

## 4. 存量迁移与双向孤儿检查

### 版本化 DDL

项目没有 Alembic，应新增版本化 SQL 迁移目录，并调整 `.gitignore` 允许提交该目录中的 SQL。

分为两步：

1. Expand migration：
   - 新增 `laws.object_name`。
   - 重命名 `secure_name` 为 `pending_file_name`。
   - 新增 `laws_drafts.pending_file_name`。
   - 暂时保留 `filename`，不立即增加唯一索引。
2. Contract migration：
   - 数据迁移验证通过后删除 `filename`。
   - 添加 `object_name` 唯一索引。

### 双向本地孤儿检查

改造 `bits/check-dangling.py`，保持只读，不检查或删除 OSS。

Legacy 模式检查：

- 数据库引用集合：
  - `laws.secure_name`
  - `laws_drafts.data.secure_name`
- 本地集合：`<UPLOAD_PATH>/laws/` 下所有普通文件。
- 输出：
  - `missing_local`：数据库引用存在，但本地文件缺失。
  - `unreferenced_local`：本地文件存在，但数据库未引用。
  - `duplicate_references`：同一本地文件被多个 Law/Draft 引用。
  - `unsafe_references`：引用不是纯 basename 或存在路径穿越。

新结构模式检查：

- 引用集合改为 `laws.pending_file_name` 和 `laws_drafts.pending_file_name`。
- 检查目录改为 `<UPLOAD_PATH>/tmp/laws/`。
- 另外将残留在旧 `uploads/laws/` 的文件列为 `legacy_local_files`，供迁移清理阶段核对。

工具自动检测当前表字段选择模式，支持 human/JSON 输出；一致时退出码 0，发现差异为 1，配置或数据库错误为 2。它永远不自动删除文件。

### 数据迁移脚本

新增可恢复、幂等的 Laws OSS 迁移脚本，提供：

```text
preflight
apply --batch-size 50
verify
cleanup-local
```

流程：

1. 后端保持关闭，备份数据库和 `uploads/laws/`。
2. 先运行 legacy 双向检查；数据库缺失文件必须解决，未引用本地文件只报告且不上传。
3. 执行 expand DDL。
4. `preflight`：
   - 读取所有 Law/LawDraft。
   - 生成目标 object name。
   - 检查缺失文件、无后缀、非法标题、对象名冲突和 OSS 已有对象。
   - 写 JSONL manifest，记录 law_id、源路径、目标 key、大小、状态和错误。
5. `apply`：
   - published 且无 LawDraft：上传正式对象，批量设置 `object_name` 并清空 `pending_file_name`。
   - status=draft 且存在 LawDraft：视为旧实现中的“已发布但待审”，上传主版本、恢复主表 published；将 draft 中不同于主文件的 `secure_name` 移至 tmp 并写入 `LawDraft.pending_file_name`。
   - draft 且无 LawDraft：不上传 OSS，将文件移入 tmp，继续作为待审文件。
   - 从 draft JSON 删除旧的 `filename`、`secure_name`、`object_name` 键。
   - 每批数据库提交状态写回 manifest；上传成功但数据库未提交的记录可安全续跑。
6. `verify`：
   - 对每个迁移成功的 published 对象执行 HEAD，核对存在性和长度。
   - 核对 DB `object_name`、manifest 与 OSS key 一致。
7. 执行 contract DDL并部署新代码。
8. `cleanup-local` 只删除 manifest 中已上传、已提交且已验证的旧本地源文件；不删除孤儿文件、失败记录或 draft pending 文件。

## 5. 测试与验收

实现测试但不运行任何 Python 命令，由用户在指定 Conda 环境验证。

必须覆盖：

- 中英文、仅中文、空英文、Unicode、非法分隔符、无后缀和重名 object name。
- Admin/editor 创建有文件和无文件法规。
- Editor 修改 published 后，公开 API 仍返回旧主版本，OSS 旧对象保持不变。
- Admin 同 key 文件覆盖、跨 key 替换、纯名称 copy+delete及各阶段失败补偿。
- Approve、逐条 batch approve、discard draft、suspend 后恢复、删除 published/draft。
- OSS 返回非 200/204、数据库提交失败、临时文件保存失败和并发更新。
- 下载接口 302、无对象法规 404、OSS 对象缺失错误。
- Legacy/new-schema 双向孤儿检查，包括数据库缺文件、本地无用文件、Draft 引用和重复引用。
- 迁移脚本 preflight 不写数据、apply 可中断续跑、verify 可发现缺失对象、cleanup 不误删孤儿或待审文件。
- 更新 `docs/api.md`、`docs/db.md`、README 和 `.env.example`，明确新字段、状态语义、迁移顺序及回滚步骤。

### 已锁定假设

- 法律 Bucket 使用现有 AK、Region、Endpoint，仅 bucket name 独立。
- Bucket 根目录直接存放法规对象，不增加前缀。
- OSS 与数据库无法形成真正分布式事务，采用行锁、严格状态检查和本地回滚副本实现尽力一致性。
- 不实现知识库同步状态轮询，也不在孤儿检查工具中枚举 OSS。
- 当前约 106 个本地文件、247 MB；疑似未被数据库引用的文件必须由新版检查工具准确列出后人工处理。
