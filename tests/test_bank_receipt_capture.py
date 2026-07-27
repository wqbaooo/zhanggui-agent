from server.routes.capture import _detect_source_type, _parse_fields_from_text


ICBC_RECEIPT_OCR = """
ICBC 中国工商银行 境内汇款电子回单
收款户名 王启宝
收款卡号 6214****6936
收款银行 招商银行
收款金额 2,918.76 元(人民币)
付款卡号 6215****9863
付款银行 中国工商银行
回单编号 ZZHK-0010-7208-9438-0138
交易时间 2026/07/20 23:24
附言 7.14-7.20
"""


def test_icbc_receipt_is_a_money_movement_not_daily_revenue():
    assert _detect_source_type(ICBC_RECEIPT_OCR) == "银行转账凭证"
    fields = {item["key"]: item["value"] for item in _parse_fields_from_text(ICBC_RECEIPT_OCR)}

    assert fields["date"] == "2026-07-20"
    assert fields["amount"] == 2918.76
    assert fields["transaction_reference"] == "ZZHK-0010-7208-9438-0138"
    assert fields["counterparty"] == "王启宝"
    assert fields["transaction_direction"] == "inflow"
    assert "revenue" not in fields


def test_bank_amount_survives_when_ocr_garbles_the_amount_label():
    fields = {item["key"]: item["value"] for item in _parse_fields_from_text("""
    中国工商银行 境内汇款电子回单
    收款户名\n王启宝
    WER Se Hl 2,918.76 元(人民币)
    回单编号 ZZHK-0010-7208-9438-0138
    交易时间 2026/07/20 23:24
    """)}

    assert fields["amount"] == 2918.76
    assert fields["counterparty"] == "王启宝"
