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


def test_detect_intent_returns_chat_for_general_math_question():
    assert detect_intent("1+1=？") == "chat"


def test_detect_intent_returns_chat_for_conceptual_programming_question():
    assert detect_intent("Python 是什么") == "chat"


def test_detect_intent_returns_coding_for_file_operation_prompt():
    assert detect_intent("请检查 main.py 的导入") == "coding"


def test_detect_intent_returns_coding_for_file_reference_before_chinese_punctuation():
    assert detect_intent("请创建 notes/chat-loop.txt，内容是chat loop ok") == "coding"


def test_detect_intent_returns_coding_for_workspace_operation_prompt():
    assert detect_intent("把这个组件改一下") == "coding"


def test_detect_intent_returns_coding_for_directory_listing_prompt():
    assert detect_intent("请列出 notes/listed 目录结构") == "coding"


def test_detect_intent_returns_coding_for_demo_build_prompt():
    assert detect_intent("请实现一个简单的计算器 demo") == "coding"


def test_detect_intent_returns_coding_for_runtime_error_prompt():
    assert detect_intent("pnpm dev 报错") == "coding"


def test_detect_intent_defaults_natural_language_to_chat():
    assert detect_intent("random words without known keywords") == "chat"


def test_detect_intent_returns_unknown_for_symbolic_text():
    assert detect_intent("???") == "unknown"
