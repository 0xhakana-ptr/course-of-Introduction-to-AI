# Test Set Labeling Guideline

## Label Definitions

### coding
Input contains at least ONE of:
- A programming action verb (写/改/修/fix/write/create/delete/...) AND a workspace object (文件/代码/module/test/...)
- A file path reference (e.g., src/main.py, /path/to/file)
- A code structure hint (def, import, class, function, Traceback, exception)
- A CLI command (pytest, npm, pip, git, ...)
- An error signal (bug, 报错, traceback, exception) AND a workspace object or tech context

### chat
- Pure natural language with no programming keywords
- Greetings, emotions, opinions, questions unrelated to coding
- Ambiguous input that does NOT match any coding rule

### unknown
- Empty or whitespace-only input
- Single characters or meaningless noise
- Input with no natural language content

## Notes on Log Data
Log-derived items (source="log") labels come from the system's own `detect_intent()` function.
This introduces circular validation risk: the system's classifier labels are used to evaluate the same classifier.
We acknowledge this limitation in the paper and mitigate it by:
1. Including 200 manually labeled items (source="manual") as ground truth
2. Reporting per-source breakdown in all result tables
