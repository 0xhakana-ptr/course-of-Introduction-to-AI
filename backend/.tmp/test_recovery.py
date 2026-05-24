import sys
sys.stdout.reconfigure(encoding='utf-8')

test_cases = [
    ("瑙掕壊璁惧畾", "角色设定"),
    ("鏈満", "本机"),
    ("鍐?", "写"),
    ("浠ｇ爜", "代码"),
]
print("=== Mojibake Recovery Test (GBK->UTF-8) ===")
for garbled, expected in test_cases:
    try:
        recovered = garbled.encode('gbk').decode('utf-8')
        match = "OK" if recovered == expected else f"MISMATCH (got: {recovered})"
        print(f"{match}: {garbled} -> {recovered} (expected: {expected})")
    except Exception as e:
        print(f"ERROR: {garbled} -> {e}")
