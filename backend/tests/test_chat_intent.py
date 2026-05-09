from backend.app.services.chat_action.intent import detect_intent


def test_detect_intent_returns_chat_for_greeting():
    assert detect_intent("hello there") == "chat"


def test_detect_intent_returns_coding_for_dev_prompt():
    assert detect_intent("please write python code") == "coding"


def test_detect_intent_returns_chat_for_generic_natural_language():
    assert detect_intent("random words without known keywords") == "chat"


def test_detect_intent_returns_chat_for_who_am_i_question():
    assert detect_intent("我是谁") == "chat"


def test_detect_intent_returns_chat_for_conceptual_tech_question():
    assert detect_intent("FastAPI 是什么？") == "chat"


def test_detect_intent_returns_coding_for_file_operation_prompt():
    assert detect_intent("请检查 main.py 的导入") == "coding"


def test_detect_intent_uses_llm_router_for_ambiguous_prompt(monkeypatch):
    monkeypatch.setattr("backend.app.services.chat_action.intent.llm_is_configured", lambda: True)
    monkeypatch.setattr(
        "backend.app.services.chat_action.intent.call_llm_sync",
        lambda *args, **kwargs: type(
            "FakeLLMResult",
            (),
            {"ok": True, "output": "coding", "error": None},
        )(),
    )

    assert detect_intent("把这个组件改一下") == "coding"


def test_detect_intent_falls_back_to_chat_when_llm_output_is_invalid(monkeypatch):
    monkeypatch.setattr("backend.app.services.chat_action.intent.llm_is_configured", lambda: True)
    monkeypatch.setattr(
        "backend.app.services.chat_action.intent.call_llm_sync",
        lambda *args, **kwargs: type(
            "FakeLLMResult",
            (),
            {"ok": True, "output": "maybe", "error": None},
        )(),
    )

    assert detect_intent("random words without known keywords") == "chat"


def test_detect_intent_returns_unknown_for_symbolic_text():
    assert detect_intent("???") == "unknown"
