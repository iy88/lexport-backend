# 合规报告异步生成 API

## 总体方案

- 新增 `/api/compliance-reports` Blueprint、service、OSS 封装及 Celery 任务。
- MySQL 是任务状态的唯一真相源；Redis 仅作为 Celery broker 和轮询互斥锁，不保存 active task 清单。
- Celery Beat 定期扫描非终态记录并分发短轮询任务；worker 每次仅调用一次 `responses.retrieve()`，不在进程中长时间 `sleep`。该模式符合百炼 `background=True` + Task ID 查询机制，也避免长期占用 worker。[百炼异步调用文档](https://help.aliyun.com/en/model-studio/asynchronous-call-api-reference)
- 在现有未提交改动上继续工作，不覆盖诊断模型、数据库文档等已有修改。

## 创建与异步处理

- `POST /api/compliance-reports` 要求 JWT，接收 `multipart/form-data`：
  `query`、`company_name`、`industry`、`company_size`、`target_country`、`business_model`、`budget_range` 均为必填文本；`documents` 为可重复的可选文件字段。
- 最多 5 个文件、每个 20MB，仅允许 PDF、DOC、DOCX、TXT、HTML。文件先保存至 `<UPLOAD_PATH>/tmp/<uuid>.<ext>`，保留原始文件名用于元数据。
- 使用 secure name 作为 OSS object name。全部上传返回 `status == 200` 后才继续；任一上传失败则删除所有本地临时文件，返回 `OSS_UPLOAD_FAILED`，不查询机构、不创建百炼任务、不写数据库。已上传 OSS 对象由 Bucket 生命周期清理。
- 全部上传成功后生成有效期 7200 秒的签名 URL，并以 `documents: [{"url": "..."}]` 传入 workflow。
- 使用 `Agency.region.contains(target_country)` 查询已发布机构，按原型格式生成 `relative_agency`；无匹配时传空字符串。
- 调用同步 OpenAI 客户端的 `responses.create(input=query, background=True, extra_body={"biz_params": ...})`。创建失败返回 502；成功后写入记录并返回 202。
- `DiagnosisRecord.param` 保存原生 JSON 对象，结构为 `{input, biz_params}`，包括签名 URL 和 `relative_agency`，绝不使用 `json.dumps()` 二次编码。

## 模型、轮询与查询接口

- 完成 `DiagnosisRecord` 模型：`task_id` 唯一并索引，`status` 建索引，`param` 使用非空 `db.JSON`；保留国家、规模、预算和业务模式等元数据列。
- 完成一对一 `DiagnosisResult` 模型：`result` 使用非空 `db.JSON`，完整保存 `response.model_dump()` 的 JSON 数据；关联记录删除时级联删除。
- 更新 `docs/db.md`，注明现有数据库需要添加任务字段、JSON 字段及索引；不依赖 `db.create_all()` 修改旧表。
- Celery Beat 每 10 秒批量扫描非 `completed/failed/cancelled` 记录，通过 Redis 短锁避免重复轮询。瞬时网络错误留待下一轮；超过 2 小时仍无终态则标记 `failed`。
- `completed` 时在同一事务中更新状态并写入完整结果；`failed/cancelled` 只更新记录，不创建空结果。
- `GET /api/compliance-reports?page=1&per_page=20` 返回 `id`、业务元数据、文档数量、状态和创建时间，按时间倒序分页。
- `GET /api/compliance-reports/{id}` 返回同一组元数据、状态和从完整 Response `output` 中提取的 `result_text`；未完成或失败时为 `null`。
- 普通用户只能访问自己的记录；管理员可访问全部记录。无权限时按不存在处理并返回 404。

## 配置、部署与文档

- `.env.example` 新增：
  `ALIBABA_CLOUD_ACCESS_KEY_ID`、`ALIBABA_CLOUD_ACCESS_KEY_SECRET`、`OSS_REGION`、`OSS_ENDPOINT`、`OSS_BUCKET_NAME`、`OSS_SIGN_URL_EXPIRES=7200`、`BAILIAN_API_KEY`、`REPORT_GENERATOR_APPID`、`REPORT_AI_VERSION`、`REPORT_DATA_CUTOFF_DATE`、`REDIS_URL`、`REPORT_POLL_INTERVAL_SECONDS=10`、`REPORT_TASK_TIMEOUT_SECONDS=7200`。
- Redis 任务依赖使用 `celery[redis]`；运行环境需提供兼容版本的 `openai` 和 `oss2`。
- 提供 worker 与单实例 beat 启动命令：
  `celery -A celery_app:celery_app worker --loglevel=INFO`
  和 `celery -A celery_app:celery_app beat --loglevel=INFO`。Celery 官方支持 Redis broker、定时调度和任务重试。[Celery 调度文档](https://docs.celeryq.dev/en/stable/userguide/tasks.html)
- 更新 `docs/api.md`，包含 form-data 示例、202 响应、分页/详情结构和错误码。

## 验收场景

- 验证无文件、单文件及五文件创建均返回 202，并保存原生 JSON 参数。
- 验证缺少字段、非法扩展名、超限文件分别返回 400/413，且无任务和数据库记录。
- 模拟第二个文件 OSS 上传失败，确认本地临时文件全部移除且不调用百炼。
- 模拟 `in_progress → completed`，确认只产生一条结果且保存完整响应；模拟 `failed/cancelled`，确认没有结果行。
- 重启 worker/Redis 后确认数据库中的进行中记录会被 Beat 重新发现。
- 验证普通用户隔离、管理员访问、分页顺序及详情 `result_text` 提取。
- 按用户要求，实施方不安装依赖或运行验证，由用户在配置好的 MySQL、Redis、OSS 和百炼环境中执行以上验收。
