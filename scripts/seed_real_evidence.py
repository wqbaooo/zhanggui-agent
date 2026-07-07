#!/usr/bin/env python3
"""将 2026-06-29 的真实门店图片作为可追溯证据录入资料箱。"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

PROJECT_ID = "xinyu-hengtai-dakou"
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from models.document_box import DocumentBox, StoreDocument


ATTACHMENT_DIR = Path(
    "/Users/wqboo/.codex/attachments/99dfc58f-a37a-4a71-9ece-ed81b0097ed2"
)
PUBLIC_DIR = ROOT / "web" / "public" / "store-evidence" / "2026-06-29"


EVIDENCE = [
    {
        "filename": "image-1.jpg",
        "title": "总部供应链商品目录（食材与新品）",
        "doc_type": "总部通知",
        "source": "大口餐饮供应链",
        "tags": ["真实资料案例", "总部供应链", "SKU目录"],
        "summary": "总部小程序商品目录，覆盖食材、酱料、冷冻品与基础原料；未登录状态不显示价格。",
        "facts": [
            "可识别章鱼预拌粉、调料包、原味酱、芥末酱、藤椒酱、海苔、木鱼花、鸡蛋等 SKU",
            "商品同时存在箱、包、桶、袋等采购单位，入库前需要做单位换算",
            "目录含促销与新品标记，不能直接等同于门店实际采购价",
        ],
        "risks": ["目录价格不可见，采购预算必须用销售单或登录后的实价复核"],
        "targets": ["总部SKU目录", "采购候选", "单位换算", "成本基线"],
        "actions": ["建立总部 SKU 与门店 SKU 别名", "提示补录可见采购价", "比较总部供货与本地采购成本"],
        "chain": "catalog",
    },
    {
        "filename": "image-2.jpg",
        "title": "总部供应链商品目录（冷冻品与包装耗材）",
        "doc_type": "总部通知",
        "source": "大口餐饮供应链",
        "tags": ["真实资料案例", "总部供应链", "包装耗材"],
        "summary": "总部小程序目录的冷冻品与包装耗材区，可用于补齐原料和耗材主数据。",
        "facts": [
            "可识别章鱼花、章鱼粒、培根丁、蛤蜊、蟹柳、小龙虾及多种包装耗材",
            "包装含 4 粒盒、全家福盒、塑料袋、封口袋、小票纸、标签纸和手套",
            "同类包装存在不同箱规，补货建议必须绑定具体规格",
        ],
        "risks": ["部分商品无图片或名称相近，自动匹配后仍需人工确认规格"],
        "targets": ["总部SKU目录", "包装耗材", "安全库存", "采购候选"],
        "actions": ["补齐包装耗材安全库存", "建立箱规到单个的换算", "标记无图或低置信商品"],
        "chain": "catalog",
    },
    {
        "filename": "image-3.jpg",
        "title": "总部供应链销售订单 2026-06-21",
        "doc_type": "供应商协议",
        "source": "大口餐饮供应链销售订单",
        "tags": ["真实资料案例", "进货单", "采购入库"],
        "summary": "总部采购销售订单，合计 16,108 元；可见预拌粉、调料包、包装盒、章鱼粒、章鱼花、原味酱和纸巾等。",
        "facts": [
            "单据日期：2026-06-21",
            "单据编号：XSDD-20260624-00001",
            "可见合计金额：16,108.00 元",
            "章鱼预拌粉 12 箱，调料包 2 箱，全家福打包盒塑料盖 1 箱",
        ],
        "risks": ["纸张褶皱且部分行模糊，数量、单价和箱规必须逐行复核后再入库存"],
        "targets": ["采购记录", "库存入库", "应付成本", "现金流"],
        "actions": ["逐行匹配总部 SKU", "复核 16,108 元与付款凭证", "生成到货验收任务"],
        "chain": "purchase",
    },
    {
        "filename": "image-4.jpg",
        "title": "POS 销售小票：原味章鱼烧（标准）",
        "doc_type": "其他",
        "source": "王府井购物中心负一楼店 POS",
        "tags": ["真实资料案例", "POS销售小票", "抖音团购"],
        "summary": "一份原味章鱼烧标准份销售记录，应付与实付 16 元，使用抖音团购券。",
        "facts": [
            "交易时间：2026-06-27 19:20",
            "取餐号：T10192",
            "商品：原味章鱼烧（标准），数量 1，实付 16.00 元",
            "票面展示团购价 22.80 元与支付优惠 9.00 元，需与渠道结算口径对账",
        ],
        "risks": ["票面原价、券价、实付和商家到账可能不是同一口径，不能只按实付判断渠道利润"],
        "targets": ["商品销量", "渠道核销", "营业日报", "POS对账"],
        "actions": ["与出餐标签按取餐号关联", "补录平台实际到账", "计算该笔订单渠道贡献毛利"],
        "chain": "sale",
    },
    {
        "filename": "image-5.jpg",
        "title": "出餐标签：小龙虾鸡蛋汉堡",
        "doc_type": "其他",
        "source": "王府井购物中心负一楼店 POS",
        "tags": ["真实资料案例", "出餐标签", "商品销量"],
        "summary": "厨房出餐标签，记录小龙虾鸡蛋汉堡一份，标价 11.90 元。",
        "facts": [
            "交易时间：2026-06-27 19:16",
            "取餐号：T10190",
            "商品：小龙虾鸡蛋汉堡，标价 11.90 元",
        ],
        "risks": ["出餐标签只能证明制作，不等同于已收款；需与 POS 小票或核销记录匹配"],
        "targets": ["出餐记录", "商品销量", "理论耗用", "POS对账"],
        "actions": ["寻找对应收款记录", "按配方扣减理论库存", "检查未匹配出餐标签"],
        "chain": "sale",
    },
    {
        "filename": "image-6.jpg",
        "title": "转让款银行回单 40,000 元",
        "doc_type": "转让协议",
        "source": "银行转账回单",
        "tags": ["真实资料案例", "转让款", "现金流凭证"],
        "summary": "2026-06-27 成功转账 40,000 元，附言为“转让费”；敏感账号仅保留脱敏事实。",
        "facts": [
            "交易时间：2026-06-27 14:29:50",
            "金额：40,000.00 元",
            "交易状态：成功",
            "用途/附言：转让费",
            "收付款账号：已脱敏，不进入前端结构化字段",
        ],
        "risks": [
            "付款人与收款人为个人账户，需要与转让协议主体、收款确认和商场交接材料相互印证",
            "该款属于开店投资/转让资产，不应计入日常经营成本",
        ],
        "targets": ["投资现金流", "转让协议", "付款凭证", "资产成本"],
        "actions": ["关联转让协议", "补充收款确认", "计入投资现金流而非当日损益"],
        "chain": "payment",
    },
]


def main() -> None:
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    box = DocumentBox.load(PROJECT_ID) or DocumentBox.create(PROJECT_ID)
    existing = {doc.get("file_ref") for doc in box.documents}
    added = 0

    for item in EVIDENCE:
        source = ATTACHMENT_DIR / item["filename"]
        if not source.exists():
            raise FileNotFoundError(f"缺少附件：{source}")
        target = PUBLIC_DIR / item["filename"]
        shutil.copy2(source, target)
        file_ref = f"/store-evidence/2026-06-29/{item['filename']}"
        if file_ref in existing:
            continue
        artifact = {
            "schema_version": "capture_artifact_v1",
            "source_type": item["source"],
            "document_class": item["doc_type"],
            "review_status": "needs_human_review",
            "write_targets": item["targets"],
            "confidence_summary": {"overall": "medium", "requires_confirmation": True},
            "canonical_sections": {
                "summary": item["summary"],
                "facts": [{"label": "识别事实", "value": fact, "confidence": "medium"} for fact in item["facts"]],
                "risks": [{"level": "high" if index == 0 else "medium", "detail": risk} for index, risk in enumerate(item["risks"])],
                "ai_next_actions": item["actions"],
            },
            "write_payloads": [],
        }
        box.add(
            StoreDocument(
                title=item["title"],
                doc_type=item["doc_type"],
                tags=item["tags"],
                source=item["source"],
                file_ref=file_ref,
                status="原始",
                key_terms=item["facts"],
                extracted_fields={
                    "structured_artifact": artifact,
                    "evidence_chain": item["chain"],
                },
                risk_flags=item["risks"],
                related_to={"store_id": PROJECT_ID, "captured_at": "2026-06-29"},
                notes=item["summary"],
            )
        )
        added += 1

    print(f"真实证据录入完成：新增 {added} 条，资料箱共 {len(box.documents)} 条")
    print(f"图片目录：{PUBLIC_DIR}")


if __name__ == "__main__":
    main()
