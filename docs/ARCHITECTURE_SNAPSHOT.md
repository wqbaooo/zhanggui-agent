# 开店 Agent 项目快照

> **生成日期**：2026-05-14
> **版本**：v3.0 (LangGraph/ReAct)
> **状态**：只读分析，非自动生成

---

## 1. 项目类型与定位

### 产品定义

餐饮开店智能顾问 Agent，基于 LangGraph/ReAct 架构，帮助餐饮创业者从"想法"到"运营增长"做全生命周期决策。

### 目标用户

- 餐饮创业者（新手/有经验/老手）
- 覆盖三四线城市到一线城市
- 支持摆摊 / 档口 / 小店 / 标准店 / 旗舰店多种经营模式

### 解决的核心问题

| 阶段 | 问题 |
|------|------|
| 想法验证 | 品类选什么？预算够不够？我适不适合开店？ |
| 选址筹备 | 商圈好不好？竞品多不多？铺位该不该接？ |
| 开店执行 | 证照怎么办？装修怎么控制成本？设备买什么？ |
| 运营增长 | 怎么开业引流？怎么管成本和人员？怎么持续盈利？ |

### 与普通知识库检索的本质区别

不是关键词匹配吐资料，而是**LLM 驱动的 ReAct 循环**：

```
用户输入 → [思考] 理解意图 → [行动] 调用工具（搜索/地图/财务/爬虫）
→ [观察] 整理结果 → [反思] 评估质量 → [决策] 回复或追问
```

### 核心差异化

1. **苏格拉底辩证法**：正题（用户想法）→ 反题（数据挑战）→ 合题（综合判断）
2. **宪法约束**：8 条不可违背准则（利润中性/风险前置/事实分离/边界意识/用户优先/数据透明/苏格拉底主权/进化）
3. **创业者人格评估**：六维人格（成就动机/抗压韧性/风险偏好/学习敏捷性/社交能力/财务素养）通过对话自动评估
4. **四阶段开店计划生成**：覆盖 23 个子模块

---

## 2. 技术栈

### 运行时

| 层面 | 内容 | 版本 |
|------|------|------|
| 语言 | Python | 3.12.13（pyenv 管理，要求 >= 3.10） |
| 依赖管理 | pip + pyproject.toml | setuptools >= 61.0 |
| **Agent 框架** | **LangGraph** | **1.1.9** |
| LLM 编排 | LangChain Core | 1.3.3 |
| LLM 接口 | LangChain OpenAI | 1.2.1 |
| **主 LLM** | **DeepSeek API** (`deepseek-chat`) | OpenAI 兼容协议 |
| 降级 LLM | OpenAI (`gpt-4o-mini`) | OpenAI 兼容协议 |
| OpenAI SDK | openai | 2.36.0 |

### 检索与知识库

| 层面 | 内容 | 版本 |
|------|------|------|
| BM25 索引 | `rag_index.json` (1302 chunks) | 自定义实现 |
| 向量语义搜索 | sentence-transformers | 5.4.0 |
| 向量库 | Faiss (CPU) | 1.13.2 |
| PDF 解析 | pypdf | 4.3.1 |
| 语音转写（可选） | openai-whisper | 20250625 |

### 外部服务与数据源

| 服务 | 用途 | 是否必需 |
|------|------|----------|
| DeepSeek API | LLM 推理 | 是（启用 LangGraph 模式） |
| 高德 WebService API | 商圈 POI 分析、地理编码 | 否（无 key 时工具不可用） |
| DuckDuckGo | 联网搜索 | 否（备选 Serper/Tavily） |

### 爬虫框架

| 库 | 用途 | 状态 |
|------|------|------|
| requests + BeautifulSoup4 | 美团/抖音爬虫基础 | 已安装，爬虫工具占位未实质性集成 |
| selenium / playwright | 高级爬虫 | **已注释**，未安装 |

### 没有的

| 组件 | 说明 |
|------|------|
| **Web 框架** | 无 FastAPI/Flask/uvicorn（纯 CLI + Python API） |
| **数据库** | 无 MySQL/PostgreSQL/SQLite（文件 JSON 持久化） |
| **前端** | 无 Web UI/移动端 |
| **消息队列** | 无 |
| **Docker** | 无 Dockerfile/docker-compose |

---

## 3. 架构概览

### 双架构设计

```
                    ┌──────────────────┐
                    │   main.py        │
                    │   统一入口        │
                    └──────┬───────────┘
                           │
             有 DEEPSEEK_API_KEY?
                    │
           ┌────────┴────────┐
           │ YES             │ NO
           ▼                 ▼
   ┌──────────────┐  ┌──────────────┐
   │ LangGraph    │  │ 旧状态机     │
   │ ReAct 循环   │  │ Session      │
   │ MemorySaver  │  │ StateMachine │
   └──────────────┘  └──────────────┘
```

### LangGraph v3.0 状态图

```
[START]
  ↓
[agent] ── LLM 决策节点（苏格拉底辩证法 + 工具选择）
  ↓
[constitution_check] ── 宪法审查（8 条违规检测）
  ↓
[personality_inject] ── 追加人格情境追问
  ↓
  ├─ 需要调工具 → [tools] ── ToolNode 执行（6 个工具）
  │                      ↓
  └─ 直接回复 → [END]     回到 [agent] 继续推理
```

### 核心模块映射

| 模块 | 路径 | 职责 |
|------|------|------|
| 统一入口 | `main.py` | LangGraph 优先 + 旧架构降级，总助理接口 |
| 兼容入口 | `开店Agent.py` | 委托给 main.py |
| Agent 图 | `graph/agent.py` | ReAct 循环：agent → 宪法审查 → tools → agent |
| 状态定义 | `graph/state.py` | GraphState 数据类（画像/计划/推理/证据/风险） |
| 工具定义 | `graph/tools.py` | 12 个 LLM 可调用工具（含 4 个重复定义） |
| 系统提示 | `graph/prompts.py` | 苏格拉底辩证法 + 宪法约束 + 人格评估 |
| 数据模型 | `models/` | AssistantRequest/Response、Plan/Task、ProjectMemory |
| 旧架构 | `core/` | Session、StateMachine、Orchestrator、TaskManager |
| 旧节点 | `nodes/` | 意图分类/画像收集/证据检索/风险诊断/回复合成 |
| 工具实现 | `tools/` | RAG、向量搜索、联网搜索、财务、地图、加盟、爬虫 |
| 全局配置 | `config.py` | 环境变量加载、路径常量 |
| 知识库 | `knowledge_base/` | Markdown/视频 JSON/文档 OCR/向量索引/市场数据 |
| 脚本 | `scripts/` | 索引构建/知识库扩展/视频处理/文档入库/审计 |

---

## 4. 启动方式

### 最简启动

```bash
cd "/Users/wqboo/Code/20-Products/开店Agent"
pip install -r requirements.txt
export DEEPSEEK_API_KEY="sk-你的key"
python3 开店Agent.py
```

### 所有运行模式

```bash
# 交互式对话
python3 开店Agent.py

# 命令行单次查询
python3 开店Agent.py "我想在县城用10万开早餐店"

# 知识库审计
python3 开店Agent.py --audit

# 总助理 JSON 模式
echo '{"user_message":"如何选址？"}' | python3 开店Agent.py --json

# 旧架构手动测试
python3 test_session_loop.py

# 纯 LangGraph CLI（直接进入 ReAct 循环）
python3 graph/agent.py
```

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEEPSEEK_API_KEY` | - | **必需**（启用 LangGraph 模式） |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 模型名称 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | API 地址 |
| `OPENAI_API_KEY` | - | DeepSeek 不可用时的降级方案 |
| `AMAP_WEBSERVICE_KEY` | - | 高德地图商圈分析（可选） |
| `AMAP_REQUEST_INTERVAL` | `0.35` | 高德 API 请求间隔（秒） |
| `SEARCH_BACKEND` | `auto` | 搜索后端：auto/duckduckgo/serper/tavily |
| `SERPER_API_KEY` | - | Serper 搜索 API（可选） |
| `TAVILY_API_KEY` | - | Tavily 搜索 API（可选） |

### 可选依赖

```bash
# 向量化检索（提升语义搜索质量）
pip install numpy sentence-transformers faiss-cpu

# 视频转写（需先安装 ffmpeg）
brew install ffmpeg
pip install openai-whisper ffmpeg-python pydub
```

---

## 5. 验证方式

### 健康检查

无 HTTP 健康检查接口（纯 CLI 应用）。

### 功能验证

```bash
# 1. 知识库审计（最快确认项目可运行）
python3 开店Agent.py --audit

# 2. 单次查询（验证 LLM + 知识库联动）
python3 开店Agent.py "县城早餐店10万预算可行性分析"

# 3. 交互式对话（验证多轮对话 + 画像累积）
python3 开店Agent.py
```

### 成功判定

| 模式 | 成功标志 |
|------|----------|
| `--audit` | 输出非空 JSON，含 `markdown_chunks`/`video_total`/`chunks` 等字段 |
| 单次查询 | 输出 Markdown 格式分析报告（非错误堆栈） |
| 交互式 | 出现 `开店做生意 Agent` 提示，能多轮对话 |

---

## 6. 目录安全边界

### 绝对不能删除/修改的

| 路径 | 类型 | 说明 |
|------|------|------|
| `knowledge_base/开店Agent知识库.md` | 核心知识 | 26 个片段，Markdown 格式 |
| `knowledge_base/video_knowledge/` | 视频课程 | 162 个 JSON（含转写文本） |
| `knowledge_base/document_knowledge/` | 文档知识 | PDF OCR 结果、结构化 JSON |
| `knowledge_base/qa_pairs.json` | QA 对 | 精准检索知识 |
| `knowledge_base/structured/` | 结构化知识 | 100+ 个方法论/案例 JSON |
| `knowledge_base/market_data/city_costs.json` | 成本基准 | 102 行城市成本数据 |
| `graph/` | Agent 核心 | LangGraph 图的全部代码 |
| `prompts/` | 提示词模板 | 节点专用提示词 |

### 可安全重建的

| 路径 | 类型 | 重建命令 |
|------|------|----------|
| `knowledge_base/rag_index.json` | BM25 索引 | `python3 scripts/build_rag_index.py` |
| `knowledge_base/vector_store/` | Faiss 向量索引 | `python3 scripts/build_rag_index.py --vector` |
| `knowledge_base/vector_store_sharded/` | 分片向量索引 | `python3 scripts/build_sharded_index.py` |
| `__pycache__/` | Python 缓存 | 自动生成 |

### 运行时数据（用户数据）

| 路径 | 说明 |
|------|------|
| `project_archives/` | 用户项目档案 JSON（已有一个 `PROJ_FFC0C1B0.json`） |
| `project_data/` | 持久化数据（当前为空） |

---

## 7. 已知问题与风险

### 代码层面

| 问题 | 严重程度 | 说明 |
|------|----------|------|
| **`.gitignore` 缺失** | 🟡 中 | `.env`/`__pycache__`/`.DS_Store` 可能被意外提交 |
| **`.env.example` 缺失** | 🟡 中 | 文档中说 `cp .env.example .env` 但文件不存在 |
| **`graph/tools.py` 函数重复定义** | 🟠 高 | `analyze_location`/`analyze_franchise`/`update_profile`/`generate_plan` 各定义了两次，第二次覆盖第一次（copy-paste 遗留） |
| **`langgraph` 版本号不匹配** | 🟡 中 | `requirements.txt` 写 `>=0.2.0`，实际安装 `1.1.9`，API 可能有 breaking changes |
| **`langgraph-checkpoint-sqlite` 已安装未使用** | 🟢 低 | 当前用 `MemorySaver`（内存 checkpoint），SQLite 模块闲置 |
| **爬虫工具未实质性集成** | 🟡 中 | `meituan_tool.py`/`douyin_tool.py` 存在但为占位实现 |
| **`project_data/` 为空目录** | 🟢 低 | 设计用于持久化，但无数据写入 |

### 运行时依赖

| 依赖 | 风险 |
|------|------|
| DeepSeek API | 无 key 时 Agent 降级到旧状态机（无 LLM 推理能力） |
| 高德 API | 无 key 时商圈分析不可用（工具返回提示信息） |
| DuckDuckGo | 被墙或限流时联网搜索不可用 |

---

## 8. 对外接口

### 总助理接口（`models/schemas.py`）

```python
from main import handle_assistant_request

result = handle_assistant_request({
    "user_message": "我想加盟蜜雪冰城，预算30万",
    "task_type": "finance",       # general|profile|site_eval|finance|permit|marketing|risk_review
    "project_id": "user_123",
    "context": {"city": "杭州"},
})

# 返回: 结构化 AssistantResponse（含 decision/summary/risks/next_actions/scores）
```

### 支持的 task_type

| 类型 | 触发引导 |
|------|----------|
| `general` | 通用咨询 |
| `profile` | 补充和完善开店画像 |
| `site_eval` | 评估选址，分析商圈和竞品 |
| `finance` | 财务测算，分析成本和回本周期 |
| `permit` | 开店证照和流程 |
| `marketing` | 开业营销方案 |
| `risk_review` | 风险评估和避坑分析 |

---

## 9. 知识库状态

- 核心 Markdown 知识片段：26 个
- 视频课程 JSON：162 个
- 视频已完成语音转写：141/162 个（87%）
- PDF《餐饮选址实用指南》：已登记，待 OCR
- RAG BM25 索引：1302 chunks
- 向量索引：分片存储（`vector_store_sharded/`）
- QA 对：已生成
- 结构化知识：100+ 个 JSON（方法论/案例/风险清单）
- 城市成本数据：含分线城市的租金/人工/客单价基准

---

## 10. 与外部项目关系

| 项目 | 关系 | 确认程度 |
|------|------|----------|
| MIND（记忆宫殿） | 知识检索系统，路径 `/Palace/` | 不确定（文档提到但无运行时依赖代码） |
| 总助理 | 通过 `AssistantRequest/Response` 接口调用 | 不确定（接口已定义但调用方身份未知） |
| Aether | 无引用 | 不确定 |
| Nexus | 无引用 | 不确定 |
