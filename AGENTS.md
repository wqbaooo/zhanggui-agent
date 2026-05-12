# 开店Agent 重构蓝图 v3.0

## 当前问题诊断

### 不是真正的Agent
- 现状：轻量状态机，一问一答，无规划能力
- 本质：自动化检索流程，不是智能体
- 缺失：推理、规划、任务分解、反思、人机协作

### 核心缺失
1. **无规划能力** — 不能生成可执行的开店计划
2. **无推理循环** — 没有ReAct（思考→行动→观察→反思）
3. **知识库粗放** — 视频仅转文字，无结构化提取
4. **数据单薄** — 无真实竞品/成本/市场数据
5. **人机交互弱** — 无中断确认机制，无法协作迭代

---

## 重构目标：真正的餐饮开店Agent

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

### 🔴 Phase 1（立即做）— 核心Agent能力
1. 引入LangGraph，重构状态机为ReAct循环
2. 实现规划节点（Plan生成）
3. 实现人机交互中断机制
4. 修复财务测算公式

### 🟡 Phase 2（近期做）— 知识库升级
5. 视频结构化提取（实体/关系/方法论）
6. QA对生成与向量化检索
7. 修复OCR乱码

### 🟡 Phase 3（近期做）— 数据接入
8. 美团/大众点评爬虫
9. 高德地图增强（县/乡镇）
10. 成本数据库构建

### 🟢 Phase 4（中期做）— 全生命周期
11. 任务管理与进度跟踪
12. 全阶段覆盖（想法→选址→执行→运营）
13. 合同审核工具
14. 图片分析（铺位照片评估）

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

**开始实现：Phase 1 → LangGraph核心架构重构**
