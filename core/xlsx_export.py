"""Dependency-free, professional XLSX writer for finance report downloads."""

from __future__ import annotations

import io
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from html import escape
from typing import Any


@dataclass(frozen=True)
class Formula:
    expression: str
    cached_value: int | float | str | None = None


@dataclass
class FinanceSheet:
    name: str
    title: str
    subtitle: str
    headers: list[str]
    rows: list[list[Any]]
    widths: list[int] | None = None
    currency_columns: set[int] = field(default_factory=set)
    integer_columns: set[int] = field(default_factory=set)
    date_columns: set[int] = field(default_factory=set)
    input_columns: set[int] = field(default_factory=set)
    total_rows: set[int] = field(default_factory=set)
    validations: list[tuple[int, str]] = field(default_factory=list)
    negative_warning_column: int | None = None


def _column_name(index: int) -> str:
    result = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        result = chr(65 + remainder) + result
    return result


def _cell(ref: str, value: Any, style: int = 0) -> str:
    if isinstance(value, Formula):
        formula = escape(value.expression.removeprefix("="))
        cached_value = value.cached_value
        if isinstance(cached_value, float) and style in {7, 9}:
            cached_value = round(cached_value, 2)
        cached = "" if cached_value is None else f"<v>{escape(str(cached_value))}</v>"
        return f'<c r="{ref}" s="{style}"><f>{formula}</f>{cached}</c>'
    if value is None:
        return f'<c r="{ref}" s="{style}"/>'
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{ref}" s="{style}"><v>{value}</v></c>'
    text = escape(str(value))
    return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t>{text}</t></is></c>'


def _sheet_xml(sheet: FinanceSheet) -> str:
    column_count = max(len(sheet.headers), max((len(row) for row in sheet.rows), default=1))
    last_column = _column_name(column_count)
    widths = sheet.widths or [18] * column_count
    if len(widths) < column_count:
        widths = [*widths, *([18] * (column_count - len(widths)))]
    cols = "".join(
        f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>'
        for index, width in enumerate(widths[:column_count], start=1)
    )
    rendered_rows = [
        f'<row r="1" ht="34" customHeight="1">{_cell("A1", sheet.title, 1)}</row>',
        '<row r="2" ht="8" customHeight="1"/>',
        f'<row r="3" ht="28" customHeight="1">{_cell("A3", sheet.subtitle, 2)}</row>',
        '<row r="4" ht="8" customHeight="1"/>',
        f'<row r="5" ht="28" customHeight="1">{"".join(_cell(f"{_column_name(index)}5", value, 3) for index, value in enumerate(sheet.headers, start=1))}</row>',
    ]
    for data_index, row in enumerate(sheet.rows, start=1):
        row_index = data_index + 5
        cells = []
        for column_index, value in enumerate(row, start=1):
            if data_index in sheet.total_rows:
                style = 9
            elif isinstance(value, Formula):
                style = 7 if column_index in sheet.currency_columns else 13
            elif column_index in sheet.input_columns:
                style = 8
            elif column_index in sheet.currency_columns:
                style = 4
            elif column_index in sheet.integer_columns:
                style = 5
            elif column_index in sheet.date_columns:
                style = 6
            elif data_index % 2 == 0:
                style = 12
            else:
                style = 0
            cells.append(_cell(f"{_column_name(column_index)}{row_index}", value, style))
        longest_text = max((len(str(value)) for value in row if value is not None), default=0)
        height = 40 if longest_text > 48 else 24
        rendered_rows.append(f'<row r="{row_index}" ht="{height}" customHeight="1">{"".join(cells)}</row>')
    last_row = max(5 + len(sheet.rows), 5)
    validations = ""
    if sheet.validations and sheet.rows:
        items = []
        for column, values in sheet.validations:
            letter = _column_name(column)
            formula = escape(f'"{values}"')
            items.append(
                f'<dataValidation type="list" allowBlank="1" showErrorMessage="1" '
                f'errorTitle="请选择有效值" error="请从下拉列表中选择" sqref="{letter}6:{letter}{last_row}">'
                f"<formula1>{formula}</formula1></dataValidation>"
            )
        validations = f'<dataValidations count="{len(items)}">{"".join(items)}</dataValidations>'
    conditional = ""
    if sheet.negative_warning_column is not None and sheet.rows:
        letter = _column_name(sheet.negative_warning_column)
        conditional = (
            f'<conditionalFormatting sqref="{letter}6:{letter}{last_row}">'
            f'<cfRule type="cellIs" dxfId="0" priority="1" operator="lessThan"><formula>0</formula></cfRule>'
            f"</conditionalFormatting>"
        )
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <sheetViews><sheetView showGridLines="0" workbookViewId="0"><pane ySplit="5" topLeftCell="A6" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>
  <sheetFormatPr defaultRowHeight="21"/><cols>{cols}</cols>
  <sheetData>{''.join(rendered_rows)}</sheetData>
  <mergeCells count="2"><mergeCell ref="A1:{last_column}1"/><mergeCell ref="A3:{last_column}3"/></mergeCells>
  <autoFilter ref="A5:{last_column}{last_row}"/>{conditional}{validations}
  <pageMargins left="0.3" right="0.3" top="0.5" bottom="0.5" header="0.2" footer="0.2"/>
</worksheet>'''


def _coerce_sheet(item: FinanceSheet | tuple[str, list[list[Any]], list[int] | None]) -> FinanceSheet:
    if isinstance(item, FinanceSheet):
        return item
    name, rows, widths = item
    headers, data = (rows[0], rows[1:]) if rows else ([], [])
    return FinanceSheet(
        name=name,
        title=name,
        subtitle="掌柜Agent 动态导出",
        headers=[str(value) for value in headers],
        rows=data,
        widths=widths,
    )


def build_finance_workbook(
    sheets: list[FinanceSheet | tuple[str, list[list[Any]], list[int] | None]],
) -> bytes:
    normalized = [_coerce_sheet(item) for item in sheets]
    output = io.BytesIO()
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    sheet_entries = "".join(
        f'<sheet name="{escape(sheet.name)}" sheetId="{index}" r:id="rId{index}"/>'
        for index, sheet in enumerate(normalized, start=1)
    )
    workbook_rels = "".join(
        f'<Relationship Id="rId{index}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, len(normalized) + 1)
    ) + f'<Relationship Id="rId{len(normalized)+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
    overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{index}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for index in range(1, len(normalized) + 1)
    )
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", f'''<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>{overrides}
<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>
</Types>''')
        archive.writestr("_rels/.rels", '''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>
</Relationships>''')
        archive.writestr("docProps/core.xml", f'''<?xml version="1.0" encoding="UTF-8"?>
<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/">
<dc:title>大口章鱼烧专业财务经营工作簿</dc:title><dc:creator>掌柜Agent</dc:creator><dc:description>经营资金链、记账、对账、凭证与利润完整性</dc:description><dcterms:created>{timestamp}</dcterms:created>
</cp:coreProperties>''')
        archive.writestr("xl/workbook.xml", f'''<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><calcPr calcId="191029" fullCalcOnLoad="1" forceFullCalc="1"/><sheets>{sheet_entries}</sheets></workbook>''')
        archive.writestr("xl/_rels/workbook.xml.rels", f'''<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{workbook_rels}</Relationships>''')
        archive.writestr("xl/styles.xml", _styles_xml())
        for index, sheet in enumerate(normalized, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(sheet))
    return output.getvalue()


def _styles_xml() -> str:
    return '''<?xml version="1.0" encoding="UTF-8"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<numFmts count="2"><numFmt numFmtId="164" formatCode="¥#,##0.00;[Red]-¥#,##0.00;¥0.00"/><numFmt numFmtId="165" formatCode="yyyy-mm-dd"/></numFmts>
<fonts count="5">
<font><sz val="11"/><name val="PingFang SC"/></font>
<font><b/><color rgb="FFFFFFFF"/><sz val="18"/><name val="PingFang SC"/></font>
<font><b/><color rgb="FF173B57"/><sz val="11"/><name val="PingFang SC"/></font>
<font><b/><color rgb="FFFFFFFF"/><sz val="11"/><name val="PingFang SC"/></font>
<font><b/><color rgb="FF173B57"/><sz val="11"/><name val="PingFang SC"/></font>
</fonts>
<fills count="9">
<fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FF173B57"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFFFF4E8"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFEA4F11"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFEAF3F8"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFEAF7EE"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFFFF2CC"/><bgColor indexed="64"/></patternFill></fill>
<fill><patternFill patternType="solid"><fgColor rgb="FFF7F9FA"/><bgColor indexed="64"/></patternFill></fill>
</fills>
<borders count="3"><border/><border><bottom style="thin"><color rgb="FFD8E0E5"/></bottom></border><border><left style="thin"><color rgb="FFD8E0E5"/></left><right style="thin"><color rgb="FFD8E0E5"/></right><top style="thin"><color rgb="FFD8E0E5"/></top><bottom style="thin"><color rgb="FFD8E0E5"/></bottom></border></borders>
<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>
<cellXfs count="14">
<xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyAlignment="1"><alignment wrapText="1" vertical="center"/></xf>
<xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment vertical="center"/></xf>
<xf numFmtId="0" fontId="2" fillId="3" borderId="0" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment wrapText="1" vertical="center"/></xf>
<xf numFmtId="0" fontId="3" fillId="4" borderId="2" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment wrapText="1" vertical="center"/></xf>
<xf numFmtId="164" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment vertical="center"/></xf>
<xf numFmtId="3" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment vertical="center"/></xf>
<xf numFmtId="165" fontId="0" fillId="0" borderId="1" xfId="0" applyNumberFormat="1" applyAlignment="1"><alignment vertical="center"/></xf>
<xf numFmtId="164" fontId="4" fillId="6" borderId="2" xfId="0" applyFont="1" applyFill="1" applyNumberFormat="1" applyAlignment="1"><alignment vertical="center"/></xf>
<xf numFmtId="0" fontId="0" fillId="5" borderId="2" xfId="0" applyFill="1" applyAlignment="1"><alignment wrapText="1" vertical="center"/></xf>
<xf numFmtId="164" fontId="3" fillId="2" borderId="2" xfId="0" applyFont="1" applyFill="1" applyNumberFormat="1" applyAlignment="1"><alignment vertical="center"/></xf>
<xf numFmtId="0" fontId="4" fillId="7" borderId="2" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment wrapText="1" vertical="center"/></xf>
<xf numFmtId="0" fontId="4" fillId="3" borderId="2" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment wrapText="1" vertical="center"/></xf>
<xf numFmtId="0" fontId="0" fillId="8" borderId="1" xfId="0" applyFill="1" applyAlignment="1"><alignment wrapText="1" vertical="center"/></xf>
<xf numFmtId="0" fontId="4" fillId="6" borderId="2" xfId="0" applyFont="1" applyFill="1" applyAlignment="1"><alignment wrapText="1" vertical="center"/></xf>
</cellXfs>
<dxfs count="1"><dxf><fill><patternFill patternType="solid"><fgColor rgb="FFFFC7CE"/><bgColor indexed="64"/></patternFill></fill><font><color rgb="FF9C0006"/></font></dxf></dxfs>
</styleSheet>'''
