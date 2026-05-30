# 掌柜Agent v3.0

> 餐饮开店 AI 智能顾问 — 基于 LangGraph/ReAct 架构，集成知识库、财务测算、商圈分析、加盟尽调。

---

## 项目概述

面向餐饮创业者的 AI Agent，覆盖从想法验证到门店运营的全生命周期：

1. **理解意图** — 分析用户输入，识别开店阶段
2. **补齐画像** — 苏格拉底式追问收集城市/品类/预算/经验
3. **检索证据** — 知识库搜索、联网搜索、财务测算、地图分析、加盟分析
4. **诊断风险** — 宪法约束（利润中性/风险前置/事实分离）
5. **制定规划** — Go/No-Go 判断 + 下一步行动

---

## 快速开始

### 后端（Python Agent）

```bash
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 交互式对话
python3 掌柜Agent.py

# 单次查询
python3 掌柜Agent.py "我想用20万在县城开早餐店，帮我分析"

# 总助理接口
echo '{"user_message":"如何选址？"}' | python3 main.py --json
```

### 前端（Next.js）

```bash
cd web
npm install
npm run dev
# 打开 http://localhost:3000
```

### 启动后端 API

```bash
python3 -m uvicorn server.main:app --port 8000
```

---

## 架构

### 后端：LangGraph ReAct

```
[START]
  ↓
[agent] — LLM 决策（苏格拉底辩证法 + 工具选择）
  ↓
[constitution_check] — 宪法审查
  ↓
  ├─ 调工具 → [tools] → 回到 [agent]
  └─ 直接回复 → [END]
```

### 前端：Editorial Bento Workspace

Halo Lab 编辑品牌风格的 Agent 工作台：

- **色彩**：`#0A0A0A` 黑框 + `#F5EFE3` 奶油 + `#0F4C3A` 深绿 + `#D9261C` 红 + `#7FE05A` 薄荷
- **字体**：Antonio（Display）+ JetBrains Mono（标签）+ Noto Sans SC（中文）
- **布局**：黑色画布框架 + 12 列 Bento Grid + 厚边框分隔
- **交互**：平面色块，无阴影无渐变，hover 微动

---

## 项目结构

```
掌柜Agent/
├── main.py                    # 统一入口（LangGraph + 降级）
├── 掌柜Agent.py               # CLI 入口
├── agent_v3.py                # v3.0 Agent 类
├── config.py                  # 全局配置
│
├── graph/                     # LangGraph 核心
│   ├── agent.py               # Agent 图 + ReAct 循环
│   ├── state.py               # GraphState 状态定义
│   ├── tools.py               # 6 个 LLM 工具
│   └── prompts.py             # 系统提示词
│
├── tools/                     # 工具实现
│   ├── rag_tool.py            # BM25 知识库检索
│   ├── vector_search_tool.py  # 向量语义搜索
│   ├── web_search_tool.py     # DuckDuckGo 联网搜索
│   ├── finance_tool.py        # 财务测算
│   ├── amap_tool.py           # 高德地图商圈分析
│   └── franchise_tool.py      # 加盟品牌分析
│
├── models/                    # 数据模型
│   ├── schemas.py             # 总助理接口格式
│   ├── plan.py                # 计划/任务模型
│   └── project.py             # 项目档案模型
│
├── knowledge_base/            # 知识库
│   ├── 掌柜Agent知识库.md
│   ├── video_knowledge/       # 162 个视频课程
│   ├── vector_store/          # Faiss 向量索引
│   └── qa_pairs.json          # QA 对
│
├── server/                    # FastAPI 后端
│   ├── main.py                # FastAPI 应用
│   ├── routes/                # API 路由
│   │   ├── chat.py            # 对话接口
│   │   ├── finance.py         # 财务接口
│   │   ├── projects.py        # 项目接口
│   │   └── audit.py           # 审计接口
│   └── stream.py              # 流式响应
│
├── web/                       # Next.js 前端
│   ├── src/
│   │   ├── app/
│   │   │   ├── page.tsx       # 主页面
│   │   │   └── globals.css    # 设计系统
│   │   ├── components/
│   │   │   ├── workspace/     # Agent 工作台
│   │   │   │   ├── space-shell.tsx    # 空间外壳
│   │   │   │   ├── bento.tsx          # Bento 卡片系统
│   │   │   │   ├── command-bar.tsx    # 命令栏
│   │   │   │   └── cards/             # 5 张核心卡片
│   │   │   ├── artifact/      # 功能组件（财务/选址/竞品等）
│   │   │   ├── chat/          # 对话组件
│   │   │   ├── project/       # 项目组件
│   │   │   └── ui/            # shadcn/ui 基础组件
│   │   └── lib/
│   │       ├── api.ts         # API 客户端
│   │       └── utils.ts       # 工具函数
│   └── package.json
│
├── harness/                   # 评估体系
│   └── evaluate.py            # 60 条测试用例
│
├── tests/                     # 单元测试
├── skills/                    # 垂直领域技能（7 个）
└── scripts/                   # 工具脚本
```

---

## 可用工具

| 工具 | 功能 | 触发场景 |
|------|------|---------|
| `search_knowledge` | 知识库语义搜索（BM25 + 向量混合） | 方法论、案例、避坑经验 |
| `search_web` | DuckDuckGo 联网搜索 | 实时信息、政策、品牌口碑 |
| `calculate_finance` | 财务测算（盈亏平衡/回本/敏感性） | 成本、预算、回本周期 |
| `analyze_location` | 高德地图商圈分析 | 选址、商圈、竞品分布 |
| `analyze_franchise` | 加盟品牌成本和风险分析 | 加盟、品牌、连锁 |
| `update_profile` | 更新用户画像 | 城市/品类/预算等信息 |

---

## 前端设计系统

### 色板

| Token | 色值 | 用途 |
|-------|------|------|
| Black | `#0A0A0A` | 画布框架、文字、边框 |
| Cream | `#F5EFE3` | 主卡片背景 |
| Green | `#0F4C3A` | 次卡片背景（状态/天气） |
| Red | `#D9261C` | 强调卡片、紧急标记 |
| Mint | `#7FE05A` | 小型高亮（药丸/状态点） |

### 字体

| 用途 | 字体 | 规格 |
|------|------|------|
| Display 标题 | Antonio 900 | letter-spacing: -0.03em, line-height: 0.95 |
| 标签/元数据 | JetBrains Mono 500 | 10-11px, letter-spacing: 0.06em, `[ TAG ]` 格式 |
| 中文正文 | Noto Sans SC 500 | 13-15px |

### 布局

- 黑色画布框架 `padding: 14px, border-radius: 24px`
- 12 列网格 `grid-auto-rows: 64px, gap: 10px`
- 卡片 `border-radius: 20px, padding: 18px`
- 响应式：760px 以下折叠为 6 列

---

## API 接口

### 总助理接口

```python
from main import handle_assistant_request

result = handle_assistant_request({
    "user_message": "我想加盟蜜雪冰城，预算30万",
    "task_type": "finance",
    "project_id": "user_123",
    "context": {"city": "杭州"},
})

# 返回
result["response_text"]   # 自然语言回复
result["decision"]        # go | no_go | needs_more_data | conditional_go
result["summary"]         # 摘要
result["risks"]           # 风险列表
result["next_actions"]    # 下一步行动
```

### REST API（FastAPI）

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/chat` | POST | 流式对话（SSE） |
| `/api/chat/sync` | POST | 同步对话 |
| `/api/finance` | POST | 财务测算 |
| `/api/projects/{id}/cockpit` | GET | 项目驾驶舱数据 |
| `/api/projects/{id}/operations` | GET/POST | 经营数据 |
| `/api/projects/{id}/tasks` | GET/POST | 任务管理 |
| `/health` | GET | 健康检查 |

---

## 知识库

- 核心 Markdown 知识：26 个片段
- 视频课程：162 个（141 个已完成语音转写）
- RAG BM25 索引：1302 chunks
- 向量索引：Faiss（可选，需安装 `sentence-transformers`）

---

## 测试

```bash
# 单元测试
python3 -m pytest tests/

# Agent 评估（60 条用例）
python3 harness/evaluate.py
```

---

## 宪法约束

Agent 回答遵循不可违背的原则：

1. **利润中性** — 永不承诺盈利，只做保守假设
2. **风险前置** — 致命风险先讲，不帮合理化冲动决策
3. **事实-建议分离** — 标注信息来源
4. **专业边界** — 不替代律师/会计师
5. **用户利益优先** — 加盟必须展示真实成本
6. **苏格拉底主权** — 关键决策必须中断确认

---

## 技术栈

| 层 | 技术 |
|----|------|
| Agent 框架 | LangGraph + LangChain |
| LLM | DeepSeek V4 Pro / OpenAI |
| 后端 | FastAPI |
| 前端 | Next.js 16 + React 19 + Tailwind v4 |
| UI | shadcn/ui (Base UI) + 自定义 Bento 系统 |
| 向量 | Faiss + sentence-transformers |
| 搜索 | DuckDuckGo |
| 地图 | 高德地图 API |

---

**掌柜Agent** — 餐饮创业者的 AI 经营伙伴。
