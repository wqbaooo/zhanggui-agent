#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from fastapi.testclient import TestClient

from graph.agent import personality_inject_node
from server.main import app
from server.model_routing import local_text_route, local_vision_route, model_routing_state, speech_route
import server.routes.speech as speech_api


def test_free_input_capability_routes(monkeypatch):
    monkeypatch.delenv("OLLAMA_VISION_MODEL", raising=False)
    monkeypatch.delenv("OLLAMA_TEXT_MODEL", raising=False)

    assert local_vision_route().model == "qwen3.5:4b-q4_K_M"
    assert local_vision_route().free is True
    assert local_text_route().model == "qwen3.5:4b-q4_K_M"
    assert speech_route().model == "small"

    state = model_routing_state()
    assert state["intake_pipelines"]["image"][-1] == "human_confirmation"
    assert state["intake_pipelines"]["speech"][1] == "human_confirmation"
    assert "reasoning_text_fallback" in state["intake_pipelines"]["text"]
    assert personality_inject_node({"messages": []}) == {}


def test_speech_transcript_requires_human_review(monkeypatch):
    monkeypatch.setattr(
        speech_api,
        "_transcribe",
        lambda _path: {"text": "今天营业额三千五百元", "duration_seconds": 2.4},
    )

    response = TestClient(app).post(
        "/api/speech/transcribe",
        files={"audio": ("recording.webm", b"audio-bytes", "audio/webm")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["text"] == "今天营业额三千五百元"
    assert payload["review_status"] == "needs_human_review"
    assert payload["extracted_fields"]["fields"]["revenue"] == 3500
