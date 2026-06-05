"""Run intent classification experiments on the test set."""
import sys, json, time, random
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.app.agent_workflow.intent import (
    detect_intent, looks_like_coding_prompt,
    _has_coding_action, _has_strong_operation_action,
    _has_workspace_object, _has_deliverable_object,
    has_workspace_path_reference, has_command_reference,
    _has_issue_keyword, _has_tech_context,
    has_file_reference, _has_code_structure_hint,
    CODING_ACTION_KEYWORDS, STRONG_OPERATION_ACTION_KEYWORDS,
    WORKSPACE_OBJECT_KEYWORDS, DELIVERABLE_OBJECT_KEYWORDS,
    TECH_CONTEXT_KEYWORDS, COMMAND_INLINE_KEYWORDS,
    CODING_ISSUE_KEYWORDS,
)

random.seed(42)
DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Load all coding keywords for Rule-Only baseline
ALL_KWS = set()
for kw_set in [CODING_ACTION_KEYWORDS, STRONG_OPERATION_ACTION_KEYWORDS,
               WORKSPACE_OBJECT_KEYWORDS, DELIVERABLE_OBJECT_KEYWORDS,
               TECH_CONTEXT_KEYWORDS, COMMAND_INLINE_KEYWORDS,
               CODING_ISSUE_KEYWORDS]:
    ALL_KWS.update(k.lower() for k in kw_set)

def load_test_set():
    return json.load(open(DATA_DIR / "test_set.json", encoding="utf-8"))

def baseline_rule_only(text):
    t = text.lower()
    for kw in ALL_KWS:
        if kw in t:
            return "coding"
    return "chat"

def baseline_keyword_score_1(text):
    s = str(text or "").strip()
    if not s:
        return "unknown"
    if has_file_reference(s) or _has_code_structure_hint(s):
        return "coding"
    hits = sum([
        _has_coding_action(s), _has_strong_operation_action(s),
        _has_workspace_object(s), _has_deliverable_object(s),
        has_workspace_path_reference(s), has_command_reference(s),
        _has_issue_keyword(s), _has_tech_context(s),
    ])
    return "coding" if hits >= 1 else "chat"

def ours(text):
    return detect_intent(text)

def run_method(data, fn, name):
    results = []
    latencies = []
    for item in data:
        start = time.perf_counter()
        pred = fn(item["text"])
        ms = (time.perf_counter() - start) * 1000
        latencies.append(ms)
        results.append({"true": item["label"], "pred": pred, "correct": pred == item["label"],
                        "source": item["source"], "latency_ms": ms})

    acc = sum(r["correct"] for r in results) / len(results)
    avg_lat = sum(latencies) / len(latencies)

    classes = ["chat", "coding", "unknown"]
    pc = {}
    for c in classes:
        tp = sum(1 for r in results if r["true"] == c and r["pred"] == c)
        fp = sum(1 for r in results if r["true"] != c and r["pred"] == c)
        fn_ = sum(1 for r in results if r["true"] == c and r["pred"] != c)
        p = tp / (tp + fp) if (tp + fp) else 0
        r = tp / (tp + fn_) if (tp + fn_) else 0
        f1 = 2*p*r / (p+r) if (p+r) else 0
        pc[c] = {"precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4),
                 "support": sum(1 for x in results if x["true"] == c)}

    total = len(results)
    wf1 = sum(pc[c]["f1"] * pc[c]["support"] / total for c in classes)

    # Per-source breakdown
    for src in ["manual", "log"]:
        src_results = [r for r in results if r["source"] == src]
        src_acc = sum(r["correct"] for r in src_results) / len(src_results) if src_results else 0
        print(f"  [{src}] n={len(src_results)} acc={src_acc:.3f}")

    return {"method": name, "accuracy": round(acc, 4), "weighted_f1": round(wf1, 4),
            "avg_latency_ms": round(avg_lat, 3), "per_class": pc, "n": len(results),
            "results": results}

def main():
    data = load_test_set()
    print(f"Test set: {len(data)} items\n")

    all_results = {}

    for name, fn in [("Rule-Only", baseline_rule_only),
                     ("Keyword-Score>=1", baseline_keyword_score_1),
                     ("Ours", ours)]:
        print(f"[{name}]")
        r = run_method(data, fn, name)
        all_results[name] = r
        print(f"  F1={r['weighted_f1']:.3f}  Acc={r['accuracy']:.3f}  Latency={r['avg_latency_ms']:.3f}ms\n")

    # Save
    save_data = {k: {kk: vv for kk, vv in v.items() if kk != "results"} for k, v in all_results.items()}
    with open(DATA_DIR / "experiment_results.json", "w", encoding="utf-8") as f:
        json.dump(save_data, f, ensure_ascii=False, indent=2)

    # Summary table
    print("=" * 75)
    print(f"{'Method':<20} {'Precision':>10} {'Recall':>10} {'F1':>10} {'Accuracy':>10} {'Latency':>12}")
    print("-" * 75)
    for name, r in all_results.items():
        avg_p = sum(r["per_class"][c]["precision"] for c in ["chat","coding","unknown"]) / 3
        avg_r = sum(r["per_class"][c]["recall"] for c in ["chat","coding","unknown"]) / 3
        print(f"{name:<20} {avg_p:>10.3f} {avg_r:>10.3f} {r['weighted_f1']:>10.3f} "
              f"{r['accuracy']:>10.3f} {r['avg_latency_ms']:>10.3f}ms")
    print("=" * 75)

    print(f"\n{'Method':<20} {'F1(chat)':>10} {'F1(coding)':>10} {'F1(unknown)':>12} {'Weighted':>10}")
    print("-" * 65)
    for name, r in all_results.items():
        pc = r["per_class"]
        print(f"{name:<20} {pc['chat']['f1']:>10.3f} {pc['coding']['f1']:>10.3f} "
              f"{pc['unknown']['f1']:>12.3f} {r['weighted_f1']:>10.3f}")

if __name__ == "__main__":
    main()
