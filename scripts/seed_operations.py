#!/usr/bin/env python3
"""合并种子数据到现有项目（保留总部SKU）。"""

import json
import time
from pathlib import Path

PROJECT_ID = "xinyu-hengtai-dakou"
PROJECT_DIR = Path(__file__).resolve().parent.parent / "project_data" / PROJECT_ID

now = time.time()

profile = {
    "name": "大口章鱼烧",
    "category": "章鱼小丸子/商场小吃档口",
    "city": "新余",
    "district": "渝水区",
    "location": "恒太城五楼美食城",
    "stage": "operating",
    "area_sqm": 10,
    "monthly_rent": 6500,
    "monthly_labor": 10500,
    "monthly_utility_avg": 1600,
    "monthly_utility_min": 1500,
    "monthly_utility_max": 1700,
    "wage_per_person": 3500,
    "current_staff_count": 3,
    "staff_count": 3,
    "transfer_date": "2026-07-01",
}

ops = [
    {"date":"2026-06-20","revenue":2100,"orders":115,"dine_in_revenue":840,"dine_in_orders":45,"delivery_revenue":1260,"delivery_orders":70,"food_cost":735,"packaging_cost":126,"labor":350,"rent_allocated":217,"utility":53,"other_cost":50,"takeout_orders":70,"platform_fee":275,"marketing_cost":42,"inventory_loss":63,"bad_reviews":1,"repeat_orders":38,"new_members":12,"notes":"周末，客流不错，外卖单多","source_type":"客如云"},
    {"date":"2026-06-21","revenue":2450,"orders":135,"dine_in_revenue":980,"dine_in_orders":60,"delivery_revenue":1470,"delivery_orders":75,"food_cost":858,"packaging_cost":148,"labor":350,"rent_allocated":217,"utility":53,"other_cost":55,"takeout_orders":75,"platform_fee":303,"marketing_cost":49,"inventory_loss":74,"bad_reviews":0,"repeat_orders":45,"new_members":18,"notes":"周末高峰，全家福卖得好","source_type":"客如云"},
    {"date":"2026-06-22","revenue":1850,"orders":98,"dine_in_revenue":740,"dine_in_orders":38,"delivery_revenue":1110,"delivery_orders":60,"food_cost":648,"packaging_cost":108,"labor":350,"rent_allocated":217,"utility":53,"other_cost":40,"takeout_orders":60,"platform_fee":242,"marketing_cost":37,"inventory_loss":56,"bad_reviews":2,"repeat_orders":28,"new_members":8,"notes":"周一回落，小雨影响堂食","source_type":"客如云"},
    {"date":"2026-06-23","revenue":1920,"orders":105,"dine_in_revenue":768,"dine_in_orders":42,"delivery_revenue":1152,"delivery_orders":63,"food_cost":672,"packaging_cost":115,"labor":350,"rent_allocated":217,"utility":53,"other_cost":42,"takeout_orders":63,"platform_fee":247,"marketing_cost":38,"inventory_loss":58,"bad_reviews":1,"repeat_orders":32,"new_members":10,"notes":"正常工作日","source_type":"客如云"},
    {"date":"2026-06-24","revenue":1780,"orders":96,"dine_in_revenue":712,"dine_in_orders":35,"delivery_revenue":1068,"delivery_orders":61,"food_cost":623,"packaging_cost":106,"labor":350,"rent_allocated":217,"utility":53,"other_cost":38,"takeout_orders":61,"platform_fee":229,"marketing_cost":36,"inventory_loss":53,"bad_reviews":3,"repeat_orders":25,"new_members":7,"notes":"差评多，配送超时导致","source_type":"客如云"},
    {"date":"2026-06-25","revenue":2050,"orders":112,"dine_in_revenue":820,"dine_in_orders":44,"delivery_revenue":1230,"delivery_orders":68,"food_cost":718,"packaging_cost":123,"labor":350,"rent_allocated":217,"utility":53,"other_cost":45,"takeout_orders":68,"platform_fee":267,"marketing_cost":41,"inventory_loss":62,"bad_reviews":1,"repeat_orders":36,"new_members":14,"notes":"恢复正常，调整了出餐流程","source_type":"客如云"},
    {"date":"2026-06-26","revenue":1980,"orders":108,"dine_in_revenue":792,"dine_in_orders":43,"delivery_revenue":1188,"delivery_orders":65,"food_cost":693,"packaging_cost":119,"labor":350,"rent_allocated":217,"utility":53,"other_cost":43,"takeout_orders":65,"platform_fee":252,"marketing_cost":39,"inventory_loss":59,"bad_reviews":0,"repeat_orders":34,"new_members":11,"notes":"今日数据，待打烊确认","source_type":"客如云"},
]

staff = [
    {"id":"staff-owner","name":"老板","role":"店主","phone":"","health_cert_expiry":"","skills":["章鱼烧制作","备料","收银","对账","采购"],"hourly_wage":0,"monthly_base":0,"hire_date":"2026-07-01","status":"在岗","notes":"老板本人，不计发工资，算机会成本"},
    {"id":"staff-1","name":"员工A","role":"全职店员","phone":"","health_cert_expiry":"","skills":["章鱼烧制作","加料","打包","收银"],"hourly_wage":0,"monthly_base":3500,"hire_date":"2026-01-01","status":"在岗","notes":"全职，月薪3500"},
    {"id":"staff-2","name":"员工B","role":"全职店员","phone":"","health_cert_expiry":"","skills":["章鱼烧制作","加料","打包","备料"],"hourly_wage":0,"monthly_base":3500,"hire_date":"2026-01-01","status":"在岗","notes":"全职，月薪3500"},
    {"id":"staff-3","name":"员工C","role":"全职店员","phone":"","health_cert_expiry":"","skills":["收银","打包","备料","卫生"],"hourly_wage":0,"monthly_base":3500,"hire_date":"2026-01-01","status":"在岗","notes":"全职，月薪3500"},
]

utilities = [
    {"month":"2026-04","water":180,"electricity":920,"notes":""},
    {"month":"2026-05","water":210,"electricity":1050,"notes":"空调季开始"},
    {"month":"2026-06","water":195,"electricity":1120,"notes":"持续高温"},
]

tasks = [
    {"id":"task-001","title":"采购耗材：6粒盒/4粒盒/塑料袋/打包袋","target":"工作台","priority":"high","source":"库存 Agent → 财务 Agent","status":"todo","due_date":"2026-06-27","notes":"库存 Agent 检测到 4 项耗材低于安全库存，财务 Agent 汇总采购清单 ¥187，通知掌柜下单"},
    {"id":"task-002","title":"检查 6/24 差评原因并更新 SOP","target":"SOP作业库","priority":"high","source":"渠道 Agent → SOP Agent","status":"in_progress","due_date":"2026-06-27","notes":"6月24日 3 条差评均为配送超时，SOP Agent 已生成出餐优化建议，待人工确认"},
    {"id":"task-003","title":"审核美团满减活动利润率","target":"渠道外卖","priority":"medium","source":"渠道 Agent → 财务 Agent","status":"todo","due_date":"2026-06-28","notes":"近7天外卖占比 44%，渠道 Agent 检测到手利润偏低，建议降低满减力度"},
    {"id":"task-004","title":"本周备料：章鱼粒+酱料","target":"进货库存","priority":"medium","source":"库存 Agent","status":"todo","due_date":"2026-06-28","notes":"章鱼粒库存偏低，酱料接近安全线，需本周补货"},
    {"id":"task-005","title":"员工健康证到期提醒","target":"员工训练","priority":"low","source":"风控 Agent","status":"todo","due_date":"2026-08-15","notes":"小李健康证 8月20日到期，提前2个月提醒办理"},
]

integrations = [
    {"id":"int-01","name":"客如云 POS","scope":"营业数据","status":"pending_connect","status_label":"待接入","fallback":"手动录日报","available_paths":["API对接","截图OCR"],"notes":"需要客如云账号授权"},
    {"id":"int-02","name":"美团","scope":"外卖渠道","status":"pending_auth","status_label":"待授权","fallback":"截图导入","available_paths":["商家后台截图","API对接"],"notes":""},
    {"id":"int-03","name":"淘宝闪购","scope":"外卖渠道","status":"pending_auth","status_label":"待授权","fallback":"截图导入","available_paths":["后台截图"],"notes":""},
    {"id":"int-04","name":"抖音团购","scope":"团购核销","status":"inactive","status_label":"未开通","fallback":"—","available_paths":["暂未开通抖音团购"],"notes":""},
    {"id":"int-05","name":"本地批发进货","scope":"采购","status":"active","status_label":"手动录入","fallback":"—","available_paths":["进货单拍照","手动录入"],"notes":"目前手动记录进货单"},
]

# 月度营收数据（新余恒太城店真实经营数据）
monthly_revenue = [
    {"year": 2025, "month": 1, "net_profit": 12200, "notes": "2025年1月净利润"},
    {"year": 2025, "month": 2, "net_profit": 22000, "notes": "2025年2月净利润（春节高峰）"},
    {"year": 2025, "month": 3, "net_profit": 6900, "notes": "2025年3月净利润（淡季）"},
    {"year": 2025, "month": 4, "net_profit": 6800, "notes": "2025年4月净利润"},
    {"year": 2025, "month": 5, "net_profit": 10000, "notes": "2025年5月净利润"},
    {"year": 2025, "month": 6, "net_profit": 7000, "notes": "2025年6月净利润"},
    {"year": 2025, "month": 7, "net_profit": 16000, "notes": "2025年7月净利润（暑假高峰）"},
    {"year": 2025, "month": 8, "net_profit": 15000, "notes": "2025年8月净利润（暑假高峰）"},
    {"year": 2025, "month": 9, "net_profit": 6000, "notes": "2025年9月净利润（开学淡季）"},
    {"year": 2025, "month": 10, "net_profit": 10000, "notes": "2025年10月净利润"},
    {"year": 2025, "month": 11, "net_profit": 6000, "notes": "2025年11月净利润（淡季）"},
    {"year": 2025, "month": 12, "net_profit": 6000, "notes": "2025年12月净利润（淡季）"},
    {"year": 2026, "month": 1, "revenue": 37720, "notes": "2026年1月营业款"},
    {"year": 2026, "month": 2, "revenue": 52976, "notes": "2026年2月营业款（春节高峰）"},
    {"year": 2026, "month": 3, "revenue": 27966, "notes": "2026年3月营业款（淡季）"},
    {"year": 2026, "month": 4, "revenue": 75956, "notes": "2026年4月营业款"},
]

# 读取现有 memory.json
memory_path = PROJECT_DIR / "memory.json"
with open(memory_path, "r", encoding="utf-8") as f:
    memory = json.load(f)

memory["profile"] = {**memory.get("profile", {}), **profile}
memory["daily_operations"] = ops
memory["monthly_revenue"] = monthly_revenue
memory["action_tasks"] = tasks
memory["integrations"] = integrations
memory["updated_at"] = now

with open(memory_path, "w", encoding="utf-8") as f:
    json.dump(memory, f, ensure_ascii=False, indent=2)

# 写入员工
labor_path = PROJECT_DIR / "labor.json"
with open(labor_path, "w", encoding="utf-8") as f:
    json.dump({"project_id": PROJECT_ID, "staff": staff, "work_records": [], "updated_at": now}, f, ensure_ascii=False, indent=2)

# 写入水电
util_path = PROJECT_DIR / "utilities.json"
with open(util_path, "w", encoding="utf-8") as f:
    json.dump({"project_id": PROJECT_ID, "records": utilities, "updated_at": now}, f, ensure_ascii=False, indent=2)

print(f"✅ 经营数据填充完成")
print(f"  经营日报: {len(ops)} 条")
print(f"  员工: {len(staff)} 人")
print(f"  月度营收: {len(monthly_revenue)} 条（2025全年利润 + 2026年1-4月营业款）")
print(f"  水电记录: {len(utilities)} 个月")
print(f"  行动任务: {len(tasks)} 条")
print(f"  数据集成: {len(integrations)} 项")
print(f"  SKU 保持不变（保留总部数据）")
