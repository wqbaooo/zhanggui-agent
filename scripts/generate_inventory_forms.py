#!/usr/bin/env python3
"""Generate printable employee inventory forms from the live SKU catalog."""

from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parent.parent
PROJECT_ID = "xinyu-hengtai-dakou"
SKU_FILE = ROOT / "project_data" / PROJECT_ID / "skus.json"
OUTPUT_DIR = ROOT / "output" / "pdf"
FONT_PATH = Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf")
FONT_NAME = "InventoryChinese"
ORANGE = colors.HexColor("#F97316")
INK = colors.HexColor("#1C1917")
MUTED = colors.HexColor("#78716C")
LINE = colors.HexColor("#A8A29E")
SOFT = colors.HexColor("#FFF7ED")

DAILY_USAGE_GROUPS = [
    ("基础粉料", ["章鱼预拌粉", "调料包"], "#E7F3EF"),
    ("酱料", ["原味酱", "香甜酱", "藤椒酱", "蛋黄酱", "番茄酱", "芥末酱", "奶酪酱"], "#FBF1DC"),
    ("撒料", ["木鱼花", "切丝海苔", "青海苔粉", "海苔肉松"], "#EDF3DF"),
    ("冷链配料", ["章鱼粒", "章鱼花", "玉米粒", "培根丁", "肉肠", "麻辣鲜蛤", "咸蛋黄", "芝士", "蟹柳"], "#E7F1F7"),
    ("餐盒与袋装", ["章鱼烧盒子（4粒）", "章鱼烧盒子（6粒）", "全家福打包盒", "全家福打包盒塑料盖", "外卖塑料袋", "外卖无纺布袋"], "#FAEEE3"),
    ("出餐辅助耗材", ["纸巾", "竹签", "烤肠竹签"], "#F0EFEC"),
    ("标签与收银耗材", ["外卖贴纸", "标签纸", "收银纸80*80", "收银纸57*50"], "#EDF0F2"),
]
DAILY_USAGE_ORDER = [name for _, names, _ in DAILY_USAGE_GROUPS for name in names]


def register_font() -> None:
    pdfmetrics.registerFont(TTFont(FONT_NAME, str(FONT_PATH)))


def load_skus() -> list[dict]:
    payload = json.loads(SKU_FILE.read_text(encoding="utf-8"))
    return [sku for sku in payload.get("skus", []) if sku.get("active", True)]


def name_of(sku: dict) -> str:
    return str(sku.get("hq_name") or sku.get("name") or "未命名")


def unit_of(sku: dict) -> str:
    return str(sku.get("display_unit") or sku.get("standard_unit") or sku.get("unit") or "单位")


def p(text: str, size: float = 8, bold: bool = False, align: int = TA_LEFT) -> Paragraph:
    return Paragraph(
        text,
        ParagraphStyle(
            name=f"p-{size}-{bold}-{align}",
            fontName=FONT_NAME,
            fontSize=size,
            leading=size + 2,
            textColor=INK,
            alignment=align,
        ),
    )


def base_table_style(header_rows: int = 1) -> TableStyle:
    return TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), FONT_NAME),
        ("TEXTCOLOR", (0, 0), (-1, -1), INK),
        ("GRID", (0, 0), (-1, -1), 0.55, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (-1, header_rows - 1), "CENTER"),
        ("BACKGROUND", (0, 0), (-1, header_rows - 1), SOFT),
        ("TEXTCOLOR", (0, 0), (-1, header_rows - 1), INK),
        ("BOTTOMPADDING", (0, 0), (-1, header_rows - 1), 5),
        ("TOPPADDING", (0, 0), (-1, header_rows - 1), 5),
    ])


def build_daily_usage_form(skus: list[dict]) -> Path:
    # 保持已发布文件路径兼容，但文件内容使用当前的一日一张 A4 纵向模板。
    output = OUTPUT_DIR / "大口章鱼烧_每日核心物料领用表.pdf"
    order = {name: index for index, name in enumerate(DAILY_USAGE_ORDER)}
    daily = sorted(
        [sku for sku in skus if sku.get("tracking_mode") == "daily_usage" and sku.get("asset_class") != "equipment"],
        key=lambda sku: order.get(name_of(sku), 999),
    )
    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=8 * mm,
        rightMargin=8 * mm,
        topMargin=7 * mm,
        bottomMargin=7 * mm,
    )
    story = [
        p("大口章鱼烧 · 每日物料使用登记表", 17, True, TA_CENTER),
        Spacer(1, 1.5 * mm),
        p("营业日期：____年__月__日　只记当天实际开封/领用整数；未使用留空；低频耗材在阶段盘点表管理。", 7.5, align=TA_CENTER),
        Spacer(1, 2 * mm),
    ]
    widths = [42 * mm, 57 * mm, 18 * mm, 26 * mm, 51 * mm]
    rows = [[p("品名", 7.5, True, TA_CENTER), p("规格", 7.5, True, TA_CENTER), p("单位", 7.5, True, TA_CENTER), p("今日使用", 7.5, True, TA_CENTER), p("异常/备注", 7.5, True, TA_CENTER)]]
    row_heights = [6 * mm]
    group_rows = []
    data_rows = []
    for group_index, (label, names, fill) in enumerate(DAILY_USAGE_GROUPS):
        items = [sku for sku in daily if sku.get("daily_usage_group") == label or name_of(sku) in names]
        group_row = len(rows)
        group_rows.append((group_row, fill))
        rows.append([p(f"{group_index + 1:02d}　{label} · {len(items)}项", 8, True), "", "", "", ""])
        row_heights.append(5.2 * mm)
        for sku in items:
            data_rows.append(len(rows))
            rows.append([p(name_of(sku), 7), p(str(sku.get("spec") or "待补"), 7), p(unit_of(sku), 7, align=TA_CENTER), "", ""])
            row_heights.append(5.05 * mm)
    table = Table(rows, colWidths=widths, rowHeights=row_heights)
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E6EEEB")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#21352F")),
        ("FONTNAME", (0, 0), (-1, -1), FONT_NAME), ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C5C0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 2), ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]
    for row_index, fill in group_rows:
        commands.extend([("SPAN", (0, row_index), (-1, row_index)), ("BACKGROUND", (0, row_index), (-1, row_index), colors.HexColor(fill)), ("TEXTCOLOR", (0, row_index), (-1, row_index), colors.HexColor("#2B413A"))])
    for row_index in data_rows:
        commands.append(("BACKGROUND", (3, row_index), (3, row_index), colors.HexColor("#FFF6D8")))
    table.setStyle(TableStyle(commands))
    story.append(table)
    story.extend([Spacer(1, 1.5 * mm), p("录入线上库存时按同一营业日期照纸面整数录入；重复保存覆盖当天旧版，不会重复扣库。", 7, align=TA_CENTER)])
    doc.build(story)
    return output


def build_blind_count_form(skus: list[dict]) -> Path:
    output = OUTPUT_DIR / "大口章鱼烧_周期库存盲盘表.pdf"
    materials = [sku for sku in skus if sku.get("asset_class") != "equipment" and sku.get("tracking_mode") != "asset_registry"]
    doc = SimpleDocTemplate(
        str(output),
        pagesize=A4,
        leftMargin=9 * mm,
        rightMargin=9 * mm,
        topMargin=9 * mm,
        bottomMargin=9 * mm,
    )
    story = [
        p("大口章鱼烧 · 周期库存盲盘表", 17, True, TA_CENTER),
        Spacer(1, 3 * mm),
        Table(
            [
                [p("门店：新余恒太城五楼", 8), p("盘点日期：____月____日", 8), p("位置：□门店 □仓库", 8)],
                [p("开始时间：____:____", 8), p("结束时间：____:____", 8), p("盘点人：______ 复核人：______", 8)],
            ],
            colWidths=[64 * mm, 58 * mm, 70 * mm],
            style=TableStyle([("FONTNAME", (0, 0), (-1, -1), FONT_NAME), ("BOX", (0, 0), (-1, -1), 0.6, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]),
        ),
        Spacer(1, 3 * mm),
    ]
    rows = [[
        p("分类", 7.5, True, TA_CENTER),
        p("物料", 7.5, True, TA_CENTER),
        p("采购规格", 7.5, True, TA_CENTER),
        p("核算单位", 7.5, True, TA_CENTER),
        p("实盘结余", 7.5, True, TA_CENTER),
        p("临期 / 破损 / 异常", 7.5, True, TA_CENTER),
    ]]
    for sku in materials:
        rows.append([
            p(str(sku.get("category") or "其他"), 7),
            p(name_of(sku), 7.5, True),
            p(str(sku.get("spec") or "待补"), 7),
            p(unit_of(sku), 7, align=TA_CENTER),
            "",
            "",
        ])
    widths = [20 * mm, 35 * mm, 48 * mm, 20 * mm, 24 * mm, 45 * mm]
    table = Table(rows, colWidths=widths, rowHeights=[10 * mm] + [9.2 * mm] * len(materials), repeatRows=1)
    style = base_table_style()
    style.add("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAF9")])
    table.setStyle(style)
    story.extend([
        table,
        Spacer(1, 3 * mm),
        p("盲盘规则：表中不展示系统账面数量。员工填写实盘结余，负责人复核后录入“周期盘点”；未盘到的物料必须说明原因，不能默认为 0。", 7.5),
    ])
    doc.build(story)
    return output


def main() -> None:
    register_font()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    skus = load_skus()
    for output in (build_daily_usage_form(skus), build_blind_count_form(skus)):
        print(output)


if __name__ == "__main__":
    main()
