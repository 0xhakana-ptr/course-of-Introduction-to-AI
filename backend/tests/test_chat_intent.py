from backend.app.services.chat_action.intent import detect_intent


def test_detect_intent_returns_chat_for_greeting():
    assert detect_intent("hello there") == "chat"


def test_detect_intent_returns_coding_for_dev_prompt():
    assert detect_intent("please write python code") == "coding"


def test_detect_intent_returns_unknown_for_generic_text():
    assert detect_intent("random words without known keywords") == "unknown"
