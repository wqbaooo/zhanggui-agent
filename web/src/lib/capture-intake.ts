import {
  createBusinessFactsFromCapture,
  recognizeCapture,
  type RecognizeResponse,
} from "@/lib/api";
import { parseOperationDraft, type OperationDraft } from "@/lib/operationDraft";

export type CaptureSourceType =
  | "客如云"
  | "美团"
  | "抖音"
  | "淘宝闪购"
  | "进货单"
  | "库存照片"
  | "SOP资料"
  | "水电费用"
  | "投诉异常"
  | "经营文字"
  | "未知资料";

export type CaptureReview = {
  itemId: string;
  fileName: string;
  imageUrl?: string;
  source: CaptureSourceType;
  result: RecognizeResponse;
};

export function classifyCaptureSource(value: string): CaptureSourceType {
  const lower = value.toLowerCase();
  if (/客如云|keruyun|kyy|pos|营业|日报/.test(lower)) return "客如云";
  if (/美团|meituan/.test(lower)) return "美团";
  if (/抖音|douyin|tiktok|核销/.test(lower)) return "抖音";
  if (/淘宝|闪购|taobao|tbflash/.test(lower)) return "淘宝闪购";
  if (/进货|采购|供应|货单|supplier/.test(lower)) return "进货单";
  if (/库存|冰柜|货架|剩余|stock|inventory/.test(lower)) return "库存照片";
  if (/sop|总部|标准|卫生|培训|作业/.test(lower)) return "SOP资料";
  if (/水电|电费|水费|utility|electric/.test(lower)) return "水电费用";
  if (/投诉|差评|异常|complaint/.test(lower)) return "投诉异常";
  return "未知资料";
}

export async function processCaptureFile(file: File) {
  const result = await recognizeCapture(file);
  const source = classifyCaptureSource(result.source_type || file.name);
  try {
    const imported = await createBusinessFactsFromCapture({
      file_name: file.name,
      source_type: result.source_type || source,
      fields: result.fields,
      structured_artifact: result.structured_artifact,
      raw_text: result.raw_text,
      evidence_image_url: result.image_url,
    });
    return { result, source, imported, importError: null };
  } catch (error) {
    return {
      result,
      source,
      imported: { success: false, created: 0, facts: [] },
      importError: error instanceof Error ? error.message : "候选事实生成失败",
    };
  }
}

export async function processCaptureText(text: string) {
  const draft = parseOperationDraft(text);
  if (!draft) return null;
  const imported = await createBusinessFactsFromCapture({
    file_name: `文字录入-${Date.now()}.txt`,
    source_type: "经营文字",
    fields: draft.fields.map((field) => ({
      key: String(field.key),
      label: field.label,
      value: field.value,
      confidence: field.confidence,
    })),
    structured_artifact: {
      schema_version: "capture_artifact_v1",
      source_type: "经营文字",
      document_class: "经营事实描述",
      review_status: "needs_human_review",
      write_targets: ["今日待确认"],
      confidence_summary: { overall: draft.confidence },
    },
    raw_text: text,
  });
  return { draft, imported };
}

export function buildTextNoteReview(text: string, draft?: OperationDraft | null): CaptureReview {
  const recognizedFields = draft?.fields.map((field) => ({
    key: String(field.key),
    label: field.label,
    value: field.value,
    confidence: field.confidence,
  })) ?? [];
  return {
    itemId: `note-${Date.now()}`,
    fileName: "老板文字备注",
    source: "经营文字",
    result: {
      success: true,
      source_type: "经营文字",
      source_platform: "manual",
      capture_kind: "document",
      fields: recognizedFields,
      raw_text: text,
      analysis_summary: text,
      recommended_destination: "店铺档案",
      structured_artifact: {
        schema_version: "capture_artifact_v1",
        source_type: "经营文字",
        document_class: draft ? "经营事实描述" : "经营备注",
        review_status: "needs_human_review",
        write_targets: ["店铺档案"],
        confidence_summary: { overall: "high" },
        canonical_sections: {
          facts: [{
            label: "原始备注",
            value: text,
            confidence: "high",
            evidence: "店主本次输入",
          }],
        },
      },
    },
  };
}
