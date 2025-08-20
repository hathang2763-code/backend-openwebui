# 迁移进度盘点与执行计划（截至当前）

以下为对当前仓库中 `backend` → `backend-openwebui` 迁移整合工作的实地盘点与评估，包含：已完成、差距与风险、下一步可执行计划。评估基于代码与配置的实际状态。

## 一、当前进度
- 路由接入：在 `backend-openwebui/open_webui/main.py` 已注册迁移路由
  - `analysis_migrated` 与 `cases_migrated`：`app.include_router(…, prefix="/api/v1/analysis|cases")` 已生效。
- 案例（Cases）骨架：
  - 模型与表：`open_webui/models/cases.py` 定义了 `Case/CaseNode/CaseEdge` 与 Pydantic 模型；Alembic 增量脚本已加入 `open_webui/migrations/versions/8f3d0a2b1c34_add_cases_tables.py`，`open_webui/config.py` 中 `run_migrations()` 启动时执行。
  - 路由功能：`open_webui/routers/cases_migrated.py` 已实现基础 CRUD 与图谱读写（列举/创建/详情/更新/新增节点/新增边/删节点/删边）。
- 智能分析（Analysis）初版：
  - 路由：`open_webui/routers/analysis_migrated.py` 提供 `POST /api/v1/analysis/log-parsing`，含轻量规则解析与“相关知识”检索（对接 Open WebUI 嵌入与向量库工厂）。
- 向量库扩展（Weaviate）：
  - 工厂接入：`open_webui/retrieval/vector/type.py` 新增 `WEAVIATE`，`open_webui/retrieval/vector/factory.py` 已接入。
  - 适配器：`open_webui/retrieval/vector/dbs/weaviate.py` 实现 v4/v3 客户端兼容（建表、upsert、search、query、delete、reset）。
  - 配置与依赖：`open_webui/config.py` 新增 `WEAVIATE_URL/WEAVIATE_COLLECTION_PREFIX`；`requirements.txt` 已加入 `weaviate-client`。
- 文档智能解析（阿里 IDP）与语义分块：
  - Loader：`open_webui/retrieval/loaders/alibaba_idp.py`；服务：`open_webui/services/ali_idp.py`、`open_webui/services/semantic_splitter.py`；在 `open_webui/retrieval/loaders/main.py` 通过 `CONTENT_EXTRACTION_ENGINE=alibaba_idp` 驱动。
  - 依赖：`requirements.txt` 已加入 `alibabacloud_*` 组件。
- 基线能力共用：已复用 Open WebUI 现成的 `auths/users/files/knowledge/retrieval/...` 路由与配置体系，迁移工作围绕新增能力扩展而非重写基座。

### 进度更新（2025.8.19）
- 案例（Cases）接口补全：
  - 新增：`DELETE /api/v1/cases/{id}`（连带删除节点/边）
  - 新增：`POST /api/v1/cases/{case_id}/nodes/{node_id}/rate`（节点评价，写入节点 metadata）
  - 新增：`POST /api/v1/cases/{case_id}/interactions`（生成用户补充信息与AI处理节点，并建边）
  - 新增：`PUT /api/v1/cases/{case_id}/feedback`、`GET /api/v1/cases/{case_id}/feedback`（复用通用反馈表）
  - 新增：`GET /api/v1/cases/{case_id}/nodes`、`GET /api/v1/cases/{case_id}/edges`、`GET /api/v1/cases/{case_id}/nodes/{node_id}`（节点/边列表与节点详情）
  - 新增：`GET /api/v1/cases/{case_id}/nodes/{node_id}/knowledge`（节点知识溯源，向量检索+分数归一）
  - 新增：`PUT /api/v1/cases/{case_id}/layout`、`GET /api/v1/cases/{case_id}/layout`（画布布局保存/读取，落盘于 Case.metadata）
  - 新增：`POST /api/v1/cases/`（创建案例时同步创建 `USER_QUERY` 与 `AI_ANALYSIS` 初始节点并建立边；将 `attachments` 挂在 `USER_QUERY` 节点的 `content` 中）
  - 新增：`PUT /api/v1/cases/{case_id}/nodes/{node_id}`（节点更新：标题/状态/内容/元数据）
  - 新增：`GET /api/v1/cases/{case_id}/status`（案例状态轮询：返回 PROCESSING 与 AWAITING_USER_INPUT 节点）
  - 新增：`GET /api/v1/cases/{case_id}/nodes/{node_id}/commands`（接入 `open_webui/services/vendor_command_service.py`，按节点内容+厂商返回命令建议，支持 context 占位替换）
  - 新增：`GET /api/v1/cases/{case_id}/stats`（节点/边统计信息）
  - 升级：`POST /api/v1/cases/{case_id}/nodes/{node_id}/regenerate`（调用 Open WebUI 通用模型接口 `generate_chat_completion` 完成真实再生成功能；默认非流式，直接落库并返回）
  - 兼容路由：新增 `system_migrated`
    - `GET /api/v1/system/health`、`GET /api/v1/system/statistics`（最小健康检查与统计）
  - 用户设置已统一回用原生端点：`GET /api/v1/users/user/settings`、`POST /api/v1/users/user/settings/update`
- 数据结构：
  - `Case` 增加 `metadata` JSON 字段（Alembic 迁移：`b1c2d3e4f5a6_add_case_metadata.py`）
- 分析（Analysis）：
  - 统一相似度分值：针对 Weaviate 距离做归一，与其他后端统一输出 `score` 并按降序排序。

## 二、差距与风险（未完成/需完善）
- 案例（Cases）能力缺口：
  - 交互流与反馈：已补 `interactions`/`rate_node`/`feedback`；后续可完善节点再生成、建议命令、状态轮询等。
  - 附件与统计：创建案例时的 `attachments` 已记录于首个 `USER_QUERY` 节点 `content` 中，但尚未与 `files` 路由建立强关联；列表统计信息已提供按案例的统计接口，但全局/分页聚合仍待补。
  - 权限与审计：当前以用户归属粗粒度校验，尚未与 Open WebUI 的细粒度访问控制/审计打通。
- 智能分析（Analysis）能力差距：
  - 规则/服务化：当前为轻量规则解析，尚未对齐 `backend/app/services/ai/log_parsing_service.py` 的完整规则、指标与建议模板；也未提供“文本+附件→IDP→分块→检索”全链路模式。
  - 相似度排序一致性：`analysis_migrated.py` 聚合相关知识时对不同向量库的“分数/距离”未做统一归一，Weaviate 距离越小越相似，而代码统一按降序排序，存在排序偏差风险。
- 数据迁移与兼容：
  - 历史数据：尚无从 `backend`（Flask）到 Open WebUI 的数据迁移脚本（案例/节点/边/反馈/知识文档等）。
  - Token/认证：未提供旧 Token 兼容策略（如需平滑迁移）。
- 其它未迁移模块：
  - `development`、`notifications`、`system`（健康/统计/任务监控）等在 `backend` 中的接口尚未评估接入；需要与 Open WebUI 既有 `/api/v1/tasks` 等能力对齐或裁剪。
- 测试与质量：
  - 尚无针对新增适配器/路由的单元测试与契约测试；缺 E2E 路径（上传→入库→检索→分析/案例）的回归用例。

## 三、下一步执行计划（按优先级）
1) 案例功能补全（收尾）
   - 路由：将再生成扩展为可选异步任务与状态回传（复用 `open_webui/tasks.py`），并提供停止/查询接口；完善列表维度的统计聚合接口。
   - 数据：在 `Case/CaseNode/CaseEdge` 基础上扩展标签/统计等字段（如需要，补迁移）。
   - 附件：与 `files` 路由打通，建立附件与案例/节点的关联（多对多或元数据映射）。

2) 智能分析增强
   - 抽象服务：将 `analysis_migrated.py` 解析逻辑上移为 `services/log_parsing_service.py` 风格组件，迁入完整规则库与建议模板；增强异常指标与摘要生成。
   - 全链路：新增文本+附件处理路径，调用 `AlibabaIDPLoader` → `SemanticSplitter` → 向量入库/检索，输出结构化结果与相关知识。
   - 相似度统一：对不同向量库的 `score/distance` 做规范化（例如统一为相似度分值），修正排序逻辑，确保结果一致性。

3) 检索与配置稳固
   - Weaviate 适配验证：在不同嵌入维度/度量（cosine/L2）下回归检索正确性与性能，补充失败容错与降级策略。
   - 配置开关：完善 `open_webui/config.py` 中 Weaviate/IDP 相关开关文档与默认值校验；在 README 增补配置示例。

4) 数据与认证迁移
   - 脚本：提供 `scripts/migrate_backend_data.py`（一次性 ETL），迁移 `backend` 的案例与知识数据到 Open WebUI 模型。
   - Token 兼容（可选）：在迁移期提供旧 Token→新体系的过渡解析（或文档化网关转换方案）。

5) 测试与验收
   - 单测：覆盖 `weaviate.py`、`alibaba_idp.py/semantic_splitter.py`、`cases_migrated.py`、`analysis_migrated.py` 关键路径。
   - 契约测试：对 `/api/v1/files|knowledge|retrieval|cases|analysis` 编写请求-响应契约用例（鉴权/分页/错误码）。
   - E2E：构造上传→入库→检索→分析/案例→反馈的端到端用例。

6) 文档与运维
   - README：在 `backend-openwebui/README.md` 增补典型部署/环境变量清单与迁移指引。
   - 监控：接入基础健康检查/审计日志（复用 Open WebUI 中间件），在后续阶段考虑 OTEL。

7) 兼容路由（已初步打通）
   - `system`：健康与统计。
   - `user`：已统一到原生端点。
   - `knowledge`：统一通过原生检索/上传管线并配置 `CONTENT_EXTRACTION_ENGINE=alibaba_idp` 使用阿里IDP。

---

下方为原有的总体技术计划，保留以供参考。

# 将 `backend` 逻辑与 API 迁移合并至 `backend-openwebui` 的技术计划

本文档面向在 `backend-openwebui`（FastAPI）为核心基底，将 `backend`（Flask/Flask-RESTX）中新增的功能、业务逻辑与接口对齐并合并的落地方案。目标是在尽可能复用现有能力的前提下，建立一条安全、可回滚、可验证的迁移路径。

## 1. 背景与目标
- 统一后端技术栈：以 `backend-openwebui` 的 FastAPI 为核心，整合接口、数据模型与中间件。
- 复用与增强：迁入 `backend` 的特色能力（Weaviate 检索、阿里文档智能、案例/智能分析流程）。
- 前端契约稳定：尽可能保持 Open WebUI 现有前端可用；对新增能力提供清晰、规范的 API。
- 渐进式落地：分阶段上线与回滚策略，保障现网稳定。

## 2. 现状评估（差异与风险）

### 2.1 技术栈与运行时
- `backend`：Flask + Flask-RESTX（同步）、JWT-Extended、RQ/Redis、LangChain、Weaviate。
- `backend-openwebui`：FastAPI（异步）、WebSocket/SSE、丰富路由与中间件、SQLAlchemy + Alembic（另有 Peewee 迁移兼容层）。

风险：同步/异步模型差异、流式/Socket 能力需要按需适配。

### 2.2 数据模型
- 两者均采用 SQLAlchemy（`backend-openwebui/open_webui/internal/db.py`），但表结构和字段定义不同；Open WebUI 已有 `users/files/knowledge/feedbacks/...` 等模型和 Alembic 迁移。
- `backend` 自有 `Case/Node/Edge`、`Feedback`、`KnowledgeDocument/ParsingJob` 等模型与语义。

风险：数据迁移/字段映射与双写兼容、回滚与历史数据一致性。

### 2.3 鉴权与权限
- `backend`：Flask-JWT-Extended（Bearer token），较轻量权限模型。
- `backend-openwebui`：`/api/v1/auths` 体系、API Key、OAuth/LDAP、权限粒度与访问控制更复杂（`get_verified_user`、cookie 设置等）。

风险：令牌与权限模型不一致，需统一或网关转换。

### 2.4 向量检索
- `backend` 聚焦 Weaviate（含本地文件向量 DB 兜底）。
- `backend-openwebui` 已有多向量后端工厂（Qdrant/PGVector/Milvus/Chroma/...），暂未包含 Weaviate 实现。

风险：若继续使用 Weaviate，需要补一类 `VectorType.WEAVIATE` 适配器；或做索引迁移重建。

### 2.5 API 面
- `backend`：`/api/v1` 下的 auth/user/files/knowledge/cases/analysis/notifications/system/development。
- `backend-openwebui`：`/api/v1` 下的 auths/users/files/knowledge/retrieval/chats/models/prompts/tools/groups/folders/channels/notes/tasks/openai/ollama 等，含 Socket。

风险：路径命名差异、响应结构差异、Pydantic v2 数据模型与校验。

## 3. 迁移总策略

优先采用“以 `backend-openwebui` 为主，迁入特色能力”的策略：
- 在 `backend-openwebui` 中新增或扩展 Router 与 Service，将 `backend` 的业务功能改写为 FastAPI 风格，统一使用 Open WebUI 的鉴权与模型。
- 保留/扩展 Open WebUI 的向量工厂与配置体系，新增 Weaviate 适配器（或迁移到已支持的向量存储并重建索引）。
- 对 `backend` 的 API 仅在确有前端依赖时提供“兼容路由/响应”，其余以 Open WebUI 规范为准，避免重复造轮子。

## 4. 分阶段里程碑
1) 最小可用（MVP，2–3 周）：
   - 鉴权对齐（沿用 Open WebUI 的 `/api/v1/auths`）。
   - 文件与知识库基本操作对齐（`/api/v1/files`、`/api/v1/knowledge`）。
   - Weaviate 适配或临时切换到现有向量后端并批量重建索引。
   - 新增“智能分析（analysis）”与“案例（cases）”基础 Router（不含复杂工作流）。

2) 能力完善（+2–3 周）：
   - 日志解析（阿里文档智能/语义分块等）整合为可配置 Loader/工具。
   - 案例图谱（Node/Edge）与反馈链路完善；权限/审计接入。
   - 最小 OpenAI 兼容推理闭环（如需）。

3) 深度对齐（按需，弹性）：
   - WebSocket/SSE 的对话/任务推送；高级检索（Hybrid/BM25/Rerank）。
   - 群组/频道/SCIM/管道/代码解释器等视需求分批接入或裁剪。

## 5. 详细迁移步骤

### 5.1 代码结构与目录规划
- 新增/扩展目录（建议）：
  - `open_webui/retrieval/vector/dbs/weaviate.py`：Weaviate 适配器
  - `open_webui/routers/cases_migrated.py`：案例路由（由 Flask 迁移）
  - `open_webui/routers/analysis_migrated.py`：智能分析路由
  - `open_webui/services/ali_idp.py`：阿里文档智能解析封装（由 `backend/app/services/document/*` 迁移）
  - `open_webui/services/semantic_splitter.py`：语义分块与清洗
  - `open_webui/models/cases.py`：Case/Node/Edge/Feedback（如与现有 `feedbacks.py` 冲突，需合并/引用）
  - `open_webui/migrations/versions/xxxx_add_cases_tables.py`：新增表迁移脚本
- 路由注册：在 `open_webui/main.py` 中 `app.include_router(...)` 注册上述新路由。

### 5.2 FastAPI/Pydantic 模型与路由迁移
- 将 Flask-RESTX 的 request/response 模型改写为 Pydantic v2 模型（`BaseModel`），字段命名与类型保持一致；分页统一使用 `{items,total,page,page_size}` 或 Open WebUI 既有响应风格。
- 将 Flask 的 `@jwt_required`/`get_jwt_identity` 改为 FastAPI 的依赖注入（`Depends(get_verified_user)` 等）。
- 错误与响应：统一使用 Open WebUI 的 `utils/response.py` 风格（或延续 JSONResponse），保证一致的 `detail/message` 结构。

### 5.3 数据模型与迁移
- 对照 `backend/app/models/*` 与 `backend-openwebui/open_webui/models/*`：
  - User/Files/Knowledge 已在 Open WebUI 存在，直接复用并补充必要字段（如需要）。
  - 新增 `Case/Node/Edge` 表及索引；若 `backend` 的 `Feedback` 与 Open WebUI `feedbacks.py` 有重复，整合为统一模型，保留必要字段（rating/comment/is_helpful 等）。
- 迁移脚本：使用 Alembic 在 `open_webui/migrations` 编写版本化迁移；若需历史数据迁移，提供一次性 ETL 脚本（如 `scripts/migrate_backend_data.py`）。

### 5.4 鉴权/权限对齐
- 仅保留 `backend-openwebui` 的鉴权体系：所有新路由引入 `Depends(get_verified_user)` 并基于其 `role/permissions` 判定权限。
- 若需兼容 `backend` 旧 Token，可在网关层转换或在 Router 中增加解析逻辑（过渡期可选）。

### 5.5 向量检索（Weaviate）接入
- 在 `open_webui/retrieval/vector/factory.py` 中扩展 `VectorType`，增加 `WEAVIATE` 分支，加载 `weaviate.py` 客户端。
- `weaviate.py` 需实现与 `VectorDBBase` 一致的接口：`add/get/search/delete/has_collection/delete_collection/get_stats` 等，与现有 Qdrant/Chroma 等实现对齐。
- 配置项：在 `open_webui/config.py` 增加 `WEAVIATE_URL/WEAVIATE_CLASS_NAME` 等；在 `.env` 或启动配置中暴露。
- 如果短期切换到 Open WebUI 已支持的向量后端，则需编写索引重建任务（离线重建，公用切分与嵌入逻辑）。

### 5.6 文档智能/语义分块整合
- 结合 `backend/app/services/document/idp_service*.py` 与 `semantic_splitter.py`：
  - 抽象为 `open_webui/services/ali_idp.py` 与 `semantic_splitter.py`，对外提供统一接口：`parse_document(file|url, options) -> chunks/meta`。
  - 将结果与 Open WebUI 的文件/知识库/检索流水线对接（`open_webui/routers/retrieval` 的 `process_file/process_files_batch`）。
  - 可通过 `open_webui/config.py` 增加相关引擎开关（如 `CONTENT_EXTRACTION_ENGINE`），优先保留 Open WebUI 现有配置命名与模式。

### 5.7 案例（Cases）与智能分析（Analysis）迁移
- 路由拆分：
  - `open_webui/routers/cases_migrated.py`：包含案例 CRUD、节点/边的读写、反馈写入、分页与过滤（参考 `backend/app/api_restx/cases.py`）。
  - `open_webui/routers/analysis_migrated.py`：日志解析接口（参考 `backend/app/api_restx/analysis.py`），注入用户上下文、调用 `services/ali_idp.py` 与检索服务，返回结构化结果与相关知识。
- 依赖注入：统一 `Depends(get_verified_user)`，权限判定参考 Open WebUI 的 `utils/access_control.py`。
- 模式与响应：改造为 Pydantic 响应模型，合并 `backend` 的 `success_response/validation_error` 等为 Open WebUI 响应风格。

### 5.8 文件与知识库能力对齐
- 复用 Open WebUI 的 `/api/v1/files` 与 `/api/v1/knowledge` 路由与模型，按需扩展元数据字段；若 `backend` 有特殊文件类型或缩略图生成策略，合并为 `Files` service 的可选处理。
- 批量处理与重建索引使用 Open WebUI 既有批量处理逻辑（`process_files_batch`、`reindex`）。

### 5.9 中间件与错误处理
- 复用 `open_webui` 现有中间件（CORS、压缩、审计、会话等），新路由只需遵守返回结构。
- 统一异常处理与日志（`utils/logger.py`、`utils/audit.py`）。

### 5.10 后台任务与异步
- `backend` 的 RQ/Redis 任务需要迁移为：
  - FastAPI `BackgroundTasks`（轻量短任务）；
  - 或复用 `open_webui` 的任务路由/机制（`/api/v1/tasks`，如有）。
- 长时任务建议采用队列/worker（如 Celery/RQ/Arq）但初期先用同步+后台任务，避免引入新基础设施。

### 5.11 配置与环境变量
- 将 `backend/config/settings.py` 的关键变量映射至 `open_webui/config.py` 与 `.env`：
  - 数据库、JWT（如需）、Redis、上传目录、阿里云 IDP、DashScope/OpenAI 等。
- 统一配置读取路径（`open_webui/env.py` 与 `open_webui/config.py`）。

### 5.12 API 文档与兼容
- 保持 FastAPI 自动 OpenAPI 文档；必要时在 `/api/v1/docs/` 增加人性化入口。
- 如需兼容 `backend` 的 Swagger 结构，仅保留最小映射，重点保证前端可用。

## 6. 测试与发布

### 6.1 测试策略
- 单元测试：针对新建适配器（Weaviate）、新路由（cases/analysis）、新服务（ali_idp/splitter）。
- 合同测试（契约）：对关键接口（auths/files/knowledge/retrieval/cases/analysis）编写请求-响应契约用例，覆盖鉴权、分页、错误码。
- 回归测试：构造典型用户路径（上传-入库-检索-对话/分析-反馈）。

### 6.2 迁移与回滚
- 数据迁移脚本具备幂等与回滚；重大结构变更采用“影子表/灰度发布”，双写观测 1–2 周。
- 向量索引重建离线进行，切换时以“新库读、旧库备份”为策略。

### 6.3 发布与监控
- 分阶段开关：通过环境变量或功能开关（Feature Flags）灰度开放新接口。
- 监控与告警：接入现有日志/审计，关注 5xx、超时、慢查询、索引构建失败率等。

## 7. 数据与模型映射建议（摘录）
- Users：复用 Open WebUI `open_webui/models/users.py`。
- Files/Knowledge：复用 Open WebUI；必要字段通过 `data/meta` 扩展。
- Cases：新增 `cases.py`，包含 `Case(id,user_id,title,query,status,vendor,category,created_at,updated_at)`；
  - Node：`Node(id,case_id,title,content,node_type,status,metadata,created_at)`；
  - Edge：`Edge(id,case_id,source_node_id,target_node_id,edge_type,metadata)`。
- Feedback：对齐 `open_webui/models/feedbacks.py`，按需兼容 `backend` 的评分/评论字段。

## 8. 时间与人力预估（粗略）
- MVP（3–5 人周）：
  - 向量适配或索引迁移：1–1.5 人周
  - cases/analysis 路由与服务：1–1.5 人周
  - 文档智能/分块整合：0.5–1 人周
  - 契约测试与回归：0.5–1 人周
- 完善阶段（+2–3 人周）：高级检索、权限细化、反馈/审计打通、OpenAI 兼容路径。

## 9. 风险与缓解
- 鉴权/权限不一致：统一依赖 `get_verified_user` 与 Open WebUI 权限模型；过渡期增加兼容解析。
- 数据迁移失败：影子表+灰度+回滚脚本。
- Weaviate 与工厂接口不一致：以现有 `VectorDBBase` 为准编写适配，增加契约测试。
- 异步/流式差异：先不覆盖 Socket，必要时以 SSE 或后台任务过渡。

## 10. 落地清单（可执行）
1) 代码框架
   - [ ] 新增 `open_webui/retrieval/vector/dbs/weaviate.py`，扩展 `factory.py` 与 `VectorType`。
   - [ ] 新增 `open_webui/services/ali_idp.py`、`open_webui/services/semantic_splitter.py`。
   - [ ] 新增 `open_webui/routers/cases_migrated.py`、`open_webui/routers/analysis_migrated.py` 并在 `main.py` 注册。
   - [ ] 新增/合并 `open_webui/models/cases.py`，编写 Alembic 迁移脚本。
2) 配置
   - [ ] 在 `open_webui/config.py` 增加 Weaviate 与 Ali IDP 相关配置；更新 `.env` 模板。
3) 业务联调
   - [ ] 复用/扩展 `/api/v1/files`、`/api/v1/knowledge`，对齐字段与批处理。
   - [ ] 完成 cases/analysis 的 Pydantic 模型与权限注入。
4) 向量与检索
   - [ ] 接入 Weaviate 或迁移索引；重建与一致性校验。
5) 测试与发布
   - [ ] 单元/契约/回归测试编写与通过。
   - [ ] 灰度发布与监控告警接入。

## 11. 依赖与文档参考（建议）
- FastAPI 文档（路由/依赖注入/背景任务/OpenAPI）：https://fastapi.tiangolo.com/
- Pydantic v2 模型与校验：https://docs.pydantic.dev/
- SQLAlchemy/Alembic 迁移：https://alembic.sqlalchemy.org/
- Weaviate 客户端（v3/v4 注意差异）：https://weaviate.io/developers
- LangChain/检索链路（如继续使用）：https://python.langchain.com/

> 注：实施前请根据实际依赖版本核对上述官网最新文档，避免因版本差异造成的接口不匹配（例如 Pydantic v2 与 v1 的差异、Weaviate v3/v4 客户端差异、FastAPI/Starlette 的行为变化等）。
