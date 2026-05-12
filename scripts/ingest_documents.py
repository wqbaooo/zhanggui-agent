#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 PDF/文档资料整理成 Agent 可检索的知识片段。"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from pypdf import PdfReader


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PDF = PROJECT_ROOT / "资料" / "餐饮" / "餐饮选址实用指南87M整合版本.pdf"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "knowledge_base" / "document_knowledge"


def clean_text(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(text: str, size: int = 1200, overlap: int = 180) -> List[str]:
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end].strip())
        if end == len(text):
            break
        start = max(end - overlap, start + 1)
    return [chunk for chunk in chunks if chunk]


def ingest_pdf(pdf_path: Path, output_dir: Path) -> Dict:
    reader = PdfReader(str(pdf_path))
    output_dir.mkdir(parents=True, exist_ok=True)

    chunks = []
    empty_pages = 0
    for page_index, page in enumerate(reader.pages, 1):
        text = clean_text(page.extract_text() or "")
        if not text:
            empty_pages += 1
            continue
        for chunk_index, chunk in enumerate(chunk_text(text), 1):
            chunks.append(
                {
                    "title": f"{pdf_path.stem} P{page_index}-{chunk_index}",
                    "page": page_index,
                    "chunk": chunk_index,
                    "text": chunk,
                    "status": "usable",
                }
            )

    status = "usable" if chunks else "needs_ocr"
    payload = {
        "source": str(pdf_path),
        "ingested_at": datetime.now().isoformat(),
        "status": status,
        "pages": len(reader.pages),
        "empty_pages": empty_pages,
        "chunks": chunks,
        "notes": [],
    }
    if status == "needs_ocr":
        payload["notes"].append("pypdf 未抽取到文本，PDF 很可能是扫描图片版，需要先 OCR 后才能真正进入 Agent 知识库。")
        payload["chunks"].append(
            {
                "title": pdf_path.stem,
                "page": None,
                "chunk": 1,
                "text": "该 PDF 已登记，但当前未抽取到可检索正文。请先执行 OCR，再重新入库。",
                "status": "needs_ocr",
            }
        )

    output_file = output_dir / f"{pdf_path.stem}.json"
    output_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"output_file": str(output_file), **payload}


def ocr_pdf_with_system_tools(
    pdf_path: Path,
    output_dir: Path,
    lang: str = "chi_sim+eng",
    max_pages: int | None = None,
    start_page: int = 1,
    end_page: int | None = None,
    append: bool = False,
) -> Dict:
    """用 pdftoppm + tesseract 做 OCR。

    这是可选路径：本机装了 poppler/tesseract 才能跑。没装时返回 blocked，
    避免系统假装已经读完扫描 PDF。
    """
    pdftoppm = shutil.which("pdftoppm")
    tesseract = shutil.which("tesseract")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{pdf_path.stem}.ocr.json"

    if not pdftoppm or not tesseract:
        payload = {
            "source": str(pdf_path),
            "ingested_at": datetime.now().isoformat(),
            "status": "ocr_blocked",
            "pages": None,
            "empty_pages": None,
            "chunks": [
                {
                    "title": pdf_path.stem,
                    "page": None,
                    "chunk": 1,
                    "text": "OCR 未执行：本机缺少 pdftoppm 或 tesseract。macOS 可用 brew install poppler tesseract tesseract-lang。",
                    "status": "ocr_blocked",
                }
            ],
            "notes": ["缺少 OCR 系统依赖，扫描 PDF 仍未真正进入知识库。"],
        }
        output_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"output_file": str(output_file), **payload}

    reader = PdfReader(str(pdf_path))
    page_count = len(reader.pages)
    start_page = max(1, start_page)
    last_page = min(end_page or page_count, page_count)
    if max_pages is not None:
        last_page = min(last_page, start_page + max_pages - 1)
    chunks = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        for page_num in range(start_page, last_page + 1):
            image_prefix = tmp_path / f"page_{page_num}"
            subprocess.run(
                [
                    pdftoppm,
                    "-f",
                    str(page_num),
                    "-l",
                    str(page_num),
                    "-r",
                    "200",
                    "-png",
                    str(pdf_path),
                    str(image_prefix),
                ],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            images = sorted(tmp_path.glob(f"page_{page_num}-*.png"))
            if not images:
                continue
            result = subprocess.run(
                [tesseract, str(images[0]), "stdout", "-l", lang, "--psm", "6"],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            text = clean_text(result.stdout)
            for chunk_index, chunk in enumerate(chunk_text(text), 1):
                chunks.append(
                    {
                        "title": f"{pdf_path.stem} OCR P{page_num}-{chunk_index}",
                        "page": page_num,
                        "chunk": chunk_index,
                        "text": chunk,
                        "status": "usable",
                    }
                )

    if append and output_file.exists():
        try:
            existing = json.loads(output_file.read_text(encoding="utf-8"))
            old_chunks = existing.get("chunks", [])
        except Exception:
            old_chunks = []
    else:
        old_chunks = []

    merged_chunks = old_chunks + chunks
    seen = set()
    deduped_chunks = []
    for chunk in merged_chunks:
        key = (chunk.get("page"), chunk.get("chunk"), chunk.get("text", "")[:80])
        if key in seen:
            continue
        seen.add(key)
        deduped_chunks.append(chunk)

    payload = {
        "source": str(pdf_path),
        "ingested_at": datetime.now().isoformat(),
        "status": "usable" if deduped_chunks else "ocr_empty",
        "pages": page_count,
        "ocr_page_ranges": [{"start": start_page, "end": last_page}],
        "chunks": deduped_chunks,
        "notes": [] if deduped_chunks else ["OCR 已执行但未识别到可用正文。"],
    }
    output_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"output_file": str(output_file), **payload}


def main():
    parser = argparse.ArgumentParser(description="导入 PDF 文档到 Agent 知识库")
    parser.add_argument("--pdf", default=str(DEFAULT_PDF), help="PDF 文件路径")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="输出目录")
    parser.add_argument("--ocr", action="store_true", help="对扫描 PDF 执行 OCR")
    parser.add_argument("--ocr-lang", default="chi_sim+eng", help="tesseract OCR 语言")
    parser.add_argument("--max-pages", type=int, default=None, help="OCR 页数上限，调试时可先限制")
    parser.add_argument("--start-page", type=int, default=1, help="OCR 起始页")
    parser.add_argument("--end-page", type=int, default=None, help="OCR 结束页")
    parser.add_argument("--append", action="store_true", help="追加到已有 OCR 结果中")
    args = parser.parse_args()

    if args.ocr:
        result = ocr_pdf_with_system_tools(
            Path(args.pdf),
            Path(args.output_dir),
            args.ocr_lang,
            args.max_pages,
            args.start_page,
            args.end_page,
            args.append,
        )
    else:
        result = ingest_pdf(Path(args.pdf), Path(args.output_dir))
    print(json.dumps({
        "source": result["source"],
        "output_file": result["output_file"],
        "status": result["status"],
        "pages": result["pages"],
        "chunks": len(result["chunks"]),
        "notes": result["notes"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
