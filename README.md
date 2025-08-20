# backend-openwebui（Open WebUI 后端）

本仓库为 [Open WebUI](https://github.com/open-webui/open-webui) 项目的后端（基于 FastAPI），在原生能力基础上集成并扩展了以下功能：

- 向量数据库扩展：新增 Weaviate 适配（通过 `VECTOR_DB=weaviate` 启用）。
- 文档智能解析：接入阿里云文档智能（DocMind）与语义分块，作为文件内容抽取引擎（`CONTENT_EXTRACTION_ENGINE=alibaba_idp`）。
- 业务能力迁移：新增“案例（Cases）”与“智能分析（Analysis）”路由，逐步对齐 `backend` 仓库中的新能力与 API。

---

## 核心技术栈
- 后端框架：FastAPI + Starlette
- ORM 与迁移：SQLAlchemy + Alembic
- 实时与压缩：WebSocket、中间件（CORS、压缩、会话）
- 检索与嵌入：多向量后端（Chroma、Qdrant、PgVector、Milvus、Elasticsearch、OpenSearch、S3Vector、Weaviate 等）、多嵌入/重排引擎
- 文档解析：Docling、Tika、Azure Document Intelligence、阿里云 DocMind、Mistral OCR、External

---

## 目录结构（节选）
```
backend-openwebui/
├─ open_webui/
│  ├─ main.py                 # FastAPI 应用入口
│  ├─ config.py               # 配置中心（环境、RAG、向量库、抽取引擎等）
│  ├─ env.py                  # 环境变量解析
│  ├─ internal/               # 数据库引导与会话
│  ├─ models/                 # 业务模型（users/files/knowledge/…，新增 cases）
│  ├─ routers/                # 路由（auths/users/files/knowledge/retrieval 等，新增 cases_migrated/analysis_migrated）
│  ├─ retrieval/              # RAG 抽取/检索/向量后端
│  │  ├─ loaders/             # 文档加载器（含 alibaba_idp）
│  │  └─ vector/              # 向量库抽象与具体实现（含 weaviate 适配）
│  ├─ services/               # 领域服务（新增 ali_idp 与 semantic_splitter）
│  └─ migrations/             # Alembic 迁移脚本
├─ requirements.txt           # 依赖清单
├─ start.sh / start_windows.bat
└─ …
```

---

## 快速开始（本地）
1. 准备环境
- Python 3.11，建议使用虚拟环境
- 安装依赖：
  ```bash
  pip install -r requirements.txt -U
  ```

2. 启动服务
- 首先在仓库根目录打开 bash 环境（例如 Git Bash）
- 然后激活虚拟环境
- 输入
  ```bash
  sh dev.sh
  ```
  来启动后端服务

---

## 关键配置（环境变量）

### 通用
- `ENV`：运行环境（dev/prod）
- `DATABASE_URL`：数据库连接（SQLite/Postgres/…）
- `UPLOAD_DIR`：文件上传目录

### 向量数据库
- `VECTOR_DB`：`chroma`（默认）/`qdrant`/`pgvector`/`milvus`/`elasticsearch`/`opensearch`/`s3vector`/`weaviate`/`oracle23ai`
- Weaviate（新增）：
  - `WEAVIATE_URL`（默认 `http://localhost:8080`）
  - `WEAVIATE_COLLECTION_PREFIX`（默认 `open_webui`）

### 内容抽取（Content Extraction）
- `CONTENT_EXTRACTION_ENGINE`：
  - 可选：`docling` / `tika` / `document_intelligence`（Azure）/ `mistral_ocr` / `external` / `alibaba_idp`（新增）等
- 阿里云 DocMind（仅当 `CONTENT_EXTRACTION_ENGINE=alibaba_idp` 时关注）：
  - 凭证：使用 `alibabacloud_credentials` 标准方式读取（环境或实例凭证）
  - 可选参数：
    - `ALIBABA_IDP_ENABLE_LLM`（默认 true）
    - `ALIBABA_IDP_ENABLE_FORMULA`（默认 true）
    - `ALIBABA_IDP_MAX_CHUNK_SIZE`（默认 1000）
    - `ALIBABA_IDP_CHUNK_OVERLAP`（默认 100）

### 检索与嵌入（节选）
- `RAG_EMBEDDING_ENGINE`、`RAG_EMBEDDING_MODEL`、`RAG_OPENAI_API_BASE_URL`、`RAG_OPENAI_API_KEY` 等（详见 `open_webui/config.py`）。

---

## 新增与迁移能力

### 1. Weaviate 向量后端
- 设置 `VECTOR_DB=weaviate` 即可启用。
- 相关文件：
  - `open_webui/retrieval/vector/dbs/weaviate.py`
  - `open_webui/retrieval/vector/type.py`（新增枚举）
  - `open_webui/retrieval/vector/factory.py`（工厂接入）

### 2. 阿里云文档智能 + 语义分块
- 将阿里 DocMind 解析与自定义切分器整合为抽取引擎：
  - Loader：`open_webui/retrieval/loaders/alibaba_idp.py`
  - 服务：`open_webui/services/ali_idp.py`、`open_webui/services/semantic_splitter.py`
- 使用方式：将 `CONTENT_EXTRACTION_ENGINE` 设置为 `alibaba_idp`，上传文件即可走解析→分块→向量化→检索入库流程。

### 3. Cases 与 Analysis 路由
- `open_webui/routers/cases_migrated.py`：案例 CRUD、节点/边管理、基础筛选与分页；模型与迁移见 `open_webui/models/cases.py` 与 `open_webui/migrations/versions/*cases*`。
- `open_webui/routers/analysis_migrated.py`：日志解析与相关知识检索（轻量规则库 + RAG Top-K），后续可扩展为“文本 + 附件”模式以调用 IDP 全链路。

> 迁移提示：首次引入 Cases 需执行数据库迁移（见“快速开始/初始化数据库”）。

新增案例相关接口（节选）：
- `GET /api/v1/cases`：列表/筛选/分页
- `POST /api/v1/cases`：创建案例
- `GET /api/v1/cases/{case_id}`：详情（含图谱）
- `PUT /api/v1/cases/{case_id}`：更新标题/状态等
- `DELETE /api/v1/cases/{case_id}`：删除案例（含节点/边）
- `POST /api/v1/cases/{case_id}/nodes/{node_id}/rate`：节点评价
- `POST /api/v1/cases/{case_id}/interactions`：新增一次交互（生成“用户补充信息”与“AI分析中”节点）
- `PUT /api/v1/cases/{case_id}/feedback`、`GET /api/v1/cases/{case_id}/feedback`：案例反馈读写

---

## 常用 API 路由（节选）
- 认证与用户：`/api/v1/auths`、`/api/v1/users`
- 文件与知识库：`/api/v1/files`、`/api/v1/knowledge`
- 检索管道：`/api/v1/retrieval`
- 模型与工具：`/api/v1/models`、`/api/v1/tools`、`/api/v1/prompts`
- 新增能力：
  - 案例：`/api/v1/cases`
  - 分析：`/api/v1/analysis/log-parsing`

> 其它路由与参数请参考 FastAPI 自动文档（启动后端后访问 http://localhost:8080/docs ）或源码（`open_webui/routers`）。

---

## 开发建议
- 统一依赖 `open_webui/config.py` 中的配置项，通过环境变量覆盖。
- 新增业务时优先封装为 `services/*`，路由仅做参数校验与组合编排。
- 迁移第三方能力时，尽量以“适配器 + 工厂”扩展（保持与既有实现一致的接口契约）。
- 访问其[官方文档](https://docs.openwebui.com/)来获得更多支持

---
