from main import build_store_context
from graph.agent import _build_local_fallback_system_prompt, research_node
from models.project import ProjectMemory


def test_chat_context_loads_operating_store_facts(monkeypatch):
    memory = ProjectMemory(project_id="xinyu-hengtai-dakou")
    memory.profile = {
        "stage": "operating",
        "monthly_rent": 6500,
        "current_staff_count": 3,
    }
    memory.daily_operations = [
        {
            "date": "2026-06-26",
            "revenue": 1980,
            "orders": 108,
            "food_cost": 693,
            "labor": 350,
        }
    ]
    monkeypatch.setattr(ProjectMemory, "load", classmethod(lambda cls, project_id: memory))

    context = build_store_context("xinyu-hengtai-dakou")

    assert context["store_status"] == "operating"
    assert context["last_7_days"]["entry_count"] == 1
    assert context["latest_operations"][0]["revenue"] == 1980
    assert "已开业" in context["context_rule"]


def test_chat_context_keeps_store_identity_when_memory_is_missing(monkeypatch):
    monkeypatch.setattr(ProjectMemory, "load", classmethod(lambda cls, project_id: None))

    context = build_store_context("xinyu-hengtai-dakou")

    assert context["store_name"] == "新余恒太城五楼大口章鱼烧"
    assert context["data_status"] == "门店档案尚未建立"


def test_local_model_fallback_receives_store_context():
    system_prompt = _build_local_fallback_system_prompt({
        "__store_context__": {
            "store_status": "operating",
            "last_7_days": {"entry_count": 7, "total_revenue": 13210},
        }
    })

    assert '"store_status": "operating"' in system_prompt
    assert '"entry_count": 7' in system_prompt
    assert "资料录入只是你的能力之一" in system_prompt


def test_local_model_fallback_receives_domain_report_and_owner_relationship():
    system_prompt = _build_local_fallback_system_prompt({
        "__domain_context__": {
            "route": {"domains": ["procurement", "channel"]},
            "response_contract": {
                "relationship": "用户是门店老板和经营决策者",
                "rules": ["总部管控物料不得推荐本地平替"],
            },
        }
    })

    assert "本轮领域报告" in system_prompt
    assert "用户是门店老板和经营决策者" in system_prompt
    assert "不能扮演顾客、店员或门店" in system_prompt


def test_domain_report_skips_duplicate_broad_knowledge_search():
    state = {
        "messages": [],
        "profile": {"__domain_context__": {"route": {"domains": ["procurement"]}}},
    }

    assert research_node(state) == {}
