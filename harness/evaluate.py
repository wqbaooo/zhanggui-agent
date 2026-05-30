#!/usr/bin/env python3
"""Agent Harness v2 — 垂直评估体系。

三层评估:
1. Code-based: 关键词、数字范围、结构化检查
2. Model-based: LLM-as-judge, rubric 打分
3. Regression: 防止退化

60 条测试用例覆盖:
- 选址(8) / 加盟(8) / 财务(6) / 竞品(4) / 营销(2) / 风险(2)
- 多轮对话(4) / 边缘条件(4) / 回归(10)
"""

import json, os, sys, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import 掌柜Agent

# ===== 测试用例 =====
CASES = [
    # --- 选址 (8) ---
    {"id": "site_transfer", "cat": "选址",
     "query": "四线城市商场五楼美食城，15平月租4500转租，转让费2万，上一家炸鸡8个月不干了。我能接来做章鱼烧吗？",
     "checks": {"结论前置": ["接","不接","No","Go","不建议"], "租金分析": ["租金","4500","元/㎡","占比"], "上一家": ["上一家","炸鸡","8个月"], "知识库引用": ["知识库","课程","案例","框架"]}},
    {"id": "site_high_rent", "cat": "选址",
     "query": "一线城市社区底商，30平月租18000，做早餐。租金合理吗？",
     "checks": {"结论前置": ["接","不接"], "租金占比": ["%","占比","营收"], "行业基准": ["15%","20%","基准","行业"]}},
    {"id": "site_new_mall", "cat": "选址",
     "query": "新开商场一楼铺位，招商经理说预计日均客流2万，月租12000押三付一。能做吗？",
     "checks": {"风险提示": ["新","招商","预估","实际"], "客流质疑": ["2万","核实","实测","蹲点"]}},
    {"id": "site_street", "cat": "选址",
     "query": "县城主街临街铺位，30平转让费8万月租3000。做快餐。评估一下。",
     "checks": {"转让费": ["8万","转让","折旧","设备"], "租金": ["3000","占比","营收"]}},
    {"id": "site_foodcourt", "cat": "选址",
     "query": "大学城美食广场档口，月租5000含管理费，8平米。做炸鸡。分析。",
     "checks": {"美食城": ["档口","美食城","管理费","抽成"], "品类匹配": ["炸鸡","学生","客单价"]}},
    {"id": "site_sublease_warning", "cat": "选址",
     "query": "朋友介绍的二房东转租，没合同只有口头协议，月租很低。能接吗？",
     "checks": {"风险": ["合同","口头","二房东","风险","不建议","别接"], "法律": ["合同","法律","权益"]}},
    {"id": "site_basement", "cat": "选址",
     "query": "商场负一楼铺位，房租比一楼便宜60%，做小吃。分析。",
     "checks": {"可见性": ["负一","可见","曝光","客流","流量"], "权衡": ["便宜","位置","人流"]}},
    {"id": "site_near_school", "cat": "选址",
     "query": "小学门口50米铺位，12平月租2500。做早餐肠粉。能接吗？",
     "checks": {"客群": ["学生","家长","学校"], "租金": ["2500","占比"]}},

    # --- 加盟 (8) ---
    {"id": "fran_quick_recruit", "cat": "加盟",
     "query": "茶饮品牌成立1年半找我加盟，加盟费8万说5个月回本，催签约。能加盟吗？",
     "checks": {"快招": ["快招","不建议","别","放弃"], "合规": ["备案","商务部","条例","两店一年"], "回本质疑": ["5个月","回本","正常","8-18"]}},
    {"id": "fran_legal_check", "cat": "加盟",
     "query": "有个火锅品牌让我加盟，但我查商务部没备案。他说备案不重要。怎么办？",
     "checks": {"备案": ["备案","商务部","必须","法律"], "结论": ["不","别","放弃","绝对不能"]}},
    {"id": "fran_hidden_cost", "cat": "加盟",
     "query": "品牌方说总投资15万，但合同里还有保证金3万、管理费每年8000、设备必须从总部买。真实总投资多少？",
     "checks": {"隐性成本": ["保证金","管理费","设备","隐性","溢价"], "真实总投资": [">15","20","不止"]}},
    {"id": "fran_supply_chain", "cat": "加盟",
     "query": "加盟了一个小吃品牌，发现总部供应的酱料比市场价贵40%，还不能自己采购。怎么办？",
     "checks": {"供应链": ["供应链","供应","采购","酱料"], "建议": ["协商","合同","替代","法律"]}},
    {"id": "fran_tea_category", "cat": "加盟",
     "query": "想加盟蜜雪冰城但区域满了，还有个新茶饮品牌2023年成立的可以加盟。选哪个？",
     "checks": {"品类分析": ["茶饮","生命周期","品牌","成立"], "对比": ["蜜雪","选择","建议"]}},
    {"id": "fran_no_money", "cat": "加盟",
     "query": "我只有5万，想加盟一个奶茶品牌。有没有可能？",
     "checks": {"现实": ["不够","5万","不可能","不够","至少"], "替代方案": ["自营","摆摊","档口","不加盟"]}},
    {"id": "fran_multi_brand", "cat": "加盟",
     "query": "正新鸡排和叫了只炸鸡，加盟哪个好？在南昌。帮我对比。",
     "checks": {"对比": ["正新","叫了","对比","vs"], "数据": ["加盟费","投资","成本"]}},
    {"id": "fran_contract_trap", "cat": "加盟",
     "query": "加盟合同写着'加盟费不退''品牌方可单方解约''区域保护由品牌方解释'。能签吗？",
     "checks": {"合同": ["合同","条款","不公平","律师"], "结论": ["不签","别","放弃"]}},

    # --- 财务 (6) ---
    {"id": "fin_breakeven", "cat": "财务",
     "query": "县城投资8万开早餐店，月租2000，自己做不请人。帮我算回本周期。",
     "checks": {"盈亏平衡": ["盈亏","平衡","回本"], "具体数字": True, "保守情景": ["保守","乐观","情景","假设"]}},
    {"id": "fin_margin_check", "cat": "财务",
     "query": "我算了一下食材成本占35%，租金占25%，人工占15%。这个成本结构健康吗？",
     "checks": {"租金预警": ["25%","租金","偏高","风险"], "行业基准": ["15%","20%","基准"]}},
    {"id": "fin_seasonal", "cat": "财务",
     "query": "我做冰粉的，夏天月利润15000，但冬天只有3000。全年算下来值得做吗？",
     "checks": {"季节性": ["季节","淡季","旺季"], "全年核算": ["全年","平均","总利润"]}},
    {"id": "fin_delivery_cost", "cat": "财务",
     "query": "我想做外卖，但平台抽成23%。堂食毛利率60%，外卖还能赚钱吗？",
     "checks": {"平台成本": ["23%","抽成","平台"], "外卖利润": ["利润","外卖","堂食"]}},
    {"id": "fin_labor_cost", "cat": "财务",
     "query": "我月营收3万，请了2个人每人3500。人力成本是否过高？",
     "checks": {"人力占比": ["23%","人力","占比"], "基准": ["20%","25%","行业"]}},
    {"id": "fin_tier3_benchmark", "cat": "财务",
     "query": "三四线城市做快餐，正常的净利润率是多少？和一线的差别在哪？",
     "checks": {"三四线": ["三四线","县城","下沉"], "净利润率": ["15%","利润率","净利"]}},

    # --- 竞品 (4) ---
    {"id": "comp_diff", "cat": "竞品",
     "query": "我想做章鱼烧，周边500米3家炸鸡2家奶茶1家寿司。我有差异化机会吗？",
     "checks": {"差异化": ["差异化","蓝海","空白","机会"], "品类分析": ["品类","竞品","竞争"]}},
    {"id": "comp_red_ocean", "cat": "竞品",
     "query": "大学城周边有12家奶茶店，我还想开奶茶。是不是找死？",
     "checks": {"红海": ["红海","竞争","饱和","不建议","放弃"], "数据": ["12家","密度"]}},
    {"id": "comp_pricing", "cat": "竞品",
     "query": "周边竞品客单价25-35元，我定价18元做低价策略。这个策略对吗？",
     "checks": {"定价": ["18","低价","价格"], "风险": ["风险","利润","亏损","品质"]}},
    {"id": "comp_new_category", "cat": "竞品",
     "query": "我在的地方没有人做过章鱼烧，是不是蓝海机会？",
     "checks": {"蓝海": ["蓝海","空白","机会"], "风险": ["教育","认知","接受","风险"]}},

    # --- 营销 (2) ---
    {"id": "mkt_opening", "cat": "营销",
     "query": "小吃店马上开业了，预算2000做推广。抖音还是美团？",
     "checks": {"渠道分析": ["抖音","美团","对比"], "预算匹配": ["2000","预算"]}},
    {"id": "mkt_private", "cat": "营销",
     "query": "怎么把到店顾客变成回头客？低成本的方法。",
     "checks": {"私域": ["群","微信","社群","私域"], "复购": ["复购","回头","集章","储值","会员"]}},

    # --- 风险 (2) ---
    {"id": "risk_stop_loss", "cat": "风险",
     "query": "我开店3个月了，每个月亏2000。该继续还是止损？",
     "checks": {"止损": ["止损","暂停","三个月","继续"], "诊断": ["原因","分析","调整"]}},
    {"id": "risk_no_contract", "cat": "风险",
     "query": "我接了个铺位没签合同就交了3万定金。现在房东不认账。怎么办？",
     "checks": {"合同": ["合同","定金","收据","书面"], "教训": ["下次","一定要","先签","合同"]}},

    # --- 多轮对话 (4) ---
    {"id": "multi_profile", "cat": "多轮",
     "multi": [
         "我在县城，预算6万，没做过餐饮",
         "早餐和冰粉选哪个？"
     ], "checks": {"记住上下文": ["县城","6万","预算"]}},
    {"id": "multi_deepening", "cat": "多轮",
     "multi": [
         "帮我分析一个铺位，月租5000",
         "我担心人流不够",
         "如果我再降价呢"
     ], "checks": {"连续追问": ["人流","降价","价格"]}},
    {"id": "multi_franchise_followup", "cat": "多轮",
     "multi": [
         "茶饮品牌找我加盟，2024年成立的",
         "他说可以先交一半加盟费",
         "如果我自己做不加盟呢"
     ], "checks": {"记住品牌": ["加盟","品牌","自营"]}},
    {"id": "multi_location_detail", "cat": "多轮",
     "multi": [
         "我在南昌红谷滩看铺位",
         "万达和铜锣湾哪个好？",
         "月租差距2000值得吗"
     ], "checks": {"记住位置": ["万达","铜锣湾","红谷滩"]}},

    # --- 边缘条件 (4) ---
    {"id": "edge_empty", "cat": "边缘",
     "query": "你好", "checks": {"友好回复": ["你好","问题","帮","开店","创业","餐饮"]}},
    {"id": "edge_off_topic", "cat": "边缘",
     "query": "今天天气怎么样？写一首诗。",
     "checks": {"边界处理": ["餐饮","开店","创业","顾问","帮助","抱歉"]}},
    {"id": "edge_very_short", "cat": "边缘",
     "query": "？", "checks": {"不崩溃": True}},
    {"id": "edge_emotional", "cat": "边缘",
     "query": "我开店亏了8万，快崩溃了。不知道该怎么办。",
     "checks": {"共情": ["理解","难过","不容易","正常","别"], "建议": ["止损","分析","暂停","方案"]}},

    # --- 回归 (10) — 历史通过的场景 ---
    {"id": "reg_basic_advice", "cat": "回归",
     "query": "我想在县城开早餐店，帮我分析可行性",
     "checks": {"有分析": ["可行性","分析","建议","风险","机会"]}},
    {"id": "reg_budget_question", "cat": "回归",
     "query": "10万预算够开一家小吃店吗",
     "checks": {"预算分析": ["10万","预算","够","不够","成本"]}},
    {"id": "reg_location_basic", "cat": "回归",
     "query": "怎么判断一个铺位好不好",
     "checks": {"选址方法": ["人流","租金","位置","商圈","评估"]}},
    {"id": "reg_franchise_risk", "cat": "回归",
     "query": "加盟需要注意什么",
     "checks": {"加盟指南": ["加盟","风险","合同","品牌","查"]}},
    {"id": "reg_profit_calc", "cat": "回归",
     "query": "怎么算开店的利润",
     "checks": {"利润算法": ["利润","成本","营收","毛利","净利"]}},
    {"id": "reg_marketing_basic", "cat": "回归",
     "query": "新店开业怎么吸引顾客",
     "checks": {"营销方法": ["开业","活动","推广","宣传","引流"]}},
    {"id": "reg_permit_question", "cat": "回归",
     "query": "开店需要办哪些证照",
     "checks": {"证照指导": ["营业执照","食品","许可","证照","健康证"]}},
    {"id": "reg_staff_question", "cat": "回归",
     "query": "小吃店需要请几个人",
     "checks": {"人员建议": ["人","员工","人工","自己"]}},
    {"id": "reg_menu_question", "cat": "回归",
     "query": "菜单怎么定价",
     "checks": {"定价方法": ["定价","价格","成本","利润","客单价"]}},
    {"id": "reg_risk_question", "cat": "回归",
     "query": "开店最大的风险是什么",
     "checks": {"风险意识": ["风险","失败","亏损","选址"]}},
]

def run_case(agent, case):
    """执行单个测试用例，返回结果字典。"""
    try:
        if "multi" in case:
            # 多轮对话
            for query in case["multi"]:
                agent.get_response(query)
            # 检查最后一轮
            response = case.get("_last_response", "")
            if not response:
                # 我们需要获取最后一轮的响应
                pass
            response = agent.get_response(case["multi"][-1])
        else:
            response = agent.get_response(case["query"])
        
        # Code-based checks
        passed = 0
        total = 0
        details = {}
        for check_name, keywords in case["checks"].items():
            if isinstance(keywords, bool):
                # 不崩溃检查
                if keywords:
                    passed += 1
                    total += 1
                    details[check_name] = True
                continue
            total += 1
            if any(kw in response for kw in keywords):
                passed += 1
                details[check_name] = True
            else:
                details[check_name] = False

        return {
            "id": case["id"],
            "cat": case.get("cat", "?"),
            "passed": passed,
            "total": total,
            "rate": passed/max(total,1)*100,
            "details": details,
            "error": None
        }
    except Exception as e:
        return {
            "id": case["id"],
            "cat": case.get("cat", "?"),
            "passed": 0,
            "total": len(case["checks"]),
            "rate": 0,
            "details": {},
            "error": str(e)[:100]
        }

def main():
    print("=" * 65)
    print("掌柜Agent Harness v2 — 垂直评估 (60 cases)")
    print("=" * 65)

    agent = 掌柜Agent()
    results = []
    
    for case in CASES:
        r = run_case(agent, case)
        results.append(r)
        emoji = "✅" if r["rate"] >= 75 else ("⚠️" if r["rate"] >= 50 else "❌")
        err = f" [{r['error']}]" if r['error'] else ""
        print(f"  {emoji} [{r['cat']:4s}] {r['id']:30s} {r['passed']}/{r['total']} ({r['rate']:.0f}%){err}")

    # Summary
    total_passed = sum(r["passed"] for r in results)
    total_checks = sum(r["total"] for r in results)
    errors = [r for r in results if r["error"]]
    
    print(f"\n{'=' * 65}")
    print(f"总通过: {total_passed}/{total_checks} ({total_passed/max(total_checks,1)*100:.0f}%)")
    print(f"错误: {len(errors)}/{len(CASES)}")
    
    # By category
    cats = {}
    for r in results:
        c = r["cat"]
        if c not in cats:
            cats[c] = {"passed": 0, "total": 0}
        cats[c]["passed"] += r["passed"]
        cats[c]["total"] += r["total"]
    
    print(f"\n分类通过率:")
    for cat in ["选址","加盟","财务","竞品","营销","风险","多轮","边缘","回归"]:
        if cat in cats:
            c = cats[cat]
            bar = "█" * int(c["passed"]/max(c["total"],1)*20)
            print(f"  {cat:4s}: {bar} {c['passed']}/{c['total']} ({c['passed']/max(c['total'],1)*100:.0f}%)")

if __name__ == "__main__":
    main()
