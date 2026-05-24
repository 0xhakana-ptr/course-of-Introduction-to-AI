import pathlib
path = pathlib.Path(r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\agent_workflow\roleplay.py")
content = path.read_text("utf-8")

# Fix 1: max_tokens=120 -> 512
content = content.replace("max_tokens=120", "max_tokens=512")

# Fix 2: Replace the vision prompt to be clearer
old_prompt = '''        vision_prompt = (
            f"\u7075\u80fd\u611f\u77e5\u62a5\u544a\uff1a\u7528\u6237\u5c4f\u5e55\u4e0a\u68c0\u6d4b\u5230 "
            f"{elements}\uff0c\u6d3b\u52a8\u7c7b\u578b\u5224\u5b9a\u4e3a\u300c{activity}\u300d\u3002\\n"
            f"\u8bf7\u6839\u636e\u4ee5\u4e0a\u5c4f\u5e55\u89c2\u5bdf\uff0c\u4ee5\u89d2\u8272\u8eab\u4efd\u751f\u6210\u4e00\u53e5\u81ea\u7136\u7684 quip"
            f"\uff08\u226430\u5b57\uff09\u3002\u4e0d\u8981\u8f93\u51fa chat_line\uff0c\u53ea\u8f93\u51fa quip + expression\u3002\\n"
            f"\u8bb0\u4f4f\uff1a\u4f60\u662f\u684c\u9762\u5c0f\u7cbe\u7075\u300c\u672a\u547d\u540d\u300d\uff0c\u4f60\u5728\u5077\u770b\u7528\u6237\u7684\u5c4f\u5e55\u3002"
        )'''

new_prompt = '''        vision_prompt = (
            f"\u3010\u5c4f\u5e55\u89c2\u5bdf\u3011{elements}\uff0c\u6d3b\u52a8: {activity}\u3002"
            f"\u4f60\u662f\u684c\u9762\u5c0f\u7cbe\u7075\u300c\u672a\u547d\u540d\u300d\uff0c\u4f60\u5077\u770b\u4e86\u7528\u6237\u7684\u5c4f\u5e55\u3002"
            f"\u7528\u4e00\u53e5\u81ea\u7136\u7684\u4fcf\u76ae\u8bdd\uff08\u226430\u5b57\uff09\u53cd\u5e94\u4f60\u770b\u5230\u7684\u5185\u5bb9\u3002"
            f"\u53ea\u8f93\u51fa\u5408\u6cd5JSON: {{\"quip\": \"\u226430\u5b57\u7684\u4fcf\u76ae\u8bdd\", \"expression\": \"\u8868\u60c5\u540d\"}}"
        )'''

if old_prompt in content:
    content = content.replace(old_prompt, new_prompt)
    path.write_text(content, "utf-8")
    print("Fixed max_tokens + prompt")
else:
    print("Old prompt not found, checking...")
    for i, line in enumerate(content.split("\n")):
        if "vision_prompt" in line and "f\"" in line:
            print(f"Line {i+1}: {line[:100]}")
