#!/usr/bin/env python3
"""大口章鱼烧店铺数据播种 — 7天经营 + SKU + 员工 + 水电"""

import json, time, sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent / "project_data" / "xinyu-hengtai-dakou"
PROJECT_DIR.mkdir(parents=True, exist_ok=True)

TODAY = "2026-06-26"
now = time.time()

# ── 店铺画像 ──
profile = {
    "name": "大口章鱼烧",
    "category": "章鱼小丸子/商场小吃档口",
    "city": "新余",
    "district": "渝水区",
    "location": "恒太城五楼美食城",
    "stage": "operating",
    "area_sqm": 10,
    "monthly_rent": 8500,
    "staff_count": 2,
    "opening_date": "2026-05-22",
}

# ── 7天经营日报（模拟真实波动） ──
ops = [
    {"date":"2026-06-20","revenue":2100,"orders":115,"food_cost":735,"labor":400,"rent_allocated":283,"utility":67,"other_cost":50,"takeout_orders":70,"platform_fee":275,"marketing_cost":42,"inventory_loss":63,"bad_reviews":1,"notes":"周末，客流不错，外卖单多"},
    {"date":"2026-06-21","revenue":2450,"orders":135,"food_cost":858,"labor":400,"rent_allocated":283,"utility":67,"other_cost":55,"takeout_orders":75,"platform_fee":303,"marketing_cost":49,"inventory_loss":74,"bad_reviews":0,"notes":"周末高峰，全家福卖得好"},
    {"date":"2026-06-22","revenue":1850,"orders":98,"food_cost":648,"labor":400,"rent_allocated":283,"utility":67,"other_cost":40,"takeout_orders":60,"platform_fee":242,"marketing_cost":37,"inventory_loss":56,"bad_reviews":2,"notes":"周一回落，小雨影响堂食"},
    {"date":"2026-06-23","revenue":1920,"orders":105,"food_cost":672,"labor":400,"rent_allocated":283,"utility":67,"other_cost":42,"takeout_orders":63,"platform_fee":247,"marketing_cost":38,"inventory_loss":58,"bad_reviews":1,"notes":"正常工作日"},
    {"date":"2026-06-24","revenue":1780,"orders":96,"food_cost":623,"labor":400,"rent_allocated":283,"utility":67,"other_cost":38,"takeout_orders":61,"platform_fee":229,"marketing_cost":36,"inventory_loss":53,"bad_reviews":3,"notes":"差评多，配送超时导致"},
    {"date":"2026-06-25","revenue":2050,"orders":112,"food_cost":718,"labor":400,"rent_allocated":283,"utility":67,"other_cost":45,"takeout_orders":68,"platform_fee":267,"marketing_cost":41,"inventory_loss":62,"bad_reviews":1,"notes":"恢复正常，调整了出餐流程"},
    {"date":"2026-06-26","revenue":1980,"orders":108,"food_cost":693,"labor":400,"rent_allocated":283,"utility":67,"other_cost":43,"takeout_orders":65,"platform_fee":252,"marketing_cost":39,"inventory_loss":59,"bad_reviews":0,"notes":"今日数据，待打烊确认"},
]

# ── SKU 清单 ──
skus = [
    {"id":"sku-001","name":"章鱼粉","category":"食材","unit":"kg","safety_stock":5,"current_stock":3.2,"unit_cost":28,"supplier":"南昌批发市场","batch_cycle_days":15,"consumption_per_day":0.6,"last_purchase_date":"2026-06-20","next_purchase_est":"2026-07-05","status":"active","notes":"核心原料，不可断"},
    {"id":"sku-002","name":"章鱼粒","category":"食材","unit":"kg","safety_stock":3,"current_stock":1.8,"unit_cost":65,"supplier":"南昌海产批发行","batch_cycle_days":10,"consumption_per_day":0.4,"last_purchase_date":"2026-06-18","next_purchase_est":"2026-06-28","status":"active","notes":"单价高，精准备货"},
    {"id":"sku-003","name":"鸡蛋","category":"食材","unit":"个","safety_stock":60,"current_stock":85,"unit_cost":0.8,"supplier":"本地超市","batch_cycle_days":3,"consumption_per_day":18,"last_purchase_date":"2026-06-25","next_purchase_est":"2026-06-28","status":"active","notes":""},
    {"id":"sku-004","name":"面粉（中筋）","category":"食材","unit":"kg","safety_stock":4,"current_stock":5.5,"unit_cost":6,"supplier":"本地超市","batch_cycle_days":7,"consumption_per_day":0.5,"last_purchase_date":"2026-06-24","next_purchase_est":"2026-07-01","status":"active","notes":""},
    {"id":"sku-005","name":"海苔粉","category":"食材","unit":"包","safety_stock":8,"current_stock":6,"unit_cost":12,"supplier":"南昌批发市场","batch_cycle_days":30,"consumption_per_day":0.8,"last_purchase_date":"2026-06-10","next_purchase_est":"2026-07-10","status":"active","notes":""},
    {"id":"sku-006","name":"木鱼花","category":"食材","unit":"包","safety_stock":6,"current_stock":4,"unit_cost":18,"supplier":"南昌批发市场","batch_cycle_days":30,"consumption_per_day":0.6,"last_purchase_date":"2026-06-10","next_purchase_est":"2026-07-10","status":"active","notes":""},
    {"id":"sku-007","name":"酱料（照烧+蛋黄）","category":"食材","unit":"瓶","safety_stock":4,"current_stock":2.5,"unit_cost":22,"supplier":"南昌批发市场","batch_cycle_days":14,"consumption_per_day":0.5,"last_purchase_date":"2026-06-20","next_purchase_est":"2026-07-04","status":"active","notes":"双酱共用"},
    {"id":"sku-008","name":"6粒盒","category":"耗材","unit":"个","safety_stock":200,"current_stock":85,"unit_cost":0.35,"supplier":"本地批发","batch_cycle_days":30,"consumption_per_day":28,"last_purchase_date":"2026-05-20","next_purchase_est":"2026-06-20","status":"active","notes":"⚠️ 已过预计补货日"},
    {"id":"sku-009","name":"4粒盒","category":"耗材","unit":"个","safety_stock":150,"current_stock":42,"unit_cost":0.28,"supplier":"本地批发","batch_cycle_days":30,"consumption_per_day":18,"last_purchase_date":"2026-05-20","next_purchase_est":"2026-06-20","status":"active","notes":"⚠️ 低库存"},
    {"id":"sku-010","name":"9粒圆盒","category":"耗材","unit":"个","safety_stock":100,"current_stock":60,"unit_cost":0.42,"supplier":"本地批发","batch_cycle_days":30,"consumption_per_day":10,"last_purchase_date":"2026-05-18","next_purchase_est":"2026-06-18","status":"active","notes":"⚠️ 已过预计补货日"},
    {"id":"sku-011","name":"塑料袋","category":"耗材","unit":"个","safety_stock":500,"current_stock":180,"unit_cost":0.05,"supplier":"本地批发","batch_cycle_days":15,"consumption_per_day":65,"last_purchase_date":"2026-06-10","next_purchase_est":"2026-06-25","status":"active","notes":"⚠️ 今日应补货"},
    {"id":"sku-012","name":"打包袋","category":"耗材","unit":"个","safety_stock":300,"current_stock":95,"unit_cost":0.08,"supplier":"本地批发","batch_cycle_days":20,"consumption_per_day":38,"last_purchase_date":"2026-06-05","next_purchase_est":"2026-06-25","status":"active","notes":"⚠️ 低库存"},
    {"id":"sku-013","name":"手套","category":"耗材","unit":"双","safety_stock":200,"current_stock":130,"unit_cost":0.15,"supplier":"本地批发","batch_cycle_days":20,"consumption_per_day":12,"last_purchase_date":"2026-06-15","next_purchase_est":"2026-07-05","status":"active","notes":""},
    {"id":"sku-014","name":"小票纸","category":"耗材","unit":"卷","safety_stock":10,"current_stock":4,"unit_cost":3.5,"supplier":"本地批发","batch_cycle_days":30,"consumption_per_day":0.5,"last_purchase_date":"2026-05-15","next_purchase_est":"2026-06-15","status":"active","notes":"⚠️ 已过预计补货日"},
    {"id":"sku-015","name":"清洁用品","category":"耗材","unit":"套","safety_stock":5,"current_stock":2,"unit_cost":15,"supplier":"本地批发","batch_cycle_days":30,"consumption_per_day":0.2,"last_purchase_date":"2026-05-10","next_purchase_est":"2026-06-10","status":"active","notes":"⚠️ 已过预计补货日"},
]

# ── 员工 ──
staff = [
    {"id":"staff-1","name":"老王","role":"店主/制作","phone":"138****6789","health_cert_expiry":"2027-03-15","skills":["章鱼烧制作","备料","打烊","采购","对账"],"hourly_wage":0,"monthly_base":0,"hire_date":"2026-05-22","status":"在岗","notes":"自己守店"},
    {"id":"staff-2","name":"小李","role":"店员","phone":"139****8901","health_cert_expiry":"2026-08-20","skills":["章鱼烧制作","加料","打包","收银"],"hourly_wage":18,"monthly_base":3200,"hire_date":"2026-06-01","status":"在岗","notes":"兼职，健康证8月到期"},
]

# ── 水电费 ──
utilities = [
    {"month":"2026-04","water":180,"electricity":920,"notes":""},
    {"month":"2026-05","water":210,"electricity":1050,"notes":"空调季开始"},
    {"month":"2026-06","water":195,"electricity":1120,"notes":"持续高温"},
]

# ── 行动任务（Agent 协作产出） ──
tasks = [
    {"id":"task-001","title":"采购耗材：6粒盒/4粒盒/塑料袋/打包袋","target":"工作台","priority":"high","source":"库存 Agent → 财务 Agent","status":"todo","due_date":"2026-06-27","notes":"库存 Agent 检测到 4 项耗材低于安全库存，财务 Agent 汇总采购清单 ¥187，通知掌柜下单"},
    {"id":"task-002","title":"检查 6/24 差评原因并更新 SOP","target":"SOP作业库","priority":"high","source":"渠道 Agent → SOP Agent","status":"in_progress","due_date":"2026-06-27","notes":"6月24日 3 条差评均为配送超时，SOP Agent 已生成出餐优化建议，待人工确认"},
    {"id":"task-003","title":"审核美团满减活动利润率","target":"渠道外卖","priority":"medium","source":"渠道 Agent → 财务 Agent","status":"todo","due_date":"2026-06-28","notes":"近7天外卖占比 44%，渠道 Agent 检测到手利润偏低，建议降低满减力度"},
    {"id":"task-004","title":"本周备料：章鱼粒+酱料","target":"进货库存","priority":"medium","source":"库存 Agent","status":"todo","due_date":"2026-06-28","notes":"章鱼粒库存 1.8kg（安全 3kg），酱料 2.5瓶（安全 4瓶），需本周补货"},
    {"id":"task-005","title":"员工健康证到期提醒","target":"员工训练","priority":"low","source":"风控 Agent","status":"todo","due_date":"2026-08-15","notes":"小李健康证 8月20日到期，提前2个月提醒办理"},
]

# ── 集成状态 ──
integrations = [
    {"id":"int-01","name":"客如云 POS","scope":"营业数据","status":"pending_connect","status_label":"待接入","fallback":"手动录日报","available_paths":["API对接","截图OCR"],"notes":"需要客如云账号授权"},
    {"id":"int-02","name":"美团","scope":"外卖渠道","status":"pending_auth","status_label":"待授权","fallback":"截图导入","available_paths":["商家后台截图","API对接"],"notes":""},
    {"id":"int-03","name":"淘宝闪购","scope":"外卖渠道","status":"pending_auth","status_label":"待授权","fallback":"截图导入","available_paths":["后台截图"],"notes":""},
    {"id":"int-04","name":"抖音团购","scope":"团购核销","status":"inactive","status_label":"未开通","fallback":"—","available_paths":["暂未开通抖音团购"],"notes":""},
    {"id":"int-05","name":"本地批发进货","scope":"采购","status":"active","status_label":"手动录入","fallback":"—","available_paths":["进货单拍照","手动录入"],"notes":"目前手动记录进货单"},
]

# ── 汇编 ProjectMemory ──
memory = {
    "project_id": "xinyu-hengtai-dakou",
    "created_at": now - 35 * 86400,
    "updated_at": now,
    "profile": profile,
    "franchise_constraints": {},
    "site_transfer": {},
    "candidate_sites": [],
    "financial_models": [],
    "daily_operations": ops,
    "field_observations": [],
    "risk_register": [],
    "action_tasks": tasks,
    "experiment_log": [],
    "review_reports": [],
    "integrations": integrations,
    "delivery_imports": [],
    "decisions_log": [],
    "artifacts": [],
}

# ── 写入 ──
memory_path = PROJECT_DIR / "memory.json"
memory_path.write_text(json.dumps(memory, ensure_ascii=False, indent=2), encoding="utf-8")

# ── 写入 SKU（SkuCatalog 格式） ──
sku_catalog = {
    "project_id": "xinyu-hengtai-dakou",
    "skus": skus,
    "purchases": [],
    "updated_at": now,
}
(PROJECT_DIR / "skus.json").write_text(json.dumps(sku_catalog, ensure_ascii=False, indent=2), encoding="utf-8")

# ── 写入员工（LaborTracking 格式） ──
labor = {
    "project_id": "xinyu-hengtai-dakou",
    "staff": staff,
    "work_records": [],
    "updated_at": now,
}
(PROJECT_DIR / "labor.json").write_text(json.dumps(labor, ensure_ascii=False, indent=2), encoding="utf-8")

# ── 写入水电 ──
util_path = PROJECT_DIR / "utilities.json"
util_path.write_text(json.dumps(utilities, ensure_ascii=False, indent=2), encoding="utf-8")

print(f"✅ 数据播种完成")
print(f"  项目归档: {memory_path}")
print(f"  7天经营数据: {len(ops)} 条")
print(f"  SKU: {len(skus)} 项（食材 {sum(1 for s in skus if s['category']=='食材')} + 耗材 {sum(1 for s in skus if s['category']=='耗材')}）")
print(f"  员工: {len(staff)} 人")
print(f"  水电记录: {len(utilities)} 个月")
print(f"  行动任务: {len(tasks)} 条")
print(f"  数据集成: {len(integrations)} 项")
print()
print("  现在打开 http://localhost:3005/overview 看看店铺活过来没")
