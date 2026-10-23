"""The feedback flow: classify -> duplicate check -> update lists -> reply -> store."""
from ml.pipeline import LABELS

from . import db
from .pipeline_loader import get_handle
from .replies import build_reply


def _confidence(pipeline, text, label):
    if not hasattr(pipeline, "predict_proba"):
        return None
    try:
        return float(pipeline.predict_proba(text).get(label))
    except Exception:
        return None


def process_feedback(text):
    conn = db.get_db()
    handle = get_handle()
    pipeline = handle.pipeline
    label = confidence = match_kind = match_id = error = None
    created_new = False
    suggestion = issue = None
    report_count = 0

    try:
        if pipeline is None:
            raise RuntimeError(f"pipeline unavailable ({handle.status})")
        label = pipeline.classify(text)
        if label not in LABELS:
            raise ValueError(f"classify() returned {label!r}, expected one of {LABELS}")
        confidence = _confidence(pipeline, text, label)

        if label == "suggestion":
            suggestions = db.list_suggestions()
            sid = pipeline.match_suggestion(text, suggestions)
            by_id = {s["id"]: s for s in suggestions}
            if sid is not None and sid not in by_id:
                raise ValueError(f"match_suggestion() returned unknown id {sid!r}")
            match_kind = "suggestion"
            if sid is None:
                match_id = db.next_id("suggestions", "S")
                created_new = True
                conn.execute("INSERT INTO suggestions VALUES (?, ?, 1, 'user', ?)", (match_id, text, db.now()))
                suggestion = {"id": match_id, "text": text, "count": 1}
            else:
                match_id = sid
                conn.execute("UPDATE suggestions SET count = count + 1 WHERE id = ?", (sid,))
                suggestion = {**by_id[sid], "count": by_id[sid]["count"] + 1}

        elif label == "bug":
            issues = db.list_issues()
            bid = pipeline.match_issue(text, issues)
            by_id = {i["id"]: i for i in issues}
            if bid is not None and bid not in by_id:
                raise ValueError(f"match_issue() returned unknown id {bid!r}")
            if bid is not None:
                match_kind, match_id, issue = "issue", bid, by_id[bid]
                report_count = 1 + conn.execute(
                    "SELECT COUNT(*) FROM feedback WHERE match_kind = 'issue' AND match_id = ?", (bid,)
                ).fetchone()[0]
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        # keep a valid label if we got one, but don't half-apply a match
        if label not in LABELS:
            label = None
        if match_id is None:
            match_kind = None

    reply = build_reply(label, suggestion=suggestion, created_new=created_new,
                        issue=issue, report_count=report_count)
    cur = conn.execute(
        """INSERT INTO feedback (text, created_at, label, label_source, confidence, match_kind,
                                 match_id, created_new, reply, pipeline_error)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (text, db.now(), label, "model" if label else None, confidence, match_kind, match_id,
         int(created_new), reply, error),
    )
    conn.commit()
    return {
        "id": cur.lastrowid,
        "reply": reply,
        "label": label,
        "match": {"kind": match_kind, "id": match_id, "new": created_new} if match_id else None,
    }
