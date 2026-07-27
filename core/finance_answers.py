"""Deterministic, evidence-backed answers for core owner finance questions."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from models.operating_ledger import OperatingLedger
from models.finance_ledger import FinanceLedger
from models.project import ProjectMemory
from models.store_facts import StoreFactBook


def answer_finance_question(message: str, project_id: str, previous_message: str = "") -> str | None:
    """Answer high-value finance questions without relying on model improvisation."""
    text = message.replace(" ", "")
    finance = FinanceLedger.for_project(project_id)
    if _is_date_coverage_question(text):
        from core.finance_agent import answer_finance_question as answer_structured_finance_question

        first, last = finance.period_bounds(project_id)
        if not first:
            return "当前还没有可用于逐日核对的营业或资金记录。"
        end = max(last or first, date.today().isoformat())
        result = answer_structured_finance_question(
            finance,
            project_id,
            message,
            first,
            end,
            use_model=False,
        )
        return str(result["answer"])
    memory = ProjectMemory.load(project_id)
    if not memory or not memory.daily_operations:
        return None
    all_entries = sorted(memory.daily_operations, key=lambda item: str(item.get("date", "")))
    entries = _filter_date_range(message, all_entries)
    ledger = OperatingLedger.load(project_id)
    overview = finance.finance_overview(project_id)
    operating_facts = StoreFactBook.load(project_id).finance_summary()

    if _is_follow_up(text) and previous_message:
        text = (previous_message + "；" + message).replace(" ", "")

    if any(term in text for term in ("缺失", "还要录入", "少什么", "哪些没录", "信息不全")):
        return (
            "当前最影响利润和现金判断的缺口，按优先级是：\n"
            "1. 总部¥13,791货款三笔转账各自的准确日期与金额；\n"
            "2. 7月5日后重点物料逐日开封数量和每周实盘余量；\n"
            "3. 平台佣金、配送费、商家承担优惠的完整结算单；\n"
            "4. 水电燃气首张账单、实际加班时数；\n"
            "5. 线上未打码门店采购的逐笔实付金额与到货日期。\n"
            "这些字段补齐后，才能把单份成本、贡献毛利率、保本营业额和真实净利润从估算升级为正式值。"
        )

    if any(term in text for term in ("一份能赚", "能赚多少钱", "能赚多少", "单份成本", "一份成本", "每份成本", "利润点")):
        return (
            "目前不能给出唯一的单份净利润。已确认规格包括基本款6粒、DIY双拼8粒、全家福9粒，"
            "一桶面使用2袋预拌粉、36个鸡蛋、1勺海苔粉、2包调味料和8500ml水，经验上约支撑1000元营业额。"
            "鸡蛋一箱进价已确认¥216，食用油按老板要求暂不计；但鸡蛋箱内数量、酱料铺料量、包装实际开封和平台实扣费未闭合。产品会先按“每桶/每包使用天数”反推区间，"
            "不会伪造每粒克重；完成连续盘点后再输出各SKU的售价、变动成本、贡献毛利和贡献毛利率。"
        )

    if any(term in text for term in ("员工工资", "人工成本", "老板工资", "机会成本")):
        return (
            "当前员工7—8月固定工资为¥5,200/月，加班¥16/小时；后续招聘控制在¥4,000以内只是目标，不能算当前成本。"
            "老板计划按¥4,000/月给自己发管理工资。报告会同时展示不含老板报酬的经营利润，以及扣除¥4,000老板管理报酬后的老板收益，"
            "避免把老板取款、工资和机会成本混在一起。"
        )

    if any(term in text for term in ("库存基线", "首批进货", "库存成本", "进货多少")):
        return (
            "当前库存主基线是7月5日总部补货：18种、75件、¥13,791，货已到。"
            "这笔采购先进入库存资产，不能在7月5日一次性全算成本。旧老板留下的存货大多约一周内耗尽，包装耗材余量较多，"
            "因此另列“承接库存未定价”差异；线上补充采购需排除个人商品后再并入。"
        )

    if any(term in text for term in ("供应商", "蔬菜", "鸡蛋", "本地采购", "月结")):
        return (
            f"目前已识别本地供应商7张送货单，应付合计 {_minor_money(operating_facts['local_supplier_payable_minor'])}。"
            f"蔬菜等短保食材 {_minor_money(operating_facts['direct_use_food_cost_minor'])} 按当期耗用记录；"
            f"7月5日鸡蛋一箱 {_minor_money(operating_facts['inventory_purchase_minor'])} 先进入库存。"
            "供应商采用记账后统一结算，所以当前形成应付供应商，不虚构银行卡已付款；食用油按老板要求暂不计。"
        )

    if _is_completeness_question(text):
        pending = len(ledger.list_facts("need_review"))
        return (
            "当前已录入期间的营业收入主账已经形成，但整套店铺账还没有完成，暂不能正式出具利润表和现金流量表。\n"
            f"- 已确认：{overview['period_start']} 至 {overview['period_end']} 营业收入 {_minor_money(overview['revenue_minor'])}、{overview['orders']} 单\n"
            f"- 未闭合：{'、'.join(overview.get('missing_inputs') or [])}\n"
            f"- 已关账：{overview.get('closed_days', 0)}/{overview.get('sales_days', 0)} 个营业日\n"
            f"- 账务流程：还有 {pending} 条经营事实待确认。"
        )

    if any(term in text for term in ("前老板", "代收", "待转")):
        return (
            f"前老板已于7月7日转回代收款 {_minor_money(operating_facts['former_owner_transfer_minor'])}。"
            "这不会新增营业收入：销售发生时已经按销售日期确认；转账只减少前老板应收并增加已确认银行资金。"
            f"当前账面仍有前老板应收 {_minor_money(overview['funds_minor']['former_owner_receivable'])}，需要继续按平台结算明细核销。"
        )

    if _is_platform_question(text):
        view = ledger.reconciliation_view()
        amounts = {item["platform"]: item["amount"] for item in view.get("by_platform", [])}
        return (
            f"当前对账资料：美团 {_money(amounts.get('meituan', 0))}、"
            f"淘宝闪购 {_money(amounts.get('taobao_flash', 0))}、京东 {_money(amounts.get('jd', 0))}。"
            "这些是渠道经营/结算明细，默认不能重复加到客如云主营业收入。"
            "京东是否属于客如云覆盖范围仍待确认，确认前单独列示，不擅自并入总营收。"
        )

    if _is_cash_question(text):
        cash_count = operating_facts.get("latest_cash_count")
        if cash_count:
            return (
                f"最近一次真实打烊实点是 {cash_count['date']} {_minor_money(cash_count['amount_minor'])}。"
                "这是POS机内实际现金，不等于银行卡余额，也不代表累计现金流。"
                "现金表口径为：早班记录开门时POS现金，晚班记录当天现金收款，打烊实点用于与客如云现金及现金支出核对。"
            )
        latest_close = finance.daily_close(project_id, overview["period_end"])
        if latest_close.get("status") == "open" or "cash_count" in latest_close.get("missing_inputs", []):
            return (
                "当前现金余额未知，不能计算剩余存款金额。"
                "需要先录入期初备用金、当天现金销售、现金退款/支出和打烊实点现金。"
                "本店固定留存备用金为500元；在实点现金前，不能判断当日应存银行多少钱。"
            )

    if _is_profit_question(text):
        if overview.get("profit_status") != "confirmed":
            return (
                "目前不能确认当前已录入期间的实际净利润，也不能据此确认赚了多少钱。"
                f"已确认营业收入 {_minor_money(overview['revenue_minor'])}，但利润仍缺："
                f"{_missing_cost_labels(overview.get('missing_inputs') or [])}。"
                "现有估算成本只能用于试算，不能作为真实利润。"
            )
        return f"该期间已确认净利润为 {_minor_money(overview['net_profit_minor'])}。"

    if any(term in text for term in ("债务", "负债", "欠款", "应付")):
        liabilities = overview["liabilities_minor"]
        total = sum(liabilities.values())
        return (
            f"当前已过账负债合计 {_minor_money(total)}："
            f"供应商应付 {_minor_money(liabilities['supplier_payable'])}、"
            f"工资应付 {_minor_money(liabilities['salary_payable'])}、"
            f"借款 {_minor_money(liabilities['loans'])}、"
            f"应计及其他应付 {_minor_money(liabilities['accrued_payables'])}。"
            "未上传或未确认的债务不包含在内。"
        )

    if any(term in text for term in ("投资", "转让费", "首批进货", "回本")):
        pending = overview.get("pending_capital_items") or []
        pending_text = "、".join(f"{item['title']} {_minor_money(item['amount_minor'])}" for item in pending) or "无"
        return (
            f"已过账老板投入 {_minor_money(overview['owner_equity_minor']['invested'])}。"
            f"已记录但待确认付款来源和资产口径的项目：{pending_text}。"
            "在这些投资完成过账且净利润闭合前，不计算回本周期。"
        )

    if "现金流" in text:
        cash_flow = overview["cash_flow_minor"]
        return (
            f"该期间已过账现金流：经营活动 {_minor_money(cash_flow['operating'])}、"
            f"投资活动 {_minor_money(cash_flow['investing'])}、筹资活动 {_minor_money(cash_flow['financing'])}，"
            f"资金净变动 {_minor_money(cash_flow['net_change'])}。"
            "尚未完成打烊现金实点和银行对账，因此这是已过账流量，不是已核对的期末可用现金。"
        )

    if any(term in text for term in ("成本构成", "成本明细", "费用构成", "耗材率", "毛利", "保本")):
        if overview.get("profit_status") != "confirmed":
            return (
                f"目前只能确认营业收入 {_minor_money(overview['revenue_minor'])}，"
                f"仍缺 {_missing_cost_labels(overview.get('missing_inputs') or [])}。"
                "因此毛利率、耗材率和保本营业额都必须显示为待核算，不能用行业默认值替代。"
            )

    if any(term in text for term in ("最高", "最低", "峰值")):
        high = max(entries, key=_revenue)
        low = min(entries, key=_revenue)
        diff = _revenue(high) - _revenue(low)
        return (
            f"{entries[0]['date']} 至 {entries[-1]['date']}中，营业收入最高是 {high['date']} {_money(_revenue(high))}；"
            f"最低是 {low['date']} {_money(_revenue(low))}；相差 {_money(diff)}。"
        )

    dates = _extract_dates(message, entries)
    if len(dates) >= 2 and any(term in text for term in ("相比", "变化", "增加", "下降")):
        first, second = dates[0], dates[1]
        delta = _revenue(second) - _revenue(first)
        pct = delta / _revenue(first) * 100 if _revenue(first) else 0
        direction = "增加" if delta >= 0 else "减少"
        trend = "上升" if delta >= 0 else "下降"
        return (
            f"{first['date']}营业收入 {_money(_revenue(first))}，{second['date']}为 {_money(_revenue(second))}；"
            f"{direction} {_money(abs(delta))}，{trend} {abs(pct):.2f}%。"
            "这是两个单日的描述性比较，不能仅凭两天判断长期趋势。"
        )

    if _is_total_question(text):
        total_revenue = sum(_revenue(item) for item in entries)
        total_orders = sum(int(item.get("orders", 0) or 0) for item in entries)
        avg = total_revenue / total_orders if total_orders else 0
        return (
            f"数据范围：{entries[0]['date']} 至 {entries[-1]['date']}。\n"
            f"- 总营业收入：{_money(total_revenue)}\n"
            f"- 总订单：{total_orders} 单\n"
            f"- 平均客单价：{_money(total_revenue)} ÷ {total_orders} = {_money(avg)}/单。"
        )
    if any(term in text for term in ("钱", "账", "营收", "收入", "成本", "费用", "利润", "现金", "应收", "应付", "资金")):
        funds = overview["funds_minor"]
        liabilities = overview["liabilities_minor"]
        return (
            f"营业数据范围：{entries[0]['date']} 至 {entries[-1]['date']}。\n"
            f"- 营业收入：{_minor_money(overview['revenue_minor'])}，{overview['orders']} 单\n"
            f"- 净利润：{_minor_money(overview['net_profit_minor'])}，当前状态 {'已确认' if overview['profit_status'] == 'confirmed' else '待核算'}\n"
            f"- 前老板应收：{_minor_money(funds['former_owner_receivable'])}\n"
            f"- 收款位置待核对：{_minor_money(funds['unclassified_receipts'])}\n"
            f"- 已过账负债：{_minor_money(sum(liabilities.values()))}\n"
            f"- 当前缺口：{_missing_cost_labels(overview.get('missing_inputs') or [])}。"
        )
    return None


def _revenue(entry: dict[str, Any]) -> float:
    return float(entry.get("actual_revenue") or entry.get("revenue") or 0)


def _money(value: float | int) -> str:
    return f"¥{float(value):,.2f}"


def _minor_money(value: int | None) -> str:
    return "待核算" if value is None else f"¥{value / 100:,.2f}"


def _is_total_question(text: str) -> bool:
    return any(term in text for term in ("总营业收入", "总营收", "累计营收")) or (
        "总订单" in text and "客单价" in text
    )


def _is_date_coverage_question(text: str) -> bool:
    has_day_scope = any(term in text for term in ("哪些天", "哪几天", "多少天", "日期", "空缺"))
    has_gap = any(term in text for term in ("没录", "未录", "没有录入", "漏录", "不完整", "缺失"))
    return has_day_scope and has_gap


def _is_profit_question(text: str) -> bool:
    return any(term in text for term in ("净利润", "实际利润", "赚钱吗", "赚了多少", "盈利"))


def _is_platform_question(text: str) -> bool:
    names = sum(term in text for term in ("美团", "淘宝闪购", "京东", "抖音"))
    return names >= 2 or (names >= 1 and any(term in text for term in ("分别", "客如云", "重复")))


def _is_cash_question(text: str) -> bool:
    return "现金" in text and any(term in text for term in ("多少", "备用金", "存银行", "实点"))


def _is_completeness_question(text: str) -> bool:
    return any(term in text for term in (
        "账是否已经完整", "账完整", "账算完整", "账算完了", "账算清楚",
        "正式出利润表", "现金流量表", "是否完成",
    ))


def _missing_cost_labels(fields: list[str]) -> str:
    labels = {
        "food_cost": "食材成本",
        "packaging_cost": "包装耗材",
        "labor": "实际人工",
        "rent_allocated": "房租日摊销",
        "utility": "水电",
        "cash_count": "打烊现金实点",
        "labor": "实际人工",
        "rent": "房租日摊销",
        "other_cost": "其他费用",
    }
    return "、".join(labels.get(field, field) for field in fields) or "成本确认"


def _extract_dates(message: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_month_day = {
        tuple(map(int, item["date"].split("-")[1:])): item
        for item in entries
        if item.get("date")
    }
    found = []
    for month, day in re.findall(r"(\d{1,2})月(\d{1,2})日", message):
        entry = by_month_day.get((int(month), int(day)))
        if entry and entry not in found:
            found.append(entry)
    return found


def _filter_date_range(message: str, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dates = re.findall(r"(\d{1,2})月(\d{1,2})日", message)
    if len(dates) < 2:
        return entries
    start = f"2026-{int(dates[0][0]):02d}-{int(dates[0][1]):02d}"
    end = f"2026-{int(dates[1][0]):02d}-{int(dates[1][1]):02d}"
    selected = [item for item in entries if start <= str(item.get("date", "")) <= end]
    return selected or entries


def _is_follow_up(text: str) -> bool:
    return any(term in text for term in ("那", "这个", "刚才", "上面", "这些", "它", "怎么算", "为什么"))
