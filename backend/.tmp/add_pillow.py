import pathlib
path = pathlib.Path(r"D:\codeAIAGENT\cyber-waifu-vue\backend\requirements.txt")
lines = path.read_text("utf-8").split("\n")
# Add Pillow after onnxruntime line
new_lines = []
for line in lines:
    new_lines.append(line)
    if line.startswith("onnxruntime"):
        new_lines.append("Pillow>=10.0")
path.write_text("\n".join(new_lines), "utf-8")
print("Added Pillow to requirements.txt")
# Print the relevant lines
for i, line in enumerate(new_lines):
    if "onnx" in line.lower() or "pillow" in line.lower():
        print(f"  line {i+1}: {line}")
