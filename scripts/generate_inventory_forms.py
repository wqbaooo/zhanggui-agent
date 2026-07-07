#!/usr/bin/env python3
"""Generate printable employee inventory forms from the live SKU catalog."""

from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


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
    output = OUTPUT_DIR / "大口章鱼烧_每日核心物料领用表.pdf"
    keywords = ["章鱼烧粉", "预拌粉", "调料包", "原味酱", "沙拉酱", "香甜酱", "章鱼粒", "章鱼花", "木鱼花", "肉松"]
    core = [sku for sku in skus if any(key in name_of(sku) for key in keywords)][:9]
    doc = SimpleDocTemplate(
        str(output),
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=9 * mm,
        bottomMargin=9 * mm,
    )
    story = []
    widths = [12 * mm] + [22 * mm] * len(core) + [45 * mm, 20 * mm]
    periods = [(1, 16, "上半月"), (17, 31, "下半月")]
    for page_index, (start_day, end_day, label) in enumerate(periods):
        if page_index:
            story.append(PageBreak())
        story.extend([
            p(f"大口章鱼烧 · 每日核心物料领用表（{label}）", 17, True, TA_CENTER),
            Spacer(1, 3 * mm),
            Table(
                [[p("门店：新余恒太城五楼", 8), p("月份：_______年____月", 8), p("负责人：________", 8), p("复核人：________", 8)]],
                colWidths=[70 * mm, 70 * mm, 60 * mm, 60 * mm],
                style=TableStyle([("FONTNAME", (0, 0), (-1, -1), FONT_NAME), ("BOX", (0, 0), (-1, -1), 0.6, LINE), ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]),
            ),
            Spacer(1, 3 * mm),
        ])
        header = [p("日期", 7.5, True, TA_CENTER)]
        header.extend(p(f"{name_of(sku)}<br/><font color='#78716C'>单位：{unit_of(sku)}</font>", 7, True, TA_CENTER) for sku in core)
        header.extend([p("异常 / 报废 / 临时补货", 7.5, True, TA_CENTER), p("记录人", 7.5, True, TA_CENTER)])
        rows = [header]
        for day in range(start_day, end_day + 1):
            rows.append([p(f"{day}日", 7.5, align=TA_CENTER), *([""] * len(core)), "", ""])
        table = Table(rows, colWidths=widths, rowHeights=[12 * mm] + [9 * mm] * (end_day - start_day + 1), repeatRows=1)
        style = base_table_style()
        style.add("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#FAFAF9")])
        table.setStyle(style)
        story.extend([
            table,
            Spacer(1, 2.5 * mm),
            p("填写规则：只记录当天新开包或新领用数量；盘点结余不要写在本表。异常、报废和临时补货必须写原因。", 7.5),
        ])
    doc.build(story)
    return output


def build_blind_count_form(skus: list[dict]) -> Path:
    output = OUTPUT_DIR / "大口章鱼烧_周期库存盲盘表.pdf"
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
    for sku in skus:
        rows.append([
            p(str(sku.get("category") or "其他"), 7),
            p(name_of(sku), 7.5, True),
            p(str(sku.get("spec") or "待补"), 7),
            p(unit_of(sku), 7, align=TA_CENTER),
            "",
            "",
        ])
    widths = [20 * mm, 35 * mm, 48 * mm, 20 * mm, 24 * mm, 45 * mm]
    table = Table(rows, colWidths=widths, rowHeights=[10 * mm] + [9.2 * mm] * len(skus), repeatRows=1)
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
