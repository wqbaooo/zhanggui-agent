#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
开店做生意 Agent

设计取向：用 LangGraph/ReAct 的思路做轻量本地状态机。
它不是只按关键词吐知识库，而是按“识别目标 -> 补齐画像 -> 检索证据
-> 诊断风险 -> 制定规划 -> 给出下一步行动”的流程工作。
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from rag_engine import DEFAULT_INDEX_PATH, RagIndex

try:
    from openai import OpenAI
except Exception:  # DeepSeek 兼容 OpenAI SDK；未配置时走本地规划逻辑
    OpenAI = None

try:
    from tools.vector_search_tool import VectorSearchTool
    VECTOR_SEARCH_AVAILABLE = True
except Exception:
    VectorSearchTool = None
    VECTOR_SEARCH_AVAILABLE = False


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_KB = PROJECT_ROOT / "knowledge_base" / "开店Agent知识库.md"
DEFAULT_VIDEO_KB = PROJECT_ROOT / "knowledge_base" / "video_knowledge"
DEFAULT_DOCUMENT_KB = PROJECT_ROOT / "knowledge_base" / "document_knowledge"


def load_env_file(path: Path = PROJECT_ROOT / ".env"):
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_env_file()


@dataclass
class Evidence:
    source: str
    title: str
    content: str
    score: int
    status: str = "usable"


@dataclass
class AgentState:
    user_input: str
    intent: str = "通用"
    profile: Dict[str, str] = field(default_factory=dict)
    missing_fields: List[str] = field(default_factory=list)
    evidence: List[Evidence] = field(default_factory=list)
    risk_flags: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    source_audit: Dict[str, Any] = field(default_factory=dict)


class KnowledgeHub:
    """统一管理 Markdown、PDF抽取结果、视频转写结果和视频标题索引。"""

    def __init__(
        self,
        markdown_path: Path = DEFAULT_KB,
        video_dir: Path = DEFAULT_VIDEO_KB,
        document_dir: Path = DEFAULT_DOCUMENT_KB,
    ):
        self.markdown_path = markdown_path
        self.video_dir = video_dir
        self.document_dir = document_dir
        self.markdown_chunks = self._load_markdown(markdown_path)
        self.video_items = self._load_video_items(video_dir)
        self.document_items = self._load_document_items(document_dir)
        self.rag_index = RagIndex.load(DEFAULT_INDEX_PATH)
        # 向量检索工具（懒加载）
        self._vector_tool = VectorSearchTool() if VECTOR_SEARCH_AVAILABLE else None

    def audit(self) -> Dict[str, Any]:
        video_total = len(self.video_items)
        video_with_transcript = sum(1 for item in self.video_items if item.get("transcript"))
        document_total = len(self.document_items)
        document_usable = sum(1 for item in self.document_items if item.get("status") == "usable")
        return {
            "markdown_chunks": len(self.markdown_chunks),
            "video_total": video_total,
            "video_with_transcript": video_with_transcript,
            "video_without_transcript": video_total - video_with_transcript,
            "document_chunks": document_total,
            "document_usable_chunks": document_usable,
            "rag": self.rag_index.audit(),
        }

    def search(self, query: str, limit: int = 8, phase: str = "") -> List[Evidence]:
        # 优先尝试向量语义检索（支持分片路由）
        if self._vector_tool and self._vector_tool.available():
            try:
                params = {"query": query, "limit": limit}
                if phase:
                    params["category"] = phase
                result = self._vector_tool.execute(params)
                if result.success and result.data:
                    return [
                        Evidence(
                            source=ev.source or "向量知识库",
                            title=ev.title or "未命名",
                            content=ev.text or "",
                            score=int(ev.score * 100),
                            status=ev.status or "usable",
                        )
                        for ev in result.data
                    ]
            except Exception:
                pass  # fallback 到 BM25 / 关键词检索

        if self.rag_index.chunks:
            hits = self.rag_index.search(query, limit=limit, include_unusable=True)
            return [
                Evidence(
                    source=self._source_label(hit.chunk.source_type),
                    title=hit.chunk.title,
                    content=hit.chunk.text,
                    score=int(hit.score * 100),
                    status=hit.chunk.status,
                )
                for hit in hits
            ]

        terms = self._terms(query)
        candidates: List[Evidence] = []

        for title, content in self.markdown_chunks:
            score = self._score(title + "\n" + content, terms)
            if score:
                candidates.append(Evidence("核心知识库", title, content, score))

        for item in self.document_items:
            text = item.get("text", "")
            score = self._score(item.get("title", "") + "\n" + text, terms)
            if score:
                candidates.append(
                    Evidence(
                        item.get("source", "文档知识库"),
                        item.get("title", "文档片段"),
                        text,
                        score,
                        item.get("status", "usable"),
                    )
                )

        for item in self.video_items:
            searchable = json.dumps(item, ensure_ascii=False)
            score = self._score(searchable, terms)
            if score:
                transcript = item.get("transcript")
                status = "transcribed" if transcript else "title_index_only"
                content = self._video_content(item)
                candidates.append(Evidence("视频课程", item.get("title", "未命名视频"), content, score, status))

        return sorted(candidates, key=lambda e: e.score, reverse=True)[:limit]

    def _source_label(self, source_type: str) -> str:
        return {
            "core_markdown": "核心知识库",
            "document": "文档知识库",
            "video": "视频课程",
        }.get(source_type, source_type)

    def _load_markdown(self, path: Path) -> List[Tuple[str, str]]:
        if not path.exists():
            return []
        content = path.read_text(encoding="utf-8")
        chunks: List[Tuple[str, str]] = []
        sections = re.split(r"^##\s+", content, flags=re.MULTILINE)
        for section in sections[1:]:
            lines = section.strip().splitlines()
            if not lines:
                continue
            section_title = lines[0].strip()
            body = "\n".join(lines[1:]).strip()
            subsections = re.split(r"^###\s+", body, flags=re.MULTILINE)
            if len(subsections) == 1:
                chunks.append((section_title, body))
                continue
            for subsection in subsections[1:]:
                sub_lines = subsection.strip().splitlines()
                if sub_lines:
                    chunks.append((f"{section_title} / {sub_lines[0].strip()}", "\n".join(sub_lines[1:]).strip()))
        return chunks

    def _load_video_items(self, path: Path) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        if not path.exists():
            return items
        for file_path in path.glob("**/*.json"):
            if file_path.name in {"master_knowledge_base.json", "transcription_status.json"}:
                continue
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(data, dict) or "video_info" not in data:
                continue
            info = data.get("video_info", {})
            knowledge = data.get("knowledge", {})
            items.append(
                {
                    "title": info.get("title") or knowledge.get("title") or file_path.stem,
                    "category": info.get("category") or knowledge.get("category") or file_path.parent.name,
                    "path": info.get("path", ""),
                    "keywords": knowledge.get("keywords", []),
                    "tags": knowledge.get("tags", []),
                    "summary": knowledge.get("summary", ""),
                    "key_points": knowledge.get("key_points", []),
                    "actionable_tips": knowledge.get("actionable_tips", []),
                    "transcript": data.get("transcript"),
                }
            )
        return items

    def _load_document_items(self, path: Path) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        if not path.exists():
            return items
        for file_path in path.glob("*.json"):
            try:
                data = json.loads(file_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(data, dict) and "chunks" in data:
                for chunk in data["chunks"]:
                    chunk["source"] = data.get("source", file_path.name)
                    items.append(chunk)
            elif isinstance(data, list):
                items.extend(data)
        return items

    def _video_content(self, item: Dict[str, Any]) -> str:
        lines = [
            f"分类: {item.get('category', '')}",
            f"关键词: {', '.join(item.get('keywords', []))}",
            f"标签: {', '.join(item.get('tags', []))}",
        ]
        if item.get("summary"):
            lines.append(f"摘要: {item['summary']}")
        if item.get("key_points"):
            lines.append("要点: " + "；".join(item["key_points"][:5]))
        if item.get("actionable_tips"):
            lines.append("行动建议: " + "；".join(item["actionable_tips"][:5]))
        if not item.get("transcript"):
            lines.append("注意: 当前只有标题/关键词索引，尚未完成视频语音转写。")
        return "\n".join(lines)

    def _terms(self, query: str) -> List[str]:
        seed = [
            "选址", "商圈", "商铺", "位置", "客流", "动线", "聚客", "转让",
            "选品", "品类", "产品", "小吃", "早餐", "粉面",
            "成本", "利润", "财务", "租金", "投产", "回本",
            "运营", "营销", "推广", "开业", "抖音", "团购",
            "加盟", "自营", "风险", "避坑", "合同", "装修",
        ]
        terms = [term for term in seed if term in query]
        terms += [part for part in re.split(r"\W+", query.lower()) if len(part) >= 2]
        return list(dict.fromkeys(terms)) or [query]

    def _score(self, text: str, terms: Iterable[str]) -> int:
        if not text:
            return 0
        text_lower = text.lower()
        return sum(text_lower.count(term.lower()) * (3 if len(term) >= 2 else 1) for term in terms)


class DeepSeekReasoner:
    """可选的 DeepSeek 推理层。没有 API key 时，本地规则 Agent 仍可工作。"""

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.model = model or os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        self.client = None
        if self.api_key and OpenAI:
            self.client = OpenAI(api_key=self.api_key, base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"))

    def available(self) -> bool:
        return self.client is not None

    def synthesize(self, state: AgentState, draft: str) -> str:
        if not self.client:
            return draft
        evidence_text = "\n\n".join(
            f"[{idx}] {e.source} / {e.title} / {e.status}\n{e.content[:900]}"
            for idx, e in enumerate(state.evidence[:8], 1)
        )
        prompt = f"""你是一个餐饮开店规划 Agent，不是资料复读器。
基于用户问题、当前开店画像、风险信号和证据，输出可执行规划。
如果信息不足，先给阶段性判断，并明确下一轮需要用户补充的关键字段。

用户问题：{state.user_input}
识别意图：{state.intent}
画像：{json.dumps(state.profile, ensure_ascii=False)}
缺失字段：{', '.join(state.missing_fields)}
风险信号：{'; '.join(state.risk_flags)}
证据：
{evidence_text}

本地规划草稿：
{draft}
"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "你输出中文，务实、具体、保守，重点是开店决策质量。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
            )
            return response.choices[0].message.content or draft
        except Exception as exc:
            return draft + f"\n\n> DeepSeek 调用失败，已使用本地规划结果：{exc}"


class StoreOpeningPlanner:
    city_names = [
        "北京", "上海", "广州", "深圳", "杭州", "成都", "重庆", "武汉", "南京", "苏州",
        "西安", "长沙", "郑州", "天津", "青岛", "宁波", "厦门", "福州", "合肥", "无锡",
    ]
    required_fields = {
        "城市/商圈": ["城市", "商圈", "地段", "附近", "位置"],
        "品类": ["品类", "项目", "产品", "早餐", "粉面", "小吃", "餐饮"],
        "预算": ["预算", "资金", "万", "成本", "租金"],
        "经营方式": ["加盟", "自营", "合伙", "摆摊"],
        "店铺状态": ["已有铺", "找铺", "转让", "开店", "筹备"],
    }

    def analyze_intent(self, text: str) -> str:
        mapping = [
            ("开店规划", ["规划", "方案", "计划", "怎么开", "准备开", "想开店", "能不能做", "可不可行", "可行性", "判断", "评估"]),
            ("选址诊断", ["选址", "商圈", "商铺", "位置", "地段", "客流", "动线"]),
            ("选品决策", ["选品", "品类", "项目", "产品", "做什么"]),
            ("财务测算", ["成本", "利润", "租金", "回本", "投产", "流水"]),
            ("风险控制", ["风险", "避坑", "合同", "转让", "亏", "防骗"]),
            ("营销运营", ["运营", "营销", "推广", "抖音", "团购", "开业活动"]),
        ]
        for intent, keys in mapping:
            if any(key in text for key in keys):
                return intent
        return "通用咨询"

    def extract_profile(self, text: str) -> Dict[str, str]:
        profile: Dict[str, str] = {}
        for city in self.city_names:
            if city in text:
                profile["城市/商圈"] = city
                break
        money = re.search(r"(\d+(?:\.\d+)?)\s*(万|元|w|W)", text)
        if money:
            profile["预算"] = money.group(0)
        rent = re.search(r"租金[^\d]*(\d+(?:\.\d+)?)\s*(万|元|w|W)?", text)
        if rent:
            profile["租金"] = rent.group(0)
        for field, keys in self.required_fields.items():
            if any(key in text for key in keys):
                profile[field] = "已提及"
        return profile

    def missing_fields(self, text: str, intent: str) -> List[str]:
        needed = ["城市/商圈", "品类", "预算", "经营方式"]
        if intent in {"选址诊断", "财务测算"}:
            needed += ["店铺面积", "月租金", "预估日客流", "竞品数量"]
        missing = []
        for field in needed:
            if field == "城市/商圈" and any(city in text for city in self.city_names):
                continue
            keys = self.required_fields.get(field, [field])
            if not any(key in text for key in keys):
                missing.append(field)
        return list(dict.fromkeys(missing))[:6]

    def diagnose_risks(self, text: str, evidence: List[Evidence]) -> List[str]:
        risks = []
        if "加盟" in text:
            risks.append("加盟项目需要先验证供应链、合同退出条款、真实门店盈利，不能只看总部样板。")
        if any(word in text for word in ["转让", "接店"]):
            risks.append("转让店重点核查原店闭店原因、房东是否认可转让、设备折价和隐性债务。")
        if any(word in text for word in ["地铁口", "路过", "人很多"]):
            risks.append("高人流不等于有效客流，需要看停留意愿、消费场景和进店转化。")
        if not any(e.status in {"transcribed", "usable"} for e in evidence if e.source == "视频课程"):
            risks.append("视频库目前仍以标题索引为主，视频内容需要转写后才能作为强证据。")
        return risks

    def next_actions(self, state: AgentState) -> List[str]:
        actions = [
            "先填写开店画像：城市/商圈、品类、预算、经营方式、是否已有铺位。",
            "做两轮实地蹲点：工作日和周末各覆盖早高峰、午高峰、晚高峰。",
            "列 500 米内竞品表：品类、价格带、排队情况、外卖销量、差评原因。",
            "做保守财务模型：日单量、客单价、毛利率、租金、人力、回本周期。",
        ]
        if state.intent == "选址诊断":
            actions.insert(1, "拍下铺位门头、门前动线、左右邻铺、对面街景，并记录 30 分钟有效客流。")
        if state.intent == "营销运营":
            actions.append("开业前准备团购品、达人名单、3 条同城短视频脚本和试营业反馈表。")
        return actions[:6]

    def compose_local_answer(self, state: AgentState) -> str:
        lines = [
            f"# {state.intent}",
            "",
        ]

        if state.missing_fields:
            lines += [
                "## 关键信息补全建议",
                "以下字段将直接影响决策质量，建议优先明确：",
            ]
            lines += [f"- {field}" for field in state.missing_fields]
            lines.append("")

        lines += ["## 阶段性诊断"]
        if state.intent == "开店规划":
            lines += [
                "- 先不要从“开什么店”开始，要从“谁在什么场景下为什么复购”开始。",
                "- 开店方案应该拆成四块：选品、选址、财务模型、开业获客，而不是只做知识问答。",
                "- 如果预算不高，优先考虑低装修、低人工、刚需、高复购的小店模型。",
            ]
        elif state.intent == "选址诊断":
            lines += [
                "- 选址核心不是人多，而是目标客群、有效动线、消费场景三者同时成立。",
                "- 先排除硬伤：明火/排烟/消防/转让权/租期/递增/外摆/停车/拆迁。",
                "- 再做收益倒推：月营业额至少要覆盖租金、人力、食材、平台和损耗后还能有现金流。",
            ]
        elif state.intent == "财务测算":
            lines += [
                "- 用保守模型算，不用乐观模型算。先算活下来，再算赚多少。",
                "- 至少拆日单量、客单价、毛利率、租金、人力、平台费、装修摊销、回本周期。",
            ]
        else:
            lines += [
                "- 建议结合具体开店画像进行深度分析，以确保建议的针对性。",
                "- 优先执行可验证的实地调研动作，以数据支撑决策。",
            ]
        lines.append("")

        if state.risk_flags:
            lines += ["## 风险提醒"]
            lines += [f"- {risk}" for risk in state.risk_flags]
            lines.append("")

        lines += ["## 下一步行动"]
        lines += [f"{idx}. {action}" for idx, action in enumerate(state.actions, 1)]
        lines.append("")

        if state.evidence:
            lines += ["## 参考依据"]
            for evidence in state.evidence[:5]:
                status_note = "" if evidence.status == "usable" else f"（{evidence.status}）"
                snippet = re.sub(r"\s+", " ", evidence.content).strip()[:180]
                lines.append(f"- {evidence.source} / {evidence.title}{status_note}: {snippet}")
            lines.append("")

        audit = state.source_audit
        lines += [
            "## 知识源状态",
            f"- 核心知识片段：{audit.get('markdown_chunks', 0)}",
            f"- 文档可用片段：{audit.get('document_usable_chunks', 0)}/{audit.get('document_chunks', 0)}",
            f"- 视频已转写：{audit.get('video_with_transcript', 0)}/{audit.get('video_total', 0)}",
        ]
        rag_audit = audit.get("rag", {})
        if rag_audit:
            lines.append(f"- RAG 索引片段：{rag_audit.get('chunks', 0)}")
        if audit.get("video_without_transcript", 0):
            lines.append("- 注意：未转写视频只能作为课程目录线索，不能当作完整视频内容证据。")
        return "\n".join(lines)


class 开店Agent:
    """对外保持原类名，内部改为 Agent 状态机。"""

    def __init__(
        self,
        knowledge_base_path: Optional[str] = None,
        video_knowledge_path: Optional[str] = None,
        document_knowledge_path: Optional[str] = None,
        deepseek_api_key: Optional[str] = None,
    ):
        self.knowledge_hub = KnowledgeHub(
            Path(knowledge_base_path) if knowledge_base_path else DEFAULT_KB,
            Path(video_knowledge_path) if video_knowledge_path else DEFAULT_VIDEO_KB,
            Path(document_knowledge_path) if document_knowledge_path else DEFAULT_DOCUMENT_KB,
        )
        self.planner = StoreOpeningPlanner()
        self.reasoner = DeepSeekReasoner(api_key=deepseek_api_key)
        self.conversation_history: List[Tuple[str, str]] = []

    def get_response(self, user_input: str) -> str:
        self.conversation_history.append(("user", user_input))
        state = self._run_graph(user_input)
        draft = self.planner.compose_local_answer(state)
        response = self.reasoner.synthesize(state, draft)
        self.conversation_history.append(("agent", response))
        return response

    def _run_graph(self, user_input: str) -> AgentState:
        state = AgentState(user_input=user_input)
        state.intent = self.planner.analyze_intent(user_input)
        state.profile = self.planner.extract_profile(user_input)
        state.missing_fields = self.planner.missing_fields(user_input, state.intent)
        search_query = self._build_search_query(state)
        state.evidence = self.knowledge_hub.search(search_query)
        state.source_audit = self.knowledge_hub.audit()
        state.risk_flags = self.planner.diagnose_risks(user_input, state.evidence)
        state.actions = self.planner.next_actions(state)
        return state

    def _build_search_query(self, state: AgentState) -> str:
        intent_terms = {
            "开店规划": "开店流程 选品 选址 成本 风险",
            "选址诊断": "选址 商圈 商铺 客流 动线 聚客 转让 合同",
            "选品决策": "选品 品类 小吃 早餐 粉面 竞争",
            "财务测算": "成本 利润 租金 投产 回本 财务模型",
            "风险控制": "避坑 风险 加盟 合同 转让 装修",
            "营销运营": "运营 营销 抖音 同城 团购 开业活动",
        }
        return f"{state.user_input} {intent_terms.get(state.intent, '')}"

    def reset_conversation(self):
        self.conversation_history = []

    def get_conversation_history(self) -> List[Tuple[str, str]]:
        return self.conversation_history

    def audit_sources(self) -> Dict[str, Any]:
        return self.knowledge_hub.audit()


def main():
    """委托给 main.py 的统一入口（支持 LangGraph v3.0）。"""
    from main import 开店Agent

    agent = 开店Agent()

    if "--audit" in sys.argv:
        print(json.dumps(agent.audit_sources(), ensure_ascii=False, indent=2))
        return

    if len(sys.argv) > 1:
        user_input = " ".join(arg for arg in sys.argv[1:] if arg != "--audit")
        print(agent.get_response(user_input))
        return

    if not sys.stdin.isatty():
        for line in sys.stdin:
            user_input = line.strip()
            if user_input:
                print(agent.get_response(user_input))
                print("\n" + "-" * 50 + "\n")
        return

    print("开店做生意 Agent (v3 - LangGraph/ReAct)")
    print("输入问题，输入 '退出' 结束，输入 '重置' 清空对话。")
    print("可先说：我想在某城市/商圈，用多少预算，做什么品类，帮我规划。")
    print("-" * 50)

    while True:
        try:
            user_input = input("\n你: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if user_input in {"退出", "quit", "exit"}:
            break
        if user_input in {"重置", "reset"}:
            agent.reset_conversation()
            print("对话已重置。")
            continue
        if not user_input:
            continue

        print("\nAgent:")
        response = agent.get_response(user_input)
        print(response)


if __name__ == "__main__":
    main()
