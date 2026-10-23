"""Stateful simulation + scoring. Used by scripts/evaluate.py.

It mirrors what the app does, and how the hidden test is run:
messages are processed in order, and a suggestion that matches nothing is
added to the list *with the message's id as its id*, so later messages can
match it.
"""
from __future__ import annotations

import copy
from collections import Counter

LABELS = ("query", "suggestion", "bug", "junk")


def simulate(pipeline, messages, suggestions, issues):
    """messages: iterable of (id, text). Returns list of {id, label, duplicate_of}."""
    suggestions = copy.deepcopy(suggestions)
    issues = copy.deepcopy(issues)
    out = []
    for mid, text in messages:
        label = pipeline.classify(text)
        dup = None
        if label == "suggestion":
            dup = pipeline.match_suggestion(text, suggestions)
            hit = next((s for s in suggestions if s["id"] == dup), None)
            if hit:
                hit["count"] += 1
            else:
                dup = None
                suggestions.append({"id": mid, "text": text, "count": 1})
        elif label == "bug":
            dup = pipeline.match_issue(text, issues)
            if dup not in {i["id"] for i in issues}:
                dup = None
        out.append({"id": mid, "label": label, "duplicate_of": dup or ""})
    return out


def score(gold, preds):
    """gold: list of {id, text, label, duplicate_of}; preds: output of simulate()."""
    pred = {p["id"]: p for p in preds}
    cm = Counter((g["label"], pred[g["id"]]["label"]) for g in gold)
    n = len(gold)
    accuracy = sum(cm[(l, l)] for l in LABELS) / n

    f1 = {}
    for l in LABELS:
        tp = cm[(l, l)]
        fp = sum(cm[(o, l)] for o in LABELS if o != l)
        fn = sum(v for (g, p), v in cm.items() if g == l and p != l)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1[l] = 2 * prec * rec / (prec + rec) if prec + rec else 0.0

    hits, rejects, errors = [], [], []
    for g in gold:
        p = pred[g["id"]]
        if p["label"] != g["label"]:
            errors.append({"id": g["id"], "text": g["text"], "kind": "label",
                           "gold": g["label"], "pred": p["label"]})
        if g["label"] in ("query", "junk"):
            continue
        ok = p["duplicate_of"] == g["duplicate_of"]
        (hits if g["duplicate_of"] else rejects).append(ok)
        if not ok:
            errors.append({"id": g["id"], "text": g["text"], "kind": "duplicate",
                           "gold": g["duplicate_of"] or "(new)", "pred": p["duplicate_of"] or "(new)"})

    def rate(xs):
        return sum(xs) / len(xs) if xs else None

    return {
        "n": n,
        "accuracy": accuracy,
        "macro_f1": sum(f1.values()) / len(LABELS),
        "f1": f1,
        "labels": list(LABELS),
        "confusion_matrix": [[cm[(g, p)] for p in LABELS] for g in LABELS],
        "duplicate_hit_rate": rate(hits),
        "duplicate_reject_rate": rate(rejects),
        "duplicate_accuracy": rate(hits + rejects),
        "n_duplicates": len(hits),
        "n_non_duplicates": len(rejects),
        "errors": errors,
    }


def format_report(m):
    lines = [
        f"messages evaluated: {m['n']}",
        f"label accuracy:     {m['accuracy']:.3f}",
        f"macro F1:           {m['macro_f1']:.3f}   "
        + "  ".join(f"{l}={m['f1'][l]:.2f}" for l in m["labels"]),
        "",
        "confusion matrix (rows = true, cols = predicted)",
        " " * 12 + "".join(f"{l:>12}" for l in m["labels"]),
    ]
    for l, row in zip(m["labels"], m["confusion_matrix"]):
        lines.append(f"{l:<12}" + "".join(f"{v:>12}" for v in row))

    def pct(x):
        return "n/a" if x is None else f"{x:.3f}"

    lines += [
        "",
        f"duplicate hit rate:    {pct(m['duplicate_hit_rate'])}  (n={m['n_duplicates']}, right id for real duplicates)",
        f"duplicate reject rate: {pct(m['duplicate_reject_rate'])}  (n={m['n_non_duplicates']}, left new things as new)",
        f"duplicate accuracy:    {pct(m['duplicate_accuracy'])}",
    ]
    return "\n".join(lines)
