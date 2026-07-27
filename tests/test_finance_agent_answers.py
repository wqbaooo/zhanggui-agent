from core.finance_answers import answer_finance_question


PROJECT_ID = "xinyu-hengtai-dakou"


def test_finance_agent_answers_period_total_from_real_rows():
    answer = answer_finance_question(
        "7月1日到7月10日总营业收入、总订单和平均客单价分别是多少？",
        PROJECT_ID,
    )

    assert answer is not None
    assert "¥11,879.78" in answer
    assert "778" in answer
    assert "¥15.27" in answer
    assert "2026-07-01 至 2026-07-10" in answer


def test_finance_agent_refuses_to_claim_real_profit_when_costs_are_incomplete():
    answer = answer_finance_question("我这10天实际净利润是多少？现在可以确认赚钱吗？", PROJECT_ID)

    assert answer is not None
    assert "不能确认" in answer
    assert "¥7,844.97" not in answer
    assert "食材" in answer and "现金" not in answer


def test_finance_agent_explains_platform_deduplication():
    answer = answer_finance_question(
        "美团、淘宝闪购、京东这10天分别多少钱？这些金额能不能再加到客如云营收里？",
        PROJECT_ID,
    )

    assert answer is not None
    assert "美团 ¥1,062.99" in answer
    assert "淘宝闪购 ¥1,007.70" in answer
    assert "京东 ¥427.41" in answer
    assert "不能重复加" in answer


def test_finance_agent_uses_latest_verified_cash_count_without_calling_it_bank_balance():
    answer = answer_finance_question(
        "我现在店里有多少现金？今晚应该留下多少备用金，剩下多少钱存银行？",
        PROJECT_ID,
    )

    assert answer is not None
    assert "2026-07-12 ¥47.00" in answer
    assert "不等于银行卡余额" in answer


def test_finance_agent_compares_two_daily_revenues():
    answer = answer_finance_question(
        "7月1日和7月10日的营业收入相比变化了多少？",
        PROJECT_ID,
    )

    assert answer is not None
    assert "减少 ¥88.94" in answer
    assert "下降 7.79%" in answer


def test_finance_agent_reports_books_are_not_closed():
    answer = answer_finance_question(
        "我这10天的账是否已经完整，可以正式出利润表和现金流量表吗？",
        PROJECT_ID,
    )

    assert answer is not None
    assert "还没有完成" in answer
    assert "利润表" in answer and "现金流量表" in answer


def test_finance_agent_recognizes_natural_books_complete_wording():
    answer = answer_finance_question("账算完整了吗？", PROJECT_ID)

    assert answer is not None
    assert "整套店铺账还没有完成" in answer


def test_finance_agent_answers_debt_from_unified_ledger():
    answer = answer_finance_question("我现在店铺债务和应付款有多少？", PROJECT_ID)

    assert answer is not None
    assert "已过账负债" in answer
    assert "未上传或未确认" in answer


def test_finance_agent_refuses_break_even_until_costs_close():
    answer = answer_finance_question("我的月保本营业额和耗材率是多少？", PROJECT_ID)

    assert answer is not None
    assert "待核算" in answer
    assert "不能用行业默认值" in answer


def test_finance_agent_answers_broad_money_health_question():
    answer = answer_finance_question("我的店在钱方面还有哪些问题？", PROJECT_ID)

    assert answer is not None
    assert "前老板应收" in answer
    assert "收款位置待核对" in answer


def test_finance_agent_keeps_investment_pending_until_posting_details_exist():
    answer = answer_finance_question("我的投资、转让费和回本周期怎么样？", PROJECT_ID)

    assert answer is not None
    assert "门店转让费 ¥40,000.00" in answer
    assert "不计算回本周期" in answer


def test_finance_agent_answers_latest_full_period_from_new_verified_days():
    answer = answer_finance_question("目前累计营收和总订单是多少？", PROJECT_ID)
    assert "2026-07-01 至 2026-07-12" in answer
    assert "¥14,771.48" in answer
    assert "960 单" in answer


def test_finance_agent_answers_missing_inputs_by_store_priority():
    answer = answer_finance_question("我的财务数据还有哪些缺失的？", PROJECT_ID)
    assert "三笔转账" in answer
    assert "重点物料逐日开封" in answer
    assert "线上未打码门店采购" in answer


def test_finance_agent_does_not_invent_unit_profit():
    answer = answer_finance_question("一份章鱼烧能赚多少钱，单份成本是多少？", PROJECT_ID)
    assert "不能给出唯一的单份净利润" in answer
    assert "2袋预拌粉" in answer
    assert "不会伪造每粒克重" in answer

    natural_answer = answer_finance_question("一份章鱼烧能赚多少钱？", PROJECT_ID)
    assert "不能给出唯一的单份净利润" in natural_answer
