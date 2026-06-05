"""Generate 400-item test set for intent classification experiments."""
import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

items = []
_id = 0

def add(text, label, source):
    global _id
    _id += 1
    items.append({"id": _id, "text": text, "label": label, "source": source})

# ════════════════════════════════════════════════════════════
# MANUAL ITEMS (200)
# ════════════════════════════════════════════════════════════

# --- chat: 80 items ---
# Greetings (15)
for t in ["你好", "hello", "hi", "早上好", "晚上好", "hey", "嗨",
          "好久不见", "新年好", "good morning", "good night",
          "大家好", "哈喽", "在吗", "你醒了"]:
    add(t, "chat", "manual")

# Emotions (15)
for t in ["今天心情不好", "好累啊", "开心", "无聊", "我好烦",
          "好开心啊", "郁闷", "焦虑", "太棒了", "sad",
          "我很难过", "谢谢你", "辛苦了", "加油", "好困"]:
    add(t, "chat", "manual")

# General questions (15)
for t in ["你是谁", "你会做什么", "今天天气怎么样", "现在几点了",
          "你喜欢什么", "你有名字吗", "你多大了", "你在哪里",
          "how are you", "what can you do", "what time is it",
          "你聪明吗", "你会下棋吗", "你有梦想吗", "你觉得AI怎么样"]:
    add(t, "chat", "manual")

# Opinions/small talk (15)
for t in ["推荐一部电影", "讲个笑话", "推荐本书", "今天吃什么",
          "周末干什么", "我想睡觉了", "晚安", "再见", "我失眠了",
          "陪我聊天", "推荐一首歌", "你喜欢什么颜色",
          "今天好热", "我饿了", "你觉得学习难吗"]:
    add(t, "chat", "manual")

# Chat with tech words but NOT coding (10)
for t in ["Python好难", "我想学Python", "你觉得React好用吗",
          "JavaScript和TypeScript哪个好", "AI会取代程序员吗",
          "什么是机器学习", "你了解深度学习吗", "ChatGPT好厉害",
          "你和Siri谁聪明", "你用什么语言写的"]:
    add(t, "chat", "manual")

# Incomplete/ambiguous but leaning chat (10)
for t in ["帮我看看这个", "这个怎么用", "什么意思", "然后呢",
          "继续", "好的", "ok", "嗯嗯", "知道了", "明白"]:
    add(t, "chat", "manual")

# --- coding: 100 items ---
# File write (15)
for t in ["帮我写一个Python计算器", "创建一个hello world程序",
          "写一个快速排序算法", "implement a binary search in Python",
          "生成一个React组件", "写一个SQL建表语句", "创建一个Express路由",
          "写一个shell脚本", "帮我写个爬虫", "创建一个Dockerfile",
          "写一个Makefile", "生成requirements.txt", "写一个CLI工具",
          "创建REST API", "写单元测试"]:
    add(t, "coding", "manual")

# File read (10)
for t in ["read the config file", "查看README.md", "打开配置文件",
          "读取package.json", "看看main.py", "查看日志文件",
          "cat the source code", "打开index.html", "看看.env文件",
          "查看数据库配置"]:
    add(t, "coding", "manual")

# File delete/move/copy (10)
for t in ["删除temp文件夹", "把main.py重命名为app.py",
          "移动src到backup目录", "复制config.json",
          "delete the old logs", "rename utils.py to helpers.py",
          "copy the template file", "删掉build目录",
          "把样式文件移到css目录", "备份数据库文件"]:
    add(t, "coding", "manual")

# Search/list (10)
for t in ["搜索所有TODO", "列出src目录下的文件", "find all .py files",
          "搜索所有import语句", "grep for hardcoded strings",
          "列出所有配置文件", "搜索包含error的日志",
          "查看目录结构", "find unused variables", "列出所有测试文件"]:
    add(t, "coding", "manual")

# Test/run (10)
for t in ["运行测试", "run pytest", "执行单元测试",
          "运行所有测试", "test the API", "跑一下集成测试",
          "运行代码检查", "run the build", "执行lint检查",
          "运行性能测试"]:
    add(t, "coding", "manual")

# Debug/fix (10)
for t in ["这段代码报错了帮我看看", "fix the bug in utils.py",
          "Traceback说IndexError", "debug这个函数",
          "修复登录bug", "代码有异常", "fix the import error",
          "排查内存泄漏", "修复样式问题", "解决依赖冲突"]:
    add(t, "coding", "manual")

# Refactor/optimize (10)
for t in ["帮我重构这段代码", "优化这个函数的性能",
          "refactor the authentication logic", "优化数据库查询",
          "代码太乱了帮我整理", "add type hints",
          "代码风格不统一", "减少重复代码", "提取公共方法",
          "优化启动速度"]:
    add(t, "coding", "manual")

# Config/deploy (10)
for t in ["帮我配置ESLint", "部署到服务器", "配置CI/CD",
          "setup the dev environment", "配置数据库连接",
          "设置环境变量", "配置nginx", "deploy to staging",
          "配置HTTPS", "设置日志级别"]:
    add(t, "coding", "manual")

# Code with file paths (10)
for t in ["修改src/main.py的导入语句", "读取config/database.json",
          "删除build/static/*.map", "查看backend/app/main.py",
          "搜索src/components/下的TODO", "运行tests/test_api.py",
          "编辑docker-compose.yml", "查看.github/workflows/ci.yml",
          "修改webpack.config.js", "检查package-lock.json"]:
    add(t, "coding", "manual")

# Mixed language coding (5)
for t in ["帮我add一个new feature", "fix一下这个component的bug",
          "写个script自动deploy", "update the README file",
          "帮我build一下项目"]:
    add(t, "coding", "manual")

# --- unknown: 20 items ---
for t in ["嗯", "...", "啊", "哦", "额", "呃", "哈", "嘿", "哼", "唉",
          "？", "！", "…", "emmm", "emmmmm", "？？？", "。。。", "嗯嗯嗯",
          "啊啊啊", ""]:
    add(t, "unknown", "manual")

# ════════════════════════════════════════════════════════════
# LOG ITEMS (200) — deployment-style realistic prompts
# ════════════════════════════════════════════════════════════

# --- chat: 80 items ---
chat_log = [
    "你是谁啊", "今天吃什么好", "推荐一部电影吧", "讲个笑话来听听",
    "你觉得AI会取代人类吗", "我想睡觉了", "晚安", "你会唱歌吗",
    "给我讲个故事", "你喜欢什么颜色", "今天好热啊", "周末干什么好",
    "你有名字吗", "无聊怎么办", "帮我起个名字", "你觉得学习难吗",
    "推荐本书吧", "你会下棋吗", "今天心情不错", "谢谢你帮了我",
    "再见", "你多大了", "你在哪里住", "你聪明吗", "陪我聊聊天",
    "我失眠了", "你有梦想吗", "你害怕什么", "你最喜欢什么",
    "今天过得怎么样", "我好开心", "你在干嘛", "你觉得我怎么样",
    "你喜欢猫还是狗", "你吃饭了吗", "你在听什么歌", "你能笑一个吗",
    "你有女朋友吗", "你会做饭吗", "你最喜欢的电影是什么",
    "how are you doing", "what can you do for me", "tell me a joke please",
    "good morning", "thanks a lot", "bye bye", "what is your name",
    "I am so bored", "recommend me a book", "what time is it now",
    "do you like music", "how old are you", "where are you from",
    "are you smart", "can you sing", "do you have dreams",
    "what scares you", "what do you like most", "how was your day",
    "I am happy today", "what are you doing", "do you like cats",
    "did you eat", "what song are you listening to", "can you smile",
    "do you have friends", "can you cook", "what is your favorite movie",
    "nice to meet you", "see you later", "take care", "have a good day",
    "you are funny", "I like talking to you", "you are smart",
    "you are cute", "you are helpful", "you are the best",
    "I missed you", "you are back", "finally",
]
for t in chat_log:
    add(t, "chat", "log")

# --- coding: 90 items ---
coding_log = [
    "帮我创建一个新文件", "修改main.py的导入语句", "写一个单元测试",
    "搜索所有包含error的日志", "运行pytest", "查看package.json",
    "帮我重构这段代码", "优化这个函数的性能", "添加一个.gitignore文件",
    "检查代码风格", "生成requirements.txt", "写一个Makefile",
    "帮我配置ESLint", "创建一个Dockerfile", "写一个shell脚本",
    "搜索所有TODO注释", "把这段代码改成TypeScript", "添加错误处理",
    "写一个API接口", "创建数据库迁移脚本", "fix the import error",
    "run the test suite", "create a new module", "search for hardcoded values",
    "refactor the authentication logic", "write a README for me",
    "add logging to the server", "check Python version", "install dependencies",
    "build the project", "deploy to staging", "check memory usage",
    "write integration tests", "fix the CI pipeline",
    "update the documentation", "migrate to Python 3.12",
    "add type hints to the code", "write a CLI tool for this",
    "create a REST endpoint", "optimize database queries",
    "帮我写个登录页面", "创建一个用户注册功能", "修复分页bug",
    "添加搜索功能", "写一个文件上传接口", "实现权限控制",
    "配置数据库连接池", "添加缓存机制", "实现消息队列",
    "写一个定时任务", "创建管理后台", "添加数据导出功能",
    "实现WebSocket通信", "添加国际化支持", "写一个爬虫程序",
    "创建微服务架构", "配置负载均衡", "添加监控告警",
    "实现SSO单点登录", "添加审计日志功能",
    "write a sorting algorithm", "implement binary tree traversal",
    "create a REST API with FastAPI", "set up Docker Compose",
    "configure GitHub Actions CI", "add unit tests for auth module",
    "refactor the database layer", "implement caching with Redis",
    "write a migration script", "add rate limiting middleware",
    "create a plugin system", "implement event-driven architecture",
    "set up logging with ELK", "add API versioning",
    "implement OAuth2 authentication", "write a data validation module",
    "create a CLI with Click", "set up pytest fixtures",
    "add CORS configuration", "implement file upload with S3",
    "write a health check endpoint", "set up Prometheus metrics",
    "add request tracing", "implement circuit breaker pattern",
    "create a notification service", "write a backup script",
    "set up SSL certificates", "configure Nginx reverse proxy",
    "implement session management", "add pagination to API",
]
for t in coding_log:
    add(t, "coding", "log")

# --- unknown: 30 items ---
unknown_log = [
    "嗯", "哦", "额", "呃", "哈", "嘿", "哼", "唉",
    "...", "？", "！", "emmm", "emmmmm", "嗯嗯", "哦哦",
    "啊", "吧", "呢", "嘛", "呀", "哇", "呵", "切",
    "。。。", "？？？", "！！！", "嗯嗯嗯", "啊啊啊",
    "ok", "hmm",
]
for t in unknown_log:
    add(t, "unknown", "log")

# ════════════════════════════════════════════════════════════
# Save and report
# ════════════════════════════════════════════════════════════
with open(DATA_DIR / "test_set.json", "w", encoding="utf-8") as f:
    json.dump(items, f, ensure_ascii=False, indent=2)

# Statistics
from collections import Counter
labels = Counter(d["label"] for d in items)
sources = Counter((d["source"], d["label"]) for d in items)

print(f"Total: {len(items)}")
print(f"By label: {dict(labels)}")
print(f"By (source, label): {dict(sources)}")
avg_len = sum(len(d["text"]) for d in items) / len(items)
print(f"Avg text length: {avg_len:.1f} chars")
