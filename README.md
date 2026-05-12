# 开店做生意 Agent v3.0

> 基于 LangGraph/ReAct 的餐饮开店智能 Agent，集成勇哥说餐饮理论、视频课程索引和真实数据工具。

---

## 📋 项目概述

这是一个面向餐饮创业者的智能规划 Agent。v3.0 版本基于 **LangGraph/ReAct 架构**重新构建，不再是简单的关键词检索，而是具备真正推理能力的 Agent：

1. **理解意图**：分析用户输入，识别开店阶段（想法验证/选址筹备/开店执行/运营增长）
2. **补齐画像**：通过苏格拉底式追问收集城市、品类、预算、经验等关键信息
3. **检索证据**：调用知识库搜索、联网搜索、财务测算、地图分析、加盟分析等工具
4. **诊断风险**：基于宪法约束（利润中性/风险前置/事实分离）评估风险
5. **制定规划**：生成阶段性判断（Go/No-Go/Needs More Data）和下一步行动

**双架构兼容**：配置 LLM API key 时启用 LangGraph/ReAct（推荐），无 key 时自动降级到旧状态机。

---

## 🚀 快速开始

### 1. 安装依赖

```bash
cd /Users/wqboo/Documents/MIND/02-Projects/开店Agent
pip install -r requirements.txt
```

> **注意**：如果需要视频转写功能，需额外安装 ffmpeg：
> - macOS: `brew install ffmpeg`
> - Ubuntu: `sudo apt install ffmpeg`

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入你的 API key
```

最少配置（只有 DeepSeek key 也能完整运行）：
```bash
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 3. 启动 Agent

**交互式对话（推荐）**
```bash
python3 开店Agent.py
```

**单次查询**
```bash
python3 开店Agent.py "我想用20万在县城开早餐店，帮我分析"
```

**审计知识库状态**
```bash
python3 开店Agent.py --audit
```

**总助理接口测试（JSON 模式）**
```bash
echo '{"user_message":"如何选址？"}' | python3 开店Agent.py --json
```

---

## 🏗️ 架构说明

### LangGraph v3.0 状态图

```
[START]
  ↓
[agent] —— LLM 决策节点（苏格拉底辩证法 + 工具选择）
  ↓
[constitution_check] —— 宪法审查（利润承诺/品牌推荐/风险弱化/数据造假检测）
  ↓
  ├─ 需要调工具 ──→ [tools] —— ToolNode 执行（搜索/财务/地图/加盟/画像更新）
  │                      ↓
  └─ 直接回复 ──→ [END]     回到 [agent] 继续推理
```

### 核心组件

| 模块 | 文件 | 说明 |
|------|------|------|
| 统一入口 | `main.py` | LangGraph 优先 + 旧架构降级，总助理接口 |
| Agent 图 | `graph/agent.py` | ReAct 循环：agent → 宪法审查 → tools → agent |
| 状态定义 | `graph/state.py` | GraphState：画像/计划/推理/证据/风险/输出 |
| 工具定义 | `graph/tools.py` | 6 个 LLM 可调工具 |
| 系统提示 | `graph/prompts.py` | 苏格拉底辩证法 + 宪法约束 + 加盟分析指引 |
| 数据模型 | `models/schemas.py` | AssistantRequest/Response 总助理接口格式 |
| 旧架构 | `core/session.py` | 状态机（无 API key 时降级使用） |

### 可用工具

| 工具 | 功能 | 触发场景 |
|------|------|----------|
| `search_knowledge` | 知识库语义搜索（BM25 + 向量混合） | 查询方法论、案例、避坑经验 |
| `search_web` | DuckDuckGo 联网搜索 | 查实时信息、政策、品牌口碑 |
| `calculate_finance` | 财务测算（盈亏平衡/回本/敏感性） | 涉及成本、预算、回本周期 |
| `analyze_location` | 高德地图商圈分析 | 涉及选址、商圈、竞品分布 |
| `analyze_franchise` | 加盟品牌真实成本和风险分析 | 涉及加盟、品牌、连锁 |
| `update_profile` | 更新用户画像 | 获取到城市/品类/预算等信息时 |

---

## 📁 项目结构

```
开店Agent/
├── main.py                  # 统一入口（LangGraph 优先 + 降级）
├── 开店Agent.py             # 兼容入口（委托给 main.py）
├── requirements.txt         # 依赖清单
├── .env.example             # 环境变量模板
├── config.py                # 全局配置
│
├── graph/                   # LangGraph v3.0 核心
│   ├── agent.py             # Agent 图构建 + ReAct 循环
│   ├── state.py             # GraphState 状态定义
│   ├── tools.py             # 工具定义（LLM function calling）
│   └── prompts.py           # 系统提示词 + 节点提示词
│
├── core/                    # 旧架构（降级备用）
│   ├── session.py           # Session 状态机
│   ├── state_machine.py     # 状态流转
│   └── orchestrator.py      # 编排器
│
├── nodes/                   # 旧架构节点（意图/画像/检索/风险/回复）
│
├── tools/                   # 工具实现
│   ├── rag_tool.py          # BM25 知识库检索
│   ├── vector_search_tool.py# 向量语义搜索（可选）
│   ├── web_search_tool.py   # 联网搜索
│   ├── finance_tool.py      # 财务测算
│   ├── amap_tool.py         # 高德地图
│   └── franchise_tool.py    # 加盟分析
│
├── models/                  # 数据模型
│   ├── schemas.py           # 总助理接口格式
│   ├── plan.py              # 计划/任务模型
│   └── project.py           # 项目档案模型
│
├── knowledge_base/          # 知识库
│   ├── 开店Agent知识库.md    # 核心 Markdown 知识
│   ├── document_knowledge/  # PDF/文档抽取
│   └── video_knowledge/     # 视频课程（162个）
│
└── scripts/                 # 工具脚本
    ├── audit_sources.py     # 知识库审计
    ├── ingest_documents.py  # 文档入库
    ├── video_processor.py   # 视频转写
    └── build_rag_index.py   # RAG 索引构建
```

---

## 🔌 总助理接口

Agent 支持被外部系统（总助理）通过结构化接口调用：

```python
from main import handle_assistant_request

result = handle_assistant_request({
    "user_message": "我想加盟蜜雪冰城，预算30万",
    "task_type": "finance",      # general | profile | site_eval | finance | permit | marketing | risk_review
    "project_id": "user_123",    # 可选，用于会话隔离
    "context": {"city": "杭州"},  # 可选，已有上下文
})

# 返回字段
print(result["response_text"])   # 自然语言回复
print(result["decision"])        # go | no_go | needs_more_data | conditional_go
print(result["summary"])         # 摘要
print(result["risks"])           # 风险列表
print(result["next_actions"])    # 下一步行动
print(result["scores"])          # 评分
```

CLI 测试方式：
```bash
echo '{"user_message":"如何选址？"}' | python3 main.py --json
```

---

## 📊 知识库状态

运行 `python3 开店Agent.py --audit` 查看最新状态：

- 核心 Markdown 知识片段：26 个
- 视频课程 JSON：162 个
- 视频已完成语音转写：141/162 个
- PDF《餐饮选址实用指南》：已登记，待 OCR
- RAG BM25 索引：1302 chunks

---

## 🛠️ 进阶配置

### 向量化检索（可选，提升语义搜索质量）

```bash
pip install numpy sentence-transformers faiss-cpu
```

运行向量索引构建：
```bash
python3 scripts/build_rag_index.py --vector
```

### 视频转写入库（可选，耗时较长）

```bash
python3 scripts/video_processor.py --use-whisper --whisper-model small --limit 3
```

---

## 📝 使用示例

### 示例1：选址咨询
```bash
python3 开店Agent.py "我在新余恒太城看中了一个铺位，月租8000，30平米，做早餐怎么样？"
```

Agent 会自动：
1. 用 `update_profile` 记录城市/商圈/预算/品类
2. 用 `analyze_location` 分析恒太城周边竞品和客流
3. 用 `calculate_finance` 测算盈亏平衡点
4. 给出阶段性判断和风险提示

### 示例2：加盟防骗
```bash
python3 开店Agent.py "我想加盟正新鸡排，加盟费3.5万，总投资说20万，靠谱吗？"
```

Agent 会自动：
1. 用 `analyze_franchise` 分析品牌隐性成本
2. 用 `search_web` 搜索闭店率和加盟商投诉
3. 列出签约前必须确认的问题清单
4. 给出 Conditional Go / No-Go 判断

---

## ⚠️ 重要原则

Agent 的回答遵循以下不可违背的宪法约束：

1. **利润中性**：永不承诺盈利，只做保守假设
2. **风险前置**：致命风险先讲，不帮用户合理化冲动决策
3. **事实-建议分离**：标注信息来源（知识库/搜索/测算/地图）
4. **专业边界**：不替代律师/会计师，超出能力说"我不知道"
5. **用户利益优先**：不存在"友情推荐"，加盟必须展示真实成本
6. **苏格拉底主权**：关键决策必须中断确认，追问有明确目的

---

## 🔄 版本更新

### v3.0 (2026-05-10) — LangGraph 重构
- 引入 LangGraph/ReAct 架构，LLM 真正驱动推理循环
- 实现宪法审查节点（自动检测违规输出）
- 支持双架构：LangGraph（有 key）/ 旧状态机（无 key）
- 新增 6 个 LLM 自主调用工具（知识库/联网/财务/地图/加盟/画像）
- 苏格拉底辩证法系统提示词

### v2.0 (2026-04-19)
- 轻量状态机架构
- 整合 162 个视频课程
- DeepSeek LLM 可选接入

### v1.0 (2026-04)
- 初始版本
- 关键词搜索和视频推荐

---

## 📚 参考资源

- [勇哥说餐饮 - 抖音账号](https://www.douyin.com/user/xxxxxx)
- [MIND 记忆宫殿 - 知识检索系统](/Palace/)

---

**祝您创业顺利！** 🍀
