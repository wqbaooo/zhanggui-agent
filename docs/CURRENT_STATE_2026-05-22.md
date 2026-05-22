---
project: store-agent
snapshot_date: 2026-05-22
purpose: 项目现状快照（仅事实，附待评估方案）
plan_f_relation: 无关（独立工作流）
---

# 开店 Agent — 当前状态报告

> **日期**: 2026-05-22
> **文档类型**: 只读自查，标注已实施 vs 已规划

---

## 一、Git 版本状态

| 项目 | 值 |
|------|-----|
| 分支 | `main` |
| 总提交数 | 3 |
| 未提交修改 | `graph/tools.py`（去重重构，见 5.3） |
| 未跟踪新文件 | `.gitignore`, `docs/ARCHITECTURE_SNAPSHOT.md`, `graph/tools.py.backup` |
| 缺失 | `.env` |

```
3925c57 fix: 迁移路径修复 — 知识库 JSON 中 Code/MIND → 10-Core/mind
936860f chore: 添加 pyproject.toml，清理运行缓存
17b89fc init: 开设Agent 项目独立化 — 餐饮开店智能顾问，基于 LangGraph/ReAct
```

---

## 二、技术栈（Python / 依赖清单）

### 2.1 Python 版本

- **运行时**: Python 3.12.13（pyenv 管理）
- **要求**: `>=3.10`

### 2.2 requirements.txt / pyproject.toml 声明的依赖

| 包 | 声明版本 | 用途 |
|----|---------|------|
| `langgraph` | `>=1.1.0` | Agent 编排框架 |
| `langchain` | `>=0.3.0` | 大模型调用抽象 |
| `langchain-core` | `>=0.3.0` | LangChain 核心 |
| `langchain-openai` | `>=0.2.0` | OpenAI/DeepSeek 兼容接口 |
| `openai` | `>=1.0.0` | OpenAI SDK |
| `pypdf` | `>=4.0.0` | PDF 文档解析 |
| `duckduckgo-search` | `>=6.0,<7.0` | 联网搜索 |
| `requests` | `>=2.32.0` | HTTP 请求 |
| `beautifulsoup4` | `>=4.12.0` | HTML 解析 |
| `openai-whisper` (可选) | `>=20231117` | 语音转写 |
| `ffmpeg-python` (可选) | `>=0.2.0` | 音频处理 |
| `pydub` (可选) | `>=0.25.0` | 音频处理 |
| `pytest` (dev) | `>=7.0` | 测试框架 |
| `fastapi` | `>=0.115.0` | Web 框架 |
| `uvicorn` | `>=0.30.0` | ASGI 服务器 |
| `sse-starlette` | `>=2.0` | SSE 流式支持 |

### 2.3 实际安装版本

| 包 | 安装版本 | 声明版本 | 状态 |
|----|---------|----------|------|
| `langgraph` | **1.1.9** | `>=1.1.0` | ✅ |
| `langgraph-checkpoint-sqlite` | 3.0.3 | 未声明 | 已装未用（用 MemorySaver） |
| `langgraph-prebuilt` | 1.0.10 | 未声明 | 已装 |
| `langchain-core` | 1.3.3 | `>=0.3.0` | ✅ |
| `langchain-openai` | 1.2.1 | `>=0.2.0` | ✅ |
| `openai` | 2.36.0 | `>=1.0.0` | ✅ |
| `faiss-cpu` | 1.13.2 | 注释可选 | 已装 |
| `sentence-transformers` | 5.4.0 | 注释可选 | 已装 |
| `duckduckgo-search` | 6.4.2 | `>=6.0,<7.0` | ✅ |
| `pypdf` | 4.3.1 | `>=4.0.0` | ✅ |
| `openai-whisper` | 20250625 | `>=20231117` | ✅ |
| `fastapi` | **0.124.4** | `>=0.115.0` | ✅ |
| `uvicorn` | **0.33.0** | `>=0.30.0` | ✅ |
| `sse-starlette` | - | `>=2.0` | 待 pip install |

### 2.4 环境变量需求

| 变量 | 默认值 | 状态 |
|------|--------|------|
| `DEEPSEEK_API_KEY` | - | ❌ 未配置（`.env` 不存在） |
| `OPENAI_API_KEY` | - | ❌ 降级方案 |
| `AMAP_WEBSERVICE_KEY` | - | ❌ 商圈分析不可用 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 默认 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | 默认 |

---

## 三、目录结构与文件统计

```
开店Agent/
├── graph/                9 files   Agent 核心（LangGraph ReAct）
├── tools/               19 files   工具实现（RAG/财务/地图/爬虫）
├── models/              10 files   数据模型（Plan/Project/Schemas）
├── core/                10 files   旧架构（Session/StateMachine）
├── nodes/               18 files   旧架构状态机节点
├── scripts/             10 files   运维脚本（索引构建/视频处理/审计）
├── prompts/              4 files   提示词模板
├── docs/                 5 files   文档
├── knowledge_base/     333 files   知识库（视频166+文档24+向量索引+QA对+市场数据）
├── server/               0 files   🆕 待创建 — FastAPI 后端
├── web/                  0 files   🆕 待创建 — Next.js 前端
├── project_data/         0 files   运行时持久化（当前为空）
├── project_archives/     1 file    用户项目档案 (PROJ_FFC0C1B0.json)
├── 资料/                 2 files   原始餐饮资料
│
├── main.py              统一入口（LangGraph 优先 + 降级）
├── 开店Agent.py          兼容入口（委托 main.py）
├── config.py             环境变量 + 路径常量
├── amap_tool.py          高德地图原始工具
├── rag_engine.py         RAG 检索引擎
├── agent_v3.py           早期版本（未被引用）
├── test_session_loop.py  旧架构 Session 测试
├── pyproject.toml        Python 项目配置
├── requirements.txt      Python 依赖清单
├── AGENTS.md             项目重构蓝图 v3.0
├── CONSTITUTION.md       Agent 宪法 (8条不可违背准则)
├── README.md             项目说明
├── .gitignore            忽略规则（新增，未提交）
├── .env.example         环境变量模板（新增）
└── (无 package.json, .env, .env.example, Dockerfile, Makefile)
```

---

## 四、当前架构

### 4.1 运行时模式

```
用户输入 → main.py
              ├─ DEEPSEEK_API_KEY 存在 → LangGraph ReAct 循环
              └─ 无 key → 旧状态机降级（本地规则 + 可选 LLM）
```

### 4.2 LangGraph v3.0 Agent 图

```
START → [agent] → [constitution_check] → [personality_inject]
                ←──────────────────────────────────────┐
                  ↓ should_continue?                    │
                  ├─ tool_calls → [tools] ──────────────┘
                  └─ 无 → END
```

### 4.3 12 个可用工具

| # | 工具 | 功能 |
|---|------|------|
| 1 | `search_knowledge` | 知识库语义检索（向量优先 + BM25 降级） |
| 2 | `search_web` | DuckDuckGo 联网搜索 |
| 3 | `calculate_finance` | 盈亏平衡 / 回本周期 / 净利润率测算 |
| 4 | `analyze_location` | 高德 POI 商圈分析（精确选址 + 区域扫描） |
| 5 | `update_profile` | 更新用户画像（7 项人格维度） |
| 6 | `analyze_franchise` | 加盟品牌评估框架 + 红线检查 |
| 7 | `generate_plan` | 四阶段开店计划生成 |
| 8 | `generate_feasibility_report` | 全生命周期可行性报告（23 评估维度） |
| 9 | `analyze_competition` | 美团竞品数据聚合 |
| 10 | `analyze_local_trends` | 抖音本地热点趋势 |
| 11 | `query_city_costs` | 城市成本基准查询 |
| 12 | `manage_tasks` | 项目任务 CRUD |

### 4.4 对外接口（现有）

- **CLI 交互**: `python3 开店Agent.py`
- **CLI 单次查询**: `python3 开店Agent.py "问题"`
- **知识库审计**: `python3 开店Agent.py --audit`
- **总助理 JSON**: `echo '{"user_message":"..."}' | python3 开店Agent.py --json`
- **程序调用**: `from main import handle_assistant_request`
- **无 HTTP 端点**（无 Web 服务，无 FastAPI，无端口占用）

### 4.5 知识库状态

| 指标 | 数值 |
|------|------|
| 核心 Markdown 片段 | 26 |
| 视频课程 JSON | 166 |
| 视频已转写 | 141 (87%) |
| 文档 OCR 片段 | 24 |
| RAG BM25 索引 | 1432 chunks |
| 结构化知识 | 100+ JSON (方法论/案例) |
| 城市成本数据 | 1 (city_costs.json, 102行) |
| QA 对 | 已生成 |

---

## 五、已完成的改动

### 5.1 `.gitignore` 创建

- **日期**: 2026-05-22
- **内容**: Python 缓存、虚拟环境、macOS 系统文件、IDE 配置、日志、运行时数据（`project_archives/`/`project_data/`）、向量索引（`vector_store/`/`vector_store_sharded/`/`rag_index.json`）、临时文件
- **状态**: ✅ 已创建，未提交

### 5.2 `docs/ARCHITECTURE_SNAPSHOT.md` 创建

- **日期**: 2026-05-22
- **内容**: 项目技术栈、架构、启动方式、验证方式、已知问题、外部关系
- **状态**: ✅ 已创建，未提交

### 5.3 `graph/tools.py` 去重重构

- **日期**: 2026-05-22
- **变更**: 删除 4 对重复工具函数定义（analyze_location / analyze_franchise / update_profile / generate_plan）
- **保留策略**:
  - `analyze_location` → v1（含 address/town 参数，功能最全）
  - `update_profile` → v2（dict 推导式 + 人格统计输出）
  - `analyze_franchise` → v1（离线可用，确定性输出）
  - `generate_plan` → v1（含阶段目标和通过条件）
- **行数变化**: 1985 → 1736（-249 行）
- **备份**: `graph/tools.py.backup`
- **验证**: `get_all_tools()` 返回 12 个唯一工具，Agent `--audit` 正常
- **状态**: ✅ 已实施，未提交

---

## 六、健康检查命令

```bash
cd "/Users/wqboo/Code/20-Products/开店Agent"

# 1. 知识库审计（无 API key 也能跑）
python3 开店Agent.py --audit
# 预期: JSON 输出 1432 chunks

# 2. 单次查询（需要设置 DEEPSEEK_API_KEY）
export DEEPSEEK_API_KEY="sk-xxx"
python3 开店Agent.py "县城早餐店10万预算可行性"
# 预期: Markdown 格式分析报告

# 3. 交互式对话
python3 开店Agent.py
# 预期: "开店做生意 Agent (v3 - LangGraph/ReAct)" 提示符
```

---

## 七、Plan F 关联备注

本项目与 Plan F 无关，独立工作流。

---

## 附录 A：待评估方案（非现状）

> ⚠️ **本附录内容均为方案阶段，未写入任何代码、未做任何承诺。**
> 阅读现状仅看一至五章和第六章。本附录仅作为未来 Plan G/H 的输入素材保留，
> 不构成本快照的现状声明。

### A.1 产品设计方向 — 从 CLI Agent 到 SaaS 工作台

#### 问题诊断

当前产品是 CLI 对话 Agent，不符合餐饮创业者的真实工作模式：
- 老板打开工具是为了**完成具体任务**（算账、看铺位、列清单），不是为了聊天
- 真实餐饮产品（美团商家版、客如云、千牛）全部采用 **Dashboard + 模块化表单** 模式
- AI 应是嵌入在工具中的**分析引擎**，而非主导交互界面

#### 参考产品

| 产品 | 借鉴点 |
|------|--------|
| **美团商家版** | Dashboard 首页（今日营收/订单/评价）+ 左侧模块导航 |
| **客如云** | 按业态差异（正餐/快餐/饮品）定制界面，老板助手 AI 洞察卡片 |
| **千牛卖家中心** | 数字中心首页 + 消息驱动 + 轻任务系统 |
| **抖音来客** | 内容运营 + 团购管理 + 达人合作 |

#### 三段式产品架构

```
首页（根据阶段选择入口）
 ├─ 探索模式 → 3 步向导 → 可行性报告（没见过餐饮的人）
 ├─ 筹备模式 → 项目工作台（正在筹备开店的老板）
 └─ 经营模式 → 运营工作台（已有店铺在运营的老板）
```

#### 筹备模式模块（8 个）

| 模块 | 功能 | 交互形态 |
|------|------|---------|
| 项目概览 | 进度条 + 关键指标卡片 + AI 洞察推荐 | Dashboard |
| 选址分析 | 高德地图 + 铺位卡片 + 多铺位对比表 | 地图 + 表格 |
| 竞品调研 | 美团数据聚合 + 价格带/评分分布 | 数据表格 + 图表 |
| 财务测算 | 左侧参数面板 + 右侧动态结果 | 双栏计算器 |
| 证照办理 | 城市×品类自动生成的办证清单 + Gantt 时间线 | Checklist |
| 设备采购 | 设备列表 + 预算追踪 + 增删改 | 库存列表 |
| 开业营销 | 美团/抖音/私域分渠道方案生成 | 方案卡片 |
| 风险评估 | 动态风险登记册 + 缓解措施 + 自动识别 | 风险矩阵 |

#### 经营模式模块（8 个）

| 模块 | 功能 |
|------|------|
| 经营看板 | 今日核心指标 + AI 洞察 + 预警推送 |
| 收支记账 | 每日录入 / CSV 导入 → 月 P&L |
| 数据分析 | 7d/30d/12m 收入趋势 + 时段热力图 |
| 营销效果 | 多渠道 ROI 追踪 |
| 客户反馈 | 差评预警 + 回复建议 |
| 库存管理 | 低库存自动提醒 |
| 人员管理 | 排班 + 绩效 |
| 菜单优化 | 毛利-销量矩阵分析 |
| 预警中心 | 异常事件自动推送（连续 3 天营收下降/成本异常/差评新增）|

#### AI 嵌入方式（非聊天框主导）

| 交互形态 | 占比 | 示例 |
|---------|------|------|
| **按钮触发**（点击生成报告/测算/分析） | 60% | 选址页 → "分析此铺位"按钮 → AI 生成结构化报告 |
| **自动生成**（卡片式洞察 + 预警） | 20% | 经营看板每日自动推送异常卡片 |
| **浮动对话**（右下角 FAB） | 20% | 点击 → 自由提问 → 结构化卡片回复 |

#### "大口章鱼烧"典型流程

> 老板在筹备第二家店（南昌红谷滩），预算 20 万

1. 打开项目概览 → 看进度（58%，还剩 2 个铺位要走访）
2. 选址分析 → 地图显示 3 个候选铺位 → 点"对比"看并排数据
3. 财务测算 → 输入租金 ¥8,000 + 客单价 ¥30 → 看到"日需 85 单回本"
4. 右下角浮动 AI → 点建议"分析万达广场铺位优劣" → 获得结构化分析卡片
5. AI 卡片含操作按钮："将分析加入项目档案"

### A.2 技术架构方案（未实施）

```
Next.js 15 (Frontend)          FastAPI (Backend)           LangGraph (Agent)
    useChat ──── POST /api/chat ──► StreamingResponse ──► graph.astream()
    onData ◄── SSE stream ◄────── async generator ◄──── astream_events()
```

| 层 | 选择 | 理由 |
|----|------|------|
| 前端框架 | Next.js 15 | 用户主力技术栈 |
| UI 库 | React 19 + Tailwind v4 + shadcn/ui | 克制现代，源码可控 |
| 流式通信 | Vercel AI SDK v6 (`useChat`) | 内置 reasoning/tool-call stream parts |
| 后端 | FastAPI + SSE | 异步流式，与 AI SDK 协议兼容 |
| Agent | LangGraph 1.1.9（不动） | 现有核心 |
| 地图 | 高德 JS API（前端直接调用） | 无需后端代理 |

### A.3 Phase 1 实施范围（未实施）

| 优先级 | 内容 |
|--------|------|
| P0 | FastAPI 后端 + SSE 流式对话端点 |
| P0 | Next.js 项目框架 + 三栏布局 + shadcn/ui 组件 |
| P0 | 首页（三段式入口） |
| P0 | 项目概览页（筹备模式入口 Dashboard） |
| P0 | 浮动 AI 助手面板 |
| P1 | 财务测算工具（双栏参数 → 结果） |
| P1 | 选址分析（地图 + 铺位卡片 + 对比） |

**不在 Phase 1**: 经营模式（8 模块）、竞品爬虫、证照生成、设备采购（后续迭代）

### A.4 新增依赖（未加入 requirements.txt）

| 包 | 版本 | 用途 |
|----|------|------|
| `fastapi` | `>=0.115` | Web 框架（已系统安装 0.124.4） |
| `uvicorn` | `>=0.30` | ASGI 服务器（已系统安装 0.33.0） |
| `sse-starlette` | `>=2.0` | SSE 流式支持 |
| 前端 | Next.js 15 + React 19 + Tailwind v4 | `package.json` 待创建 |

### A.5 待解决问题（来自架构审计）

| # | 问题 | 严重度 | 状态 |
|---|------|--------|------|
| 1 | `.env` 文件缺失 — Agent 无法启动 LangGraph 模式 | 🔴 高 | `.env.example` 已创建，`.env` 待用户填写 |
| 2 | `.env.example` 模板缺失 — README 中指向的文件不存在 | 🟡 中 | ✅ 已修复 |
| 3 | `requirements.txt` 中 `langgraph>=0.2.0` 与实际 `1.1.9` 不匹配 | 🟡 中 | ✅ 已修复 (`>=1.1.0`) |
| 4 | `langgraph-checkpoint-sqlite` 已装未用 — 仍用 MemorySaver | 🟢 低 | 后续 |
| 5 | 4 个 prompt 中引用但未注册为 tool 的函数 | 🟡 中 | ✅ tools.py 已修复 |
| 6 | 两套 `ProjectMemory` 实现未统一 | 🟡 中 | 后续 |
| 7 | `fastapi`/`uvicorn` 系统已装但未声明为项目依赖 | 🟡 中 | ✅ 已修复（加入 requirements.txt/pyproject.toml） |
| 8 | `graph/tools.py` 去重重构未提交 | 🟢 低 | 等待提交 |

---

## 附录 B：下一步建议

1. **提交现有改动**: `git add .gitignore docs/ARCHITECTURE_SNAPSHOT.md graph/tools.py && git commit`
2. **创建 `.env.example`**: 解决 README 中 `cp .env.example .env` 找不到文件的问题
3. **更新 `requirements.txt`**: 加入 `fastapi`/`uvicorn`/`sse-starlette`，修正 `langgraph>=1.1`
4. **Phase 1 产品化**: 按 A.3 的方案创建 FastAPI 后端 + Next.js 前端骨架
5. **配置 DeepSeek API Key**: 解除 LangGraph 模式依赖

---

> **本报告为只读快照。附录 A 均为方案规划，不构成本快照的现状声明。可在确认后逐阶段执行。**
