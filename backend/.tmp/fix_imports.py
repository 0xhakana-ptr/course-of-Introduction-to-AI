import os, shutil

# 1. Fix api/chat_routes.py
fp = r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\api\chat_routes.py"
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace('from ..services.chat_interface import generate_chat_response', 'from ..services.chat import generate_chat_response')
with open(fp, 'w', encoding='utf-8') as f:
    f.write(content)
print('OK: chat_routes.py')

# 2. Fix api/run_routes.py
fp = r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\api\run_routes.py"
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace('from ..services.run_interface import (', 'from ..services.run import (')
with open(fp, 'w', encoding='utf-8') as f:
    f.write(content)
print('OK: run_routes.py')

# 3. Fix main.py
fp = r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\main.py"
with open(fp, 'r', encoding='utf-8') as f:
    content = f.read()
content = content.replace('from .services.run_interface import recover_interrupted_runs', 'from .services.run import recover_interrupted_runs')
with open(fp, 'w', encoding='utf-8') as f:
    f.write(content)
print('OK: main.py')

# 4. Delete chat_action/ directory
chat_action_dir = r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\services\chat_action"
if os.path.exists(chat_action_dir):
    shutil.rmtree(chat_action_dir)
    print('OK: Deleted chat_action/ directory')

# 5. Make tools/workspace/ a re-export layer
workspace_init = r"D:\codeAIAGENT\cyber-waifu-vue\backend\app\tools\workspace\__init__.py"
with open(workspace_init, 'w', encoding='utf-8') as f:
    f.write('"""Compatibility re-exports for tools.workspace subpackage."""\n')
    f.write('from ..workspace_constants import *  # noqa: F401, F403\n')
    f.write('from ..workspace_file_ops import *   # noqa: F401, F403\n')
    f.write('from ..workspace_formatters import *  # noqa: F401, F403\n')
    f.write('from ..workspace_utils import *     # noqa: F401, F403\n')
print('OK: tools/workspace/__init__.py -> re-export layer')

print('\nAll imports updated and chat_action/ deleted!')
