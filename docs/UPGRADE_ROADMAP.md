# 开店 Agent 升级路线

> 本文记录当前已完成的小型 MVP，以及后续必须补齐的全栈能力。不要把已规划能力写成已实现能力。

## 已完成：全栈升级基线

### 外部案例库与采集

- 新增 `knowledge_base/cases/structured_cases.json`
  - 已种子化法律/纠纷、超级加盟商、投资人分析、商场档口、单店利润压力等案例
  - 每条案例保留 `source_url`、`source_role`、`confidence`，避免把低置信内容当事实
- 新增 `core/case_repository.py`
  - 支持结构化案例加载、保存、upsert 和相似案例检索
- 新增 `scripts/ingest_external_cases.py`
  - 支持 `--url` 直接采集
  - 支持 `--query` 联网搜索后采集
  - 从文章抽取 title/text，并按加盟、商场、人工、租金、合同、外卖等信号转成 `RestaurantCase`

### ProjectMemory 与经营生命周期

- `models/project.py` 已补齐：
  - `franchise_constraints`：总部约束、强制采购、调价/加品类边界
  - `site_transfer`：转租费、押金、位置、原店数据
  - `daily_operations`：每日营业额、订单、食材、人工、租金摊销、水电、外卖、平台、营销、报损
  - `operation_summary()`：7/30 天经营汇总、净利润、食材率、外卖占比、预警
- 新增 `server/routes/projects.py`
  - `GET /api/projects/{project_id}`
  - `PUT /api/projects/{project_id}/profile`
  - `PUT /api/projects/{project_id}/franchise-constraints`
  - `PUT /api/projects/{project_id}/site-transfer`
  - `GET/POST /api/projects/{project_id}/operations`
  - `GET /api/projects/{project_id}/operations/summary`

### 前端真实数据化

- `经营看板` 已从后端读取项目经营汇总
- `收支记账` 已增加每日经营录入表单
- 已移除这两个关键组件里写死的九江/demo 经营数据
- 无数据时展示空状态，不再把样例当真实经营结果
- 首页已升级为生命周期驾驶舱，左半段筹备链路和右半段 30/60/90 天运营增长同时可见
- 数据分析、营销 ROI、人员、库存、会员、菜单优化已改为统一账本或待接入状态
- 竞品调研、开业营销、设备交接、风险登记已改为新余恒太城接店语境，不展示虚构月销、评分、ROI 或已缓解结论

## 已完成：判断层

### 案例智能

- 新增 `core/case_intelligence.py`
- 支持从用户输入识别：
  - 加盟/自营
  - 商场/美食城/档口等位置类型
  - 低线城市
  - 老板亲自守店 vs 请人模型
- 当前规则覆盖：
  - 老板自营和请人经营必须分开算
  - 加盟约束优先于自营式建议
  - 单店能否脱离老板本人仍赚钱
  - 外卖/团购必须单独算平台扣点和满减
  - 商场美食城不能只看总人流，要看高峰转化、出餐和同层竞品

### 经营哲学方法层

- 新增 `core/philosophy.py`
- 已接入 `graph/agent.py` 的每轮动态 guidance
- 已写入 `graph/prompts.py` 系统契约
- 目标不是输出哲学名词，而是把以下方法内化为经营判断：
  - 苏格拉底追问：用结构化问题逼近关键事实
  - 主要矛盾分析：先抓最影响成败的 1-2 个变量
  - 实践检验：建议必须能变成小实验和复盘
  - 具体问题具体分析：不把别的城市/品牌/地段经验硬套
  - 从真实顾客中来：优先看买不买、为什么不买、买完回不回来

## 仍需补齐：必须继续推进的全栈重点

### 1. 案例入库 Pipeline 强化

当前已有基础采集脚本。下一步要强化：

- 站点适配器：知乎/小红书/抖音/公众号/法院文书/新闻站分开解析
- 去重与可信度：同一事件多源合并，低置信来源不能覆盖高置信来源
- 人工审核队列：低置信案例先入待审核，不直接进入高权重检索
- 失败/成功标签：用统一标签体系沉淀“为什么亏/为什么赚”

当前 schema：

```json
{
  "source_role": "single_store_owner | franchisee | super_franchisee | investor | operator | lawyer | landlord | platform_operator",
  "case_type": "success | failure | dispute | expansion | turnaround",
  "city_tier": "一线 | 二线 | 三四线 | 县城 | 乡镇",
  "location_type": "商场 | 美食城 | 街边 | 社区 | 学校 | 夜市 | 外卖店",
  "category": "小吃 | 快餐 | 茶饮 | 烧烤 | 早餐 | 其他",
  "mode": "加盟 | 自营 | 联营",
  "scale": "1店 | 2-5店 | 10店+ | 区域代理",
  "failure_reason": [],
  "success_pattern": [],
  "warning_signal": [],
  "agent_rule": "",
  "source_url": "",
  "confidence": "low | medium | high"
}
```

### 2. ProjectMemory 统一深化

当前已把加盟约束、转租信息、经营流水接入 `models/project.py`。仍需统一 `core/task_manager.py` 的任务/里程碑概念。

目标统一为：

- `ProjectProfile`
- `FranchiseConstraints`
- `SiteTransferDeal`
- `DailyOperationEntry`
- `DecisionLog`
- `ExperimentLog`
- `ReviewReport`

### 3. 前端真实数据化扩展

当前 `经营看板`、`收支记账` 已接真实 API。库存、人员、营销 ROI、会员、菜单、竞品和开业营销已移除虚构结果，下一步是补录入与导入能力。

目标：

- 空状态：没有数据时明确提示“尚未录入”
- 录入表单：每日经营数据、外卖数据、库存损耗、营销动作、竞品照片、设备交接、会员触达
- 数据读取：从后端项目档案读取，不在组件里写死旧城市或样例结果
- 报告输出：7 天复盘、30 天复盘、止损预警

### 4. 相似案例检索升级

当前已在 `core/case_intelligence.py` 接入结构化案例检索。下一步要把检索结果与向量 RAG、城市/品类/合同字段做混合排序。

检索维度：

- 城市层级
- 品类
- 加盟/自营
- 商场/街边/社区等位置
- 转租/新铺
- 老板亲自守店/请人
- 预算区间
- 租金区间

### 5. 复盘飞轮

目标：真实门店越用，Agent 越懂餐饮。

流程：

```text
用户咨询
  -> 生成计划
  -> 执行记录
  -> 每日经营数据
  -> 7/30 天复盘
  -> 结构化案例
  -> 反哺下次判断
```

## 验证命令

```bash
python3 -m pytest -q
python3 -m py_compile main.py server/main.py server/stream.py server/routes/projects.py graph/agent.py graph/prompts.py core/readiness.py core/case_intelligence.py core/philosophy.py core/case_repository.py scripts/ingest_external_cases.py
cd web && npm run lint && npm run build
```
