import httpx

from app.services import llm_service


class FakeResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {
            "message": {
                "role": "assistant",
                "content": "Critical shortage requires urgent outsourcing.",
            }
        }


SELECTED_ACTION_JSON = (
    '{"recommendation": "Add 10 outsourced couriers today.", '
    '"timing": "Runs 2026-08-01 to 2026-08-01, deadline 2026-08-01.", '
    '"reasons": ["Short-term shortage requires immediate outsourcing."]}'
)


class FakeSelectedActionResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {
            "message": {
                "role": "assistant",
                "content": SELECTED_ACTION_JSON,
            }
        }


def test_returns_none_when_ollama_is_disabled(monkeypatch):
    monkeypatch.setenv("OLLAMA_ENABLED", "false")

    def fail_if_called(*args, **kwargs):
        raise AssertionError("HTTP request must not be called")

    monkeypatch.setattr(
        llm_service.httpx,
        "post",
        fail_if_called,
    )

    result = llm_service.request_llm_explanation(
        {"shortage": 10},
        "en",
    )

    assert result is None


def test_returns_explanation_from_ollama(monkeypatch):
    monkeypatch.setenv("OLLAMA_ENABLED", "true")
    monkeypatch.setenv(
        "OLLAMA_BASE_URL",
        "http://ollama.test:11434",
    )
    monkeypatch.setenv("OLLAMA_MODEL", "qwen2.5:7b")

    captured_request = {}

    def fake_post(url, *, json, timeout):
        captured_request["url"] = url
        captured_request["body"] = json
        captured_request["timeout"] = timeout

        return FakeSelectedActionResponse()

    monkeypatch.setattr(
        llm_service.httpx,
        "post",
        fake_post,
    )

    result = llm_service.request_llm_explanation(
        {
            "scope": {"decision_action_id": "action-1"},
            "decision_plan": {
                "items": [
                    {
                        "action_id": "action-1",
                        "store_id": "DXB-001",
                        "action_type": "emergency_outsourcing",
                        "couriers": 10,
                    }
                ]
            },
        },
        "en",
    )

    assert result == {
        "recommendation": "Add 10 outsourced couriers today.",
        "timing": "Runs 2026-08-01 to 2026-08-01, deadline 2026-08-01.",
        "reasons": ["Short-term shortage requires immediate outsourcing."],
    }

    assert captured_request["url"] == ("http://ollama.test:11434/api/chat")
    assert captured_request["body"]["model"] == "qwen2.5:7b"
    assert captured_request["body"]["stream"] is False
    assert captured_request["body"]["think"] is False
    assert captured_request["body"]["format"] == "json"
    assert '"recommendation"' in (
        captured_request["body"]["messages"][0]["content"]
    )
    assert '"timing"' in (
        captured_request["body"]["messages"][0]["content"]
    )
    assert '"reasons"' in (
        captured_request["body"]["messages"][0]["content"]
    )
    user_content = captured_request["body"]["messages"][1]["content"]

    assert '"selected_action"' in user_content
    assert '"action_id": "action-1"' in user_content
    assert '"scope"' not in user_content


def test_returns_none_when_selected_action_json_is_malformed(monkeypatch):
    monkeypatch.setenv("OLLAMA_ENABLED", "true")

    monkeypatch.setattr(
        llm_service.httpx,
        "post",
        lambda *args, **kwargs: FakeResponse(),
    )

    result = llm_service.request_llm_explanation(
        {
            "scope": {"decision_action_id": "action-1"},
            "decision_plan": {
                "items": [
                    {
                        "action_id": "action-1",
                        "store_id": "DXB-001",
                        "action_type": "emergency_outsourcing",
                        "couriers": 10,
                    }
                ]
            },
        },
        "en",
    )

    assert result is None


def test_returns_none_when_ollama_is_unavailable(monkeypatch):
    monkeypatch.setenv("OLLAMA_ENABLED", "true")

    def raise_connection_error(*args, **kwargs):
        raise httpx.ConnectError("Ollama unavailable")

    monkeypatch.setattr(
        llm_service.httpx,
        "post",
        raise_connection_error,
    )

    result = llm_service.request_llm_explanation(
        {"shortage": 10},
        "en",
    )

    assert result is None
