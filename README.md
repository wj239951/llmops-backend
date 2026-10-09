# LLMOps 平台 · 后端（llmops-backend）

基于 **FastAPI** 的一站式大模型应用平台后端，提供 **Prompt 管理、知识库问答（RAG）、多模型对话、会话记忆、运行日志** 五大模块的 REST API。

支持 **本地 Ollama 小模型** 与 **DeepSeek / Qoder 云端 API** 双通道切换，RAG 检索基于 **bge-m3 embedding + Chroma 向量库** 实现语义检索。

> 配套前端仓库：[llmops-frontend](https://github.com/wj239951/llmops-frontend)（Vue3 + TypeScript + Element Plus）

---

## 目录

- [项目亮点](#项目亮点)
- [技术栈](#技术栈)
- [系统架构](#系统架构)
- [目录结构](#目录结构)
- [数据模型](#数据模型)
- [API 接口](#api-接口)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [核心设计说明](#核心设计说明)
- [已知问题 / TODO](#已知问题--todo)

---

## 项目亮点

| 能力 | 实现要点 |
| --- | --- |
| **RAG 检索增强问答** | LangChain + Chroma 向量库 + bge-m3 embedding，长文档按 500 字 / 重叠 50 字切分（中文标点优先断句），知识库 CRUD 后向量库自动同步，回答返回引用来源 |
| **多模型双通道** | 抽象统一调用层，`ollama` / `deepseek` / `qoder` 三种 provider 按需切换，同一套业务代码不改 |
| **会话记忆** | 自设计 `ChatLog + conversation_id` 方案，按会话加载最近 N 轮历史作为上下文；首次提问自动生成会话标题 |
| **运行日志** | 记录 token 消耗、响应耗时、成功/失败状态与错误信息，支持分页与状态过滤 |
| **Prompt 管理** | Prompt 模板 CRUD，模板内可绑定模型、temperature、top_p，对话时一键套用 |

---

## 技术栈

| 分类 | 技术 |
| --- | --- |
| Web 框架 | FastAPI + Uvicorn |
| ORM / 数据库 | SQLAlchemy 2.0（`Mapped` / `mapped_column`）+ MySQL 8.x（PyMySQL 驱动） |
| 配置管理 | pydantic-settings（读取 `.env`） |
| RAG / 向量 | LangChain（`langchain-community`）+ Chroma + bge-m3（Ollama Embeddings）+ `RecursiveCharacterTextSplitter` |
| 模型调用 | OpenAI SDK（DeepSeek 兼容 OpenAI 协议）、Ollama HTTP API |
| 文档解析 | PyMuPDF（PDF）、原生解码（TXT / MD / PY / JSON） |
| 中文分词 | jieba（关键词检索方案保留） |

---

## 系统架构

```
┌────────────────────┐
│   前端 Vue3 (SPA)   │   llmops-frontend
└─────────┬──────────┘
          │  HTTP / JSON（REST，允许 localhost:5173/5174 跨域）
┌─────────▼────────────────────────────────────────────────────┐
│                    FastAPI 应用 (app/main.py)                 │
│         lifespan 启动时自动建表 · 统一 /api 前缀 · CORS        │
├──────────────────────────────────────────────────────────────┤
│ API 层 (app/api)                                              │
│   /chat   /conversations   /knowledge   /prompts   /logs      │
├──────────────────────────────────────────────────────────────┤
│ 业务层 (app/services)                                          │
│                                                              │
│   ChatService  ──┬──► PromptService   （读模板 / 参数）        │
│   （流程编排）    ├──► RAGService      （检索 + 拼上下文）      │
│                  └──► LLMService      （模型分发）             │
│                                                              │
│   file_parser（PDF/TXT/MD 解析入库）                            │
├──────────────────────────────────────────────────────────────┤
│ 模型通道层                                                   │
│   OllamaService（本地 deepseek-r1:7b）                        │
│   DeepSeekService（DeepSeek 云端 API，兼容 OpenAI SDK）        │
│   QoderService（Qoder 云端 Agent）                            │
├──────────────────────────────────────────────────────────────┤
│ 持久层                                                       │
│   SQLAlchemy ──► MySQL（4 张业务表）                          │
│   Chroma     ──► 本地 ./chroma_db（向量 + 元数据）             │
└──────────────────────────────────────────────────────────────┘
```

### 一次 `/api/chat` 请求的完整链路

`ChatService.chat()` 是核心编排逻辑，按以下顺序执行（每一步都会写入返回体的 `reasoning` 字段，便于前端展示"思考过程"）：

1. 读取用户输入
2. 加载系统提示词（默认值或请求传入）
3. **套用 Prompt 模板**（可选，传入 `prompt_id` 时覆盖提示词与模型参数）
4. **加载会话记忆**（可选，`memory_enabled=true` 且带 `conversation_id` 时取最近 `MEMORY_MAX_TURNS` 轮）
5. **RAG 检索**（可选，`use_rag=true` 时检索知识库并把命中片段拼进上下文）
6. 调用大模型生成回答（由 `LLMService` 按 provider 分发）
7. 模型回答生成完成
8. **将调用日志写入数据库**（含 `conversation_id`，供后续会话记忆检索）
9. 记录本次调用耗时，返回回答 + 引用来源

> 失败时同样落库，`status="failed"` 并记录 `error_message`，保证日志可追溯。

---

## 目录结构

```
llmops-backend/
├── app/
│   ├── main.py                 # FastAPI 入口：注册路由、CORS、启动建表
│   ├── api/                    # 路由层
│   │   ├── chat.py             # POST /chat
│   │   ├── conversations.py    # 会话列表 / 新建 / 聊天记录 / 删除
│   │   ├── knowledge.py        # 知识库 CRUD + 文件上传
│   │   ├── logs.py             # 运行日志分页查询
│   │   └── prompt.py           # Prompt 模板 CRUD
│   ├── core/
│   │   ├── config.py           # Settings（读 .env）
│   │   └── database.py         # engine / SessionLocal / get_db / init_db
│   ├── models/                 # SQLAlchemy 表模型
│   │   ├── chat_log.py         # llm_chat_logs
│   │   ├── conversation.py     # conversations
│   │   ├── knowledge.py        # llm_knowledge_documents
│   │   └── prompt.py           # llm_prompts
│   ├── schemas/                # Pydantic 请求/响应模型
│   │   ├── chat.py
│   │   ├── knowledge.py
│   │   └── prompt.py
│   └── services/               # 业务逻辑
│       ├── chat_service.py     # 对话主流程编排
│       ├── llm_service.py      # 模型通道统一分发
│       ├── ollama_service.py   # 本地 Ollama 调用
│       ├── deepseek_service.py # DeepSeek 云端调用
│       ├── qoder_service.py    # Qoder 云端调用
│       ├── rag_service.py      # 向量检索 + 上下文拼接 + Chroma 同步
│       ├── prompt_service.py   # Prompt CRUD
│       ├── file_parser.py      # 文件解析（PDF / TXT / MD / PY / JSON）
│       └── Disable_word_list.txt  # 停用词表（关键词检索方案使用）
├── .env.example                # 环境变量模板（真实 .env 已被 gitignore）
├── requirements.txt
└── run.py                      # 启动入口（uvicorn，端口 8000）
```

---

## 数据模型

### MySQL（库名 `llmops_db`，由 `init_db()` 自动建表）

**`llm_prompts`** — Prompt 模板

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int PK | 自增主键 |
| name | varchar(100) | 模板名，唯一索引 |
| description | varchar(255) | 描述 |
| system_prompt | text | 系统提示词内容 |
| model_provider | varchar(50) | 绑定的模型通道，默认 `ollama` |
| model_name | varchar(100) | 绑定的模型名 |
| temperature / top_p | float | 采样参数 |
| enabled | bool | 是否启用 |
| created_at / updated_at | datetime | 时间戳 |

**`llm_knowledge_documents`** — 知识库文档

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int PK | 自增主键（同时作为向量库关联键） |
| title | varchar(200) | 标题，索引 |
| content | text | 正文全文 |
| source | varchar(255) | 来源（上传时存文件名） |
| created_at | datetime | 创建时间 |

**`conversations`** — 会话

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | varchar(36) PK | UUID |
| title | varchar(30) | 会话标题（首次提问取问题前 30 字） |
| created_at / updated_at | datetime | 时间戳（列表按 updated_at 倒序） |

**`llm_chat_logs`** — 调用日志

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | int PK | 自增主键 |
| conversation_id | varchar(64) | 会话 ID，索引（会话记忆据此回查） |
| user_input / assistant_output | text | 提问与回答 |
| model_provider / model_name | varchar | 实际使用的模型通道与模型 |
| prompt_name | varchar(100) | 本次套用的 Prompt 模板名 |
| total_tokens | int | token 消耗 |
| latency_ms | int | 响应耗时（毫秒） |
| status | varchar(30) | `success` / `failed` |
| error_message | text | 失败原因 |
| created_at | datetime | 创建时间，索引 |

### Chroma 向量库（本地 `./chroma_db`）

- Collection：`knowledge_bge_m3`
- 每篇文档经 `RecursiveCharacterTextSplitter`（`chunk_size=500`、`chunk_overlap=50`、中文标点优先断句）切分为多个 chunk，**每个 chunk 一条向量**
- 向量 ID：`{文档id}_{序号}`；metadata：`{"id": MySQL主键, "title": 标题, "chunk": 序号}`
- 检索命中后，用 metadata 里的 `id` 反查 MySQL 拿回完整文档信息（标题 / 来源），保证向量库与业务库解耦

---

## API 接口

统一前缀 `/api`（根路径 `/` 返回服务基本信息）。启动后可在 `http://127.0.0.1:8000/docs` 查看自动生成的 Swagger 文档。

### Chat

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/chat` | 发起对话（支持 Prompt 模板 / RAG / 会话记忆） |

请求体：

```json
{
  "query": "润滑脂型号是什么",
  "prompt_id": null,
  "system_prompt": null,
  "model_provider": "ollama",
  "model_name": null,
  "temperature": 0.7,
  "top_p": 0.9,
  "use_rag": true,
  "conversation_id": "3f2b1c9e-...",
  "memory_enabled": true
}
```

响应体：

```json
{
  "answer": "根据知识库，应使用 RL-2077 型润滑脂。",
  "reasoning": "步骤1：读取用户输入。…",
  "thought": "已调用本地 Ollama 模型 deepseek-r1:7b，并完成 Prompt/RAG/会话记忆/日志流程。",
  "model_provider": "ollama",
  "model_name": "deepseek-r1:7b",
  "total_tokens": 512,
  "latency_ms": 4210,
  "conversation_id": "3f2b1c9e-...",
  "sources": [
    { "title": "设备维护手册", "snippet": "必须使用指定润滑脂，型号为 RL-2077…", "source": "manual.pdf" }
  ]
}
```

### Conversations（会话管理）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/conversations` | 会话列表（按更新时间倒序） |
| POST | `/api/conversations` | 新建会话（服务端生成 UUID） |
| GET | `/api/conversations/{conversation_id}/messages` | 某会话的聊天记录（仅 `success`） |
| DELETE | `/api/conversations/{conversation_id}` | 删除会话及其聊天记录 |

### Knowledge（知识库）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/knowledge` | 新增文档（text 录入），自动切分并写入向量库 |
| POST | `/api/knowledge/upload` | 上传文件（TXT / MD / PY / JSON / PDF），解析后入库并向量化 |
| GET | `/api/knowledge` | 文档列表（按 id 倒序） |
| PUT | `/api/knowledge/{id}` | 更新文档，同步重建该文档的向量 |
| DELETE | `/api/knowledge/{id}` | 删除文档，同步删除其全部向量 |

> 更新与删除都会按 `metadata.id` 精确清理对应的全部 chunk，避免向量库残留脏数据。

### Prompts（Prompt 模板）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/api/prompts` | 新建模板 |
| GET | `/api/prompts` | 模板列表 |
| PUT | `/api/prompts/{id}` | 更新模板（不存在返回 404） |
| DELETE | `/api/prompts/{id}` | 删除模板（不存在返回 404） |

### Logs（运行日志）

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| GET | `/api/logs?page=1&page_size=10&status=success` | 分页查询日志，`status` 可选（`success` / `failed`） |

---

## 快速开始

### 环境要求

- **Python 3.10+**（代码使用了 `str | None` 联合类型与 `match` 语句）
- **MySQL 8.x**
- **[Ollama](https://ollama.com/)**（本地模型 + RAG 的 embedding 模型都靠它）
- DeepSeek API Key（可选，不配置则只用本地 Ollama）

### 步骤

**1. 准备数据库**

```sql
CREATE DATABASE llmops_db DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

表结构由应用启动时自动创建，无需手动建表。

**2. 准备 Ollama 模型**

```bash
# 对话模型（本地小模型）
ollama pull deepseek-r1:7b

# 向量模型（RAG 检索必需，缺了知识库检索会失败）
ollama pull bge-m3

# 确认服务已启动
ollama list
```

**3. 安装依赖**

```bash
git clone https://github.com/wj239951/llmops-backend.git
cd llmops-backend

python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

**4. 配置环境变量**

```bash
# Windows
copy .env.example .env
# macOS / Linux
cp .env.example .env
```

然后编辑 `.env`，至少填好 MySQL 密码；如需云端通道再填 DeepSeek Key（见下方[配置说明](#配置说明)）。

**5. 启动服务**

```bash
python run.py
```

等价于：

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

启动后：

- 接口地址：`http://127.0.0.1:8000`
- 接口文档（Swagger UI）：`http://127.0.0.1:8000/docs`

**6. 配合前端使用**

克隆并启动前端仓库 [llmops-frontend](https://github.com/wj239951/llmops-frontend)，前端默认访问本服务。后端的 CORS 已放行 `http://localhost:5173` 与 `http://localhost:5174`。

---

## 配置说明

配置全部通过项目根目录的 `.env` 读取（模板见 `.env.example`）：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `API_PREFIX` | `/api` | 接口统一前缀 |
| `MYSQL_HOST` | `127.0.0.1` | MySQL 地址 |
| `MYSQL_PORT` | `3306` | MySQL 端口 |
| `MYSQL_DATABASE` | `llmops_db` | 数据库名 |
| `MYSQL_USER` | `root` | 用户名 |
| `MYSQL_PASSWORD` | 空 | 密码（**必填**） |
| `DEFAULT_MODEL_PROVIDER` | `ollama` | 默认模型通道 |
| `OLLAMA_BASE_URL` | `http://127.0.0.1:11434` | Ollama 服务地址 |
| `OLLAMA_MODEL` | `deepseek-r1:7b` | 本地对话模型 |
| `DEEPSEEK_API_KEY` | 空 | DeepSeek Key（不填则只有本地通道） |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | DeepSeek 接口地址 |
| `DEEPSEEK_MODEL` | `deepseek-v4-pro` | 云端模型；官方通用模型为 `deepseek-chat`、带思考链为 `deepseek-reasoner`，按需在 `.env` 覆盖 |
| `QODER_API_KEY` | 空 | Qoder 个人访问令牌（可选通道） |
| `QODER_BASE_URL` | `https://api.qoder.com.cn` | Qoder 网关 |
| `QODER_MODEL` | `qoder-cloud-agent` | Qoder 模型 |
| `QODER_TIMEOUT` | `180` | Qoder 轮询超时（秒） |
| `QODER_AGENT_MODEL` / `QODER_AGENT_ID` / `QODER_ENVIRONMENT_ID` | `ultimate` / 空 / 空 | Qoder 建 agent 用的档位与资源 ID，留空则自动取账号下第一个 |
| `MEMORY_MAX_TURNS` | `10` | 会话记忆加载的最大历史轮数 |

> ⚠️ **安全提示**：`.env` 已在 `.gitignore` 中，请勿提交真实密钥。仓库内只保留 `.env.example` 占位模板。

---

## 核心设计说明

### 1. 会话记忆为什么这样设计

多轮对话的关键是"把哪些历史喂给模型"。本项目的做法是：

- 每次对话把 `conversation_id` 一起写进 `llm_chat_logs`；
- 下次请求若带同一 `conversation_id` 且 `memory_enabled=true`，就从日志表按 `created_at` 倒序取最近 `MEMORY_MAX_TURNS` 轮**成功**记录，反转成正序后拼成 `[{role: user}, {role: assistant}, ...]`；
- 最终消息顺序固定为：`system → 历史轮次 → 当前问题`。

设计取舍：直接复用聊天日志表作为记忆来源，而不是另建一张"上下文表"，避免同一份数据存两份、也不会出现"历史记录被重复投喂"的问题。

### 2. RAG 从关键词检索升级到向量检索

**第一代（关键词）**：`jieba.lcut_for_search` 分词 → `OR` 召回 → 按关键词命中数排序 → 停用词 / 标点过滤 / 空查询守卫。

这一代修的是一个很典型的中文检索 bug：

| 查询 | 原方案 `split()` 切出的词 | 命中 |
| --- | --- | --- |
| `润滑脂型号是什么` | `['润滑脂型号是什么']` | **0 条** ← bug |
| `润滑脂` | `['润滑脂']` | 1 条 |
| `润滑脂 型号` | `['润滑脂', '型号']` | 1 条 |

根因有三层：`split()` 只按空格切，中文问句没有空格 → 整句变成 1 个 token → `LIKE` 要求整句原样连续出现 → 必然 0 命中；其次循环 `.filter()` 累加成 `AND` 链，多词必须全部命中；改 `OR` 之后又出现"命中 3 个词和命中 1 个词权重相同"的问题，于是补了按命中数排序。

**第二代（向量，当前实现）**：`bge-m3` 生成 embedding → Chroma 存储 → `similarity_search` 余弦相似度召回。整句话变成一个向量，**天然不需要精确子串匹配、也不需要人工分词**，这正是向量检索相对关键词检索的本质优势。旧的关键词实现以注释形式保留在 `rag_service.py` 中，便于对比。

### 3. 向量维度必须统一（一个隐蔽的坑）

Chroma 有两种写入方式，维度行为不同：

- 直接调用 `vectorstore._collection.add(documents=...)`：Chroma 会用**自带的默认 embedding 模型（384 维）**；
- 走 LangChain 包装层 `vectorstore.add_texts(...)`：才会使用配置的 **bge-m3（1024 维）**。

两者混用会导致"写入 384 维、读取 1024 维"的维度冲突。本项目统一走 `add_texts`，保证写入与检索同维度。

### 4. 多模型通道抽象

`LLMService.chat()` 是唯一的模型调用出口，按 `provider` 分发到 `OllamaService` / `DeepSeekService` / `QoderService`，三者签名一致（`query, system_prompt, model_name, temperature, top_p, history`），返回值统一为：

```python
{
    "answer": str,
    "reasoning": str,        # deepseek-reasoner 的思考内容，或本地模型的工作流说明
    "model_provider": str,
    "model_name": str,
    "total_tokens": int,
}
```

好处是新增一个模型通道只需实现一个类并注册分支，`ChatService` 与所有接口都不用改动。DeepSeek 走 OpenAI 兼容 SDK，只需改 `base_url` + `model`。

### 5. 分块策略

`RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)`，分隔符列表加入了中文标点（`。！？；，`），优先在句子边界断开，避免把一句话从中间切碎；50 字重叠保证跨块语义不会被割裂。

---

## 已知问题 / TODO

- [ ] **`langchain-text-splitters` 未显式写入 `requirements.txt`**（当前由 `langchain-community` 间接引入，建议显式声明避免环境差异）
- [ ] 接口无鉴权，仅适用于本地开发；部署前需补充认证
- [ ] 后端尚无单元测试（计划为 `chat` 流程、`RAGService.search`、Prompt CRUD 补 pytest）
- [ ] 前端尚未接入 `/api/knowledge/upload`（后端接口已就绪）
- [ ] 未容器化部署（Docker 打包进行中）

---

## 说明

本项目为个人学习与课程实践项目，独立设计并实现后端全部模块。开发过程中重点记录并修复了中文检索 0 命中、向量维度不一致、REST 状态码语义（资源不存在应为 404 而非 500）、Pydantic 字段静默丢失等问题。
