# 开店Agent 重构蓝图 v3.0

## 当前进度状态（2026-05-28 更新）

### 🆕 V2 架构升级 — Franchise Decision OS（进行中）

**核心转变：Chat-first Agent → Case-first Workspace**

- **核心对象**：DecisionCase（案件），不是 message history
- **工作流**：5 阶段固定流程（约束 → 机会 → 候选 → 尽调 → 决策）
- **状态**：`v2/state.py` — DecisionCaseState（证据图 + 决策门 + 验证任务 + 矛盾分析）
- **子图**：`v2/workflow.py` — 模块化子图，每阶段独立节点
- **LLM 角色**：仅 reasoning/summarization，不驱动整个循环
- **范围**：仅加盟签约前周期

### ✅ 已完成的工作

#### Phase 1: 核心架构重构 — ✅ 已完成
- **LangGraph + ReAct 架构**：`graph/agent.py` 实现研究→推理→审查工作流
- **GraphState 状态定义**：`graph/state.py` 完整实现画像/计划/推理/证据/风险/输出
- **6 个 LLM 可调工具**：知识库搜索、联网搜索、财务测算、高德地图、加盟分析、画像更新
- **审查节点**：`constitution_check` 实现利润承诺/品牌推荐/风险弱化/数据造假检测
- **人格化对话**：苏格拉底辩证法 + 加盟分析指引

#### Phase 2: 知识库结构化升级 — ✅ 已完成
- **知识库结构**：`knowledge_base/` 完整实现
- **视频转写**：141/162 个视频已完成语音转写
- **RAG 索引**：1302 chunks BM25 索引已构建
- **向量搜索**：`vector_store/` Faiss 索引已实现
- **QA 对**：`qa_pairs.json` 已生成

#### Phase 3: 数据接入 — ✅ 已完成
- **高德地图工具**：`tools/amap_tool.py` 已实现商圈分析
- **联网搜索**：`tools/web_search_tool.py` DuckDuckGo 搜索已实现
- **财务测算**：`tools/finance_tool.py` 盈亏平衡/回本/敏感性分析
- **加盟分析**：`tools/franchise_tool.py` 品牌真实成本和风险分析

#### Phase 4: 产品化 — ✅ 已完成
- **FastAPI 后端**：`server/` 完整实现（chat/finance/projects/audit 路由）
- **Next.js 前端**：`web/` Editorial Bento Agent 工作台
- **总助理接口**：`handle_assistant_request` 结构化调用已实现

#### Phase 5: 测试和评估 — ✅ 已完成
- **60 条测试用例**：`harness/evaluate.py` 覆盖选址/加盟/财务/竞品/营销/风险
- **单元测试**：`tests/` 5 个测试文件
- **技能定义**：`skills/` 7 个垂直领域技能（选址/加盟/财务/竞品/营销/运营/风险）

#### Phase 6: 前端 Editorial Bento 重构 — ✅ 已完成
- **设计风格**：Halo Lab 编辑品牌语言，非深色科技风
- **色彩系统**：`#0A0A0A` 黑框 + `#F5EFE3` 奶油 + `#0F4C3A` 深绿 + `#D9261C` 红 + `#7FE05A` 薄荷
- **字体系统**：Antonio 900（Display）+ JetBrains Mono（标签）+ Noto Sans SC（中文）
- **布局**：黑色画布框架 + 12 列 Bento Grid + 厚边框分隔
- **5 张核心卡片**：Hero 叙事 / 经营状态 / 项目 / 待办 / 天气
- **命令栏**：底部居中，`[ ASK ]` 标签，自然语言输入
- **详情页**：整页导航，黑框 + 奶油色内容卡

---

## 当前问题诊断（已解决）

### ✅ 已解决的问题
1. **架构问题** — 已从轻量状态机升级为 LangGraph + ReAct 架构
2. **推理能力** — 已实现研究→推理→审查工作流
3. **知识库** — 已完成结构化升级和向量化
4. **数据接入** — 已实现高德/联网/财务/加盟工具
5. **人机交互** — 已实现中断确认机制（通过 LangGraph interrupt）

### 🔍 待优化的问题
1. **规划能力** — 可进一步增强 Plan 生成和任务分解
2. **记忆系统** — 可引入 ProjectMemory 长期记忆
3. **爬虫数据** — 可接入美团/大众点评/抖音真实数据
4. **图片分析** — 可实现铺位照片评估

---

## 重构目标：真正的餐饮开店Agent（已实现）

### Agent定义（ReAct + Planning + Reflection）
```
用户输入
    ↓
[思考] 理解意图、分析画像、判断阶段
    ↓
[规划] 生成/更新开店计划（Plan）
    ↓
[行动] 调用工具（检索、搜索、地图、财务、爬虫）
    ↓
[观察] 收集工具返回结果
    ↓
[反思] 评估结果质量、识别风险、判断是否需要更多信息
    ↓
[决策] 
    ├── 需要用户确认 → 中断，生成选项/问题等待输入
    ├── 信息不足 → 追问用户
    └── 可以输出 → 生成回复+更新任务状态
    ↓
[记忆] 归档到项目档案（ProjectMemory）
```

### 全生命周期覆盖

```
┌─────────────────────────────────────────────────────────────┐
│                    餐饮开店Agent 全生命周期                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  【阶段1: 想法验证】                                          │
│   ├─ 品类分析（市场容量、竞争强度、进入门槛）                     │
│   ├─ 预算规划（总投资、资金结构、回本周期）                     │
│   ├─ 能力评估（经验、时间、资金、风险承受力）                   │
│   └─ 可行性报告（Go/No-Go决策）                               │
│                                                             │
│  【阶段2: 选址筹备】                                          │
│   ├─ 商圈扫描（高德API：县/乡镇级别POI分析）                   │
│   ├─ 竞品调研（美团/大众点评爬虫：真实竞品数据）                │
│   ├─ 铺位评估（照片分析、硬件检查、合同审核）                   │
│   ├─ 转让费评估（市场对比、折旧计算）                          │
│   └─ 选址决策报告（A/B/C方案对比）                            │
│                                                             │
│  【阶段3: 开店执行】                                          │
│   ├─ 证照办理（流程清单、材料准备、时间规划）                   │
│   ├─ 装修设计（布局优化、动线设计、成本控制）                   │
│   ├─ 设备采购（清单生成、比价、供应商推荐）                    │
│   ├─ 人员招聘（岗位设计、薪资结构、培训计划）                   │
│   └─ 供应链搭建（供应商筛选、品控标准、库存管理）               │
│                                                             │
│  【阶段4: 运营增长】                                          │
│   ├─ 开业活动（抖音同城、美团新店、私域引流）                   │
│   ├─ 日常运营（成本监控、人员排班、品质管理）                   │
│   ├─ 营销推广（抖音内容、达人合作、团购设计）                   │
│   ├─ 会员体系（储值、积分、复购提升）                         │
│   └─ 数据分析（营业额追踪、成本结构优化、盈利提升）             │
│                                                             │
│  【贯穿全周期】                                                │
│   ├─ 项目档案（跨轮次记忆、进度跟踪、里程碑检查）               │
│   ├─ 风险监控（实时预警、止损建议、合同审核）                   │
│   └─ 任务管理（待办清单、截止日期、完成状态）                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 1: 核心架构重构（LangGraph + ReAct）

### 技术栈
- **LangGraph**: 状态图编排，支持循环、中断、人机交互
- **LangChain**: LLM调用、Prompt管理、工具定义
- **ReAct**: 推理-行动循环

### 状态设计（GraphState）
```python
class GraphState:
    # 用户输入
    user_input: str
    messages: List[BaseMessage]  # 对话历史
    
    # 画像（跨轮次累积）
    profile: Dict[str, Any]  # 城市/品类/预算/经验等
    
    # 计划（核心新增）
    plan: Optional[Plan]  # 开店计划
    current_task: Optional[Task]  # 当前执行任务
    completed_tasks: List[Task]  # 已完成任务
    pending_tasks: List[Task]  # 待办任务
    
    # 推理（ReAct）
    thought: str  # 当前思考
    action: str  # 当前行动
    observation: str  # 观察结果
    
    # 证据
    evidence: List[Evidence]  # 检索到的证据
    
    # 输出
    response: str  # 给用户看的回复
    structured_output: Dict  # 结构化输出
    
    # 人机交互
    interrupt_reason: Optional[str]  # 中断原因
    options: List[str]  # 选项（让用户选择）
    needs_human_input: bool  # 是否需要人工输入
```

### 节点设计

```
[START] 
  ↓
[understand] 理解用户输入（意图+画像提取）
  ↓
[plan] 规划节点（生成/更新计划）
  ↓
[think] 思考节点（ReAct: 分析当前状态，决定下一步）
  ↓
[act] 行动节点（调用工具：检索/搜索/地图/财务/爬虫）
  ↓
[observe] 观察节点（整理工具返回结果）
  ↓
[reflect] 反思节点（评估结果，识别风险，判断下一步）
  ↓
[decide] 决策节点
  ├─ 需要确认 → [interrupt] → 等待用户输入 → [resume]
  ├─ 信息不足 → [ask_user] → 等待用户输入 → [resume]
  └─ 可以输出 → [synthesize] → [END]
```

### 关键能力

#### 1. 规划能力（Plan Generation）
- 将开店目标分解为阶段→任务→子任务
- 每个任务有：描述、截止日期、依赖关系、验收标准
- 支持多方案对比（A/B测试选址、品类）

#### 2. 推理能力（ReAct Loop）
- **思考**: 分析当前画像、已收集证据、计划进度
- **行动**: 选择工具调用（检索/搜索/地图/财务）
- **观察**: 整理工具返回，提取关键信息
- **反思**: 评估是否达到目标，是否需要迭代

#### 3. 人机交互（Human-in-the-loop）
- **中断点**: 
  - 生成Plan后让用户确认/修改
  - 关键决策前让用户选择（A选址 vs B选址）
  - 发现高风险时让用户确认是否继续
- **选项生成**: 不是开放式提问，而是给出结构化选项

#### 4. 记忆系统
- **短期记忆**: 当前对话上下文
- **长期记忆**: 
  - 项目档案（ProjectMemory）：画像、计划、进度
  - 知识库：结构化知识、QA对、案例库

---

## Phase 2: 知识库结构化升级

### 视频处理流程（从转写到结构化）

```
视频文件
  ↓
[Whisper转写] → 原始文本
  ↓
[结构化提取] 
  ├─ 实体识别: 地点、价格、流程、方法论、风险点
  ├─ 关系抽取: 选址方法→适用场景、成本项→计算公式
  ├─ 方法论提取: 步骤1→步骤2→步骤3（带条件判断）
  └─ 案例提取: 背景→决策→结果→经验教训
  ↓
[QA对生成]
  ├─ 从每个视频生成3-5个问答对
  ├─ 问题覆盖：What/How/Why/When/Where
  └─ 答案引用原文片段+结构化总结
  ↓
[向量化]
  ├─ 文本向量化（sentence-transformers）
  ├─ 支持语义检索（不只是关键词匹配）
  └─ 混合检索：BM25 + 向量相似度
```

### 知识库结构
```
knowledge_base/
├── core/                    # 核心结构化知识
│   ├── theories.json        # 理论方法论（360度看商圈、人-流-场模型）
│   ├── cases.json           # 案例库（早餐哥、脸盆姐等）
│   ├── formulas.json        # 计算公式（盈亏平衡、租金营收比）
│   ├── risks.json           # 风险清单（十大坑、止损线）
│   └── checklists.json      # 检查清单（开店流程、证照清单）
│
├── videos/                  # 视频结构化知识
│   ├── transcripts/         # 原始转写文本
│   ├── entities/            # 实体提取结果
│   ├── methods/             # 方法论提取
│   ├── cases/               # 案例提取
│   └── qa_pairs.json        # QA对（用于精准检索）
│
├── documents/               # 文档知识
│   ├── ocr_texts/           # OCR文本
│   ├── structured/          # 结构化提取
│   └── qa_pairs.json        # QA对
│
├── market_data/             # 市场数据（新增）
│   ├── city_costs.json      # 各城市成本基准
│   ├── category_data.json   # 品类市场数据
│   └── brand_data.json      # 品牌加盟数据
│
└── vector_store/            # 向量数据库
    ├── index.faiss          # Faiss索引
    └── metadata.json        # 元数据
```

---

## Phase 3: 数据接入（真实世界数据）

### 美团/大众点评爬虫
```python
class MeituanCrawler:
    """美团/大众点评竞品数据抓取"""
    
    def search_around(self, city: str, district: str, category: str, radius: int = 1000):
        """
        返回周边竞品列表：
        - 店铺名称、评分、人均消费、月销量
        - 主营品类、营业时间、优惠活动
        - 用户评价关键词（口味、服务、环境）
        """
        pass
    
    def analyze_competition(self, competitors: List[Shop]):
        """
        竞争分析：
        - 市场饱和度（同品类密度）
        - 价格带分布
        - 评分分布
        - 差异化机会点
        """
        pass
```

### 抖音本地生活数据
```python
class DouyinCrawler:
    """抖音本地生活数据"""
    
    def search_local_videos(self, city: str, category: str):
        """
        返回同城视频数据：
        - 热门视频内容、点赞量、评论热词
        - 达人探店情况
        - 本地生活话题热度
        """
        pass
```

### 高德地图（细化到县/乡镇）
```python
class AmapEnhancedTool:
    """增强版高德工具"""
    
    def analyze_town(self, city: str, county: str, town: str, category: str):
        """
        乡镇级分析：
        - 人口密度、商圈分布
        - 竞品POI列表
        - 交通设施（公交、停车场）
        - 周边配套（学校、医院、社区）
        """
        pass
```

### 加盟网站爬虫
```python
class FranchiseCrawler:
    """加盟品牌数据抓取"""
    
    def search_brand(self, brand_name: str):
        """
        返回加盟信息：
        - 加盟费、保证金、管理费
        - 总投资预算（一线/二线/三线不同）
        - 门店面积要求
        - 供应链模式
        - 真实门店数据（在营数量、闭店率）
        - 用户评价（口碑）
        """
        pass
```

---

## Phase 4: 提示词工程（Agent人格定义）

### System Prompt 核心要素

```
你是「勇哥餐饮开店Agent」，一位拥有15年经验的独立餐饮创业顾问。

## 核心能力
- 餐饮品类分析与选品决策
- 商圈评估与选址诊断（细化到县/乡镇）
- 财务测算与投资回报分析
- 加盟风险评估与合同审核
- 开店全流程规划与执行跟踪
- 运营策略设计与抖音/美团引流

## 工作模式（ReAct）
1. 理解：分析用户输入，提取画像信息
2. 规划：生成/更新开店计划（含任务分解）
3. 推理：思考→行动→观察→反思
4. 决策：关键节点中断，提供选项让用户确认
5. 输出：专业建议+具体行动+风险提示

## 输出规范
- 阶段性判断：Go / No-Go / Needs More Data
- 核心发现：事实为主，标注假设
- 下一步行动：2-4条具体可执行动作
- 风险提示：按严重程度分级
- 参考依据：标注信息来源（知识库/视频/联网搜索）

## 限制
- 不做任何具体品牌推荐（只给分析方法）
- 不提供虚假数据（无数据时明确说明"暂无数据"）
- 不承诺盈利（只做保守测算）
- 涉及合同/法律问题，建议咨询专业律师
```

---

## Phase 5: 全生命周期覆盖

### 项目档案（ProjectMemory v2）

```python
@dataclass
class ProjectMemory:
    project_id: str
    
    # 画像
    profile: Dict[str, Any]  # 城市/品类/预算/经验/经营方式
    
    # 计划
    plan: Plan  # 开店主计划
    phases: List[Phase]  # 阶段列表
    
    # 进度
    current_phase: str  # 当前阶段
    completed_tasks: List[Task]
    pending_tasks: List[Task]
    
    # 选址
    candidate_sites: List[SiteEvaluation]  # 候选铺位评估
    selected_site: Optional[SiteEvaluation]  # 选定铺位
    
    # 财务
    financial_models: List[FinancialModel]  # 多版本测算
    
    # 风险
    risk_register: List[Risk]  # 风险登记册
    
    # 决策日志
    decisions: List[Decision]  # 所有决策记录
    
    # 里程碑
    milestones: List[Milestone]  # 关键节点
    
    # 沟通历史
    conversation_history: List[Message]
```

---

## 实现优先级

### ✅ Phase 1（已完成）— 核心Agent能力
1. ✅ 引入LangGraph，重构状态机为ReAct循环
2. ✅ 实现规划节点（Plan生成）
3. ✅ 实现人机交互中断机制
4. ✅ 修复财务测算公式

### ✅ Phase 2（已完成）— 知识库升级
5. ✅ 视频结构化提取（实体/关系/方法论）
6. ✅ QA对生成与向量化检索
7. ⚠️ OCR乱码修复（待优化）

### ✅ Phase 3（已完成）— 数据接入
8. ✅ 高德地图增强（县/乡镇）
9. ⚠️ 美团/大众点评爬虫（待实现）
10. ⚠️ 成本数据库构建（待完善）

### ✅ Phase 4（部分完成）— 全生命周期
11. ✅ 任务管理与进度跟踪
12. ✅ 全阶段覆盖（想法→选址→执行→运营）
13. ⚠️ 合同审核工具（待实现）
14. ⚠️ 图片分析（铺位照片评估，待实现）

### 🔴 Phase 5（下一步）— 优化与增强
1. 增强规划能力（Plan 生成和任务分解）
2. 引入 ProjectMemory 长期记忆
3. 接入美团/大众点评/抖音真实数据
4. 实现铺位照片评估
5. 优化 OCR 处理
6. 完善成本数据库

---

## 技术依赖

```requirements.txt
# Agent框架
langgraph>=0.2.0
langchain>=0.3.0
langchain-openai>=0.2.0

# 向量化
sentence-transformers>=3.0
faiss-cpu>=1.8.0

# 爬虫
requests>=2.32.0
beautifulsoup4>=4.12.0
selenium>=4.0.0
playwright>=1.40.0

# 图像分析（可选）
# pillow>=10.0.0
# transformers>=4.40.0

# 现有依赖保持
openai>=1.0.0
pypdf>=4.0.0
duckduckgo-search>=6.0,<7.0
```

---

## 当前项目结构

```
开店Agent/
├── main.py                  # 统一入口（LangGraph 优先 + 降级）
├── 开店Agent.py             # 兼容入口（委托给 main.py）
├── agent_v3.py              # v3.0 Agent 类
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
│   ├── vector_search_tool.py# 向量语义搜索
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
│   ├── video_knowledge/     # 视频课程（162个）
│   ├── vector_store/        # 向量数据库
│   └── qa_pairs.json        # QA 对
│
├── server/                  # FastAPI 后端
│   ├── main.py              # FastAPI 应用
│   ├── routes/              # API 路由（chat/finance/projects/audit）
│   └── stream.py            # 流式响应
│
├── web/                     # Next.js 前端
│   ├── src/
│   │   ├── app/             # 页面路由
│   │   ├── components/      # React 组件
│   │   │   ├── workspace/   # Agent 工作台（Editorial Bento）
│   │   │   ├── artifact/    # 功能组件（财务/选址/竞品等）
│   │   │   ├── chat/        # 对话组件
│   │   │   ├── project/     # 项目组件
│   │   │   └── ui/          # shadcn/ui 基础组件
│   │   └── lib/             # 工具函数
│   └── package.json
│
├── harness/                 # 评估体系
│   └── evaluate.py          # 60 条测试用例
│
├── tests/                   # 单元测试
│   ├── test_case_intelligence.py
│   ├── test_case_repository.py
│   ├── test_philosophy.py
│   ├── test_project_api.py
│   └── test_readiness.py
│
├── skills/                  # 垂直领域技能
│   ├── location_analysis.md # 选址分析
│   ├── franchise_dd.md      # 加盟尽调
│   ├── finance_modeling.md  # 财务建模
│   ├── competitor_analysis.md # 竞品分析
│   ├── marketing_planning.md # 营销策划
│   ├── operations.md        # 运营管理
│   └── risk_assessment.md   # 风险评估
│
└── scripts/                 # 工具脚本
    ├── audit_sources.py     # 知识库审计
    ├── ingest_documents.py  # 文档入库
    ├── video_processor.py   # 视频转写
    └── build_rag_index.py   # RAG 索引构建
```

---

## 下一步行动建议

### 短期优化（1-2周）
1. **增强规划能力** — 改进 Plan 生成和任务分解逻辑
2. **完善记忆系统** — 实现 ProjectMemory 长期记忆
3. **优化 OCR 处理** — 修复文档乱码问题

### 中期增强（1-2月）
4. **接入真实数据** — 美团/大众点评/抖音爬虫
5. **实现图片分析** — 铺位照片评估功能
6. **完善成本数据库** — 各城市/品类成本基准

### 长期目标（3-6月）
7. **全生命周期覆盖** — 从想法到运营的完整跟踪
8. **智能推荐系统** — 基于用户画像的个性化建议
9. **多模态交互** — 支持图片、语音、视频输入

---

**当前状态：核心架构已完成，进入优化和增强阶段**
