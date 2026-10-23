import csv
import importlib
import io
import json
import traceback
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path

from flask import (Blueprint, Response, current_app, jsonify, redirect, render_template, request,
                   session, url_for)

from ml.pipeline import LABELS

from . import db
from .pipeline_loader import get_handle, reload_pipeline
from .service import process_feedback

bp = Blueprint("feedback", __name__)

MAX_LEN = 2000


# ---------------------------------------------------------------- public
@bp.get("/feedback")
def feedback_page():
    return render_template("feedback.html")


@bp.post("/api/feedback")
def submit_feedback():
    text = ((request.get_json(silent=True) or {}).get("text") or "").strip()
    if len(text) < 3:
        return jsonify(error="Please write a little more so we can help."), 400
    if len(text) > MAX_LEN:
        return jsonify(error=f"Please keep it under {MAX_LEN} characters."), 400
    return jsonify(process_feedback(text))


# ---------------------------------------------------------------- admin auth
def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            if request.path.startswith("/api/"):
                return jsonify(error="login required"), 401
            return redirect(url_for("feedback.admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


@bp.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    error = None
    if request.method == "POST":
        if request.form.get("password") == current_app.config["ADMIN_PASSWORD"]:
            session["admin"] = True
            return redirect(url_for("feedback.admin_page"))
        error = "Wrong password"
    return render_template("admin_login.html", error=error,
                           default_password=current_app.config["ADMIN_PASSWORD"] == "admin")


@bp.post("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("feedback.admin_login"))


@bp.get("/admin")
@admin_required
def admin_page():
    return render_template("admin.html")


# ---------------------------------------------------------------- admin API
@bp.get("/api/admin/summary")
@admin_required
def summary():
    conn = db.get_db()
    by_label = {r["label"] or "unclassified": r["n"] for r in conn.execute(
        "SELECT label, COUNT(*) AS n FROM feedback GROUP BY label")}
    return jsonify(
        total=sum(by_label.values()),
        by_label=by_label,
        errors=conn.execute("SELECT COUNT(*) FROM feedback WHERE pipeline_error IS NOT NULL").fetchone()[0],
        new_suggestions=conn.execute("SELECT COUNT(*) FROM suggestions WHERE source = 'user'").fetchone()[0],
        unmatched_bugs=conn.execute(
            "SELECT COUNT(*) FROM feedback WHERE label = 'bug' AND match_id IS NULL").fetchone()[0],
        open_issues=conn.execute("SELECT COUNT(*) FROM issues WHERE status = 'open'").fetchone()[0],
        top_suggestions=[dict(r) for r in conn.execute(
            "SELECT id, text, count FROM suggestions ORDER BY count DESC, id LIMIT 5")],
        top_issues=[dict(r) for r in conn.execute(
            """SELECT i.id, i.title, i.status, COUNT(f.id) AS reports FROM issues i
               JOIN feedback f ON f.match_kind = 'issue' AND f.match_id = i.id
               GROUP BY i.id ORDER BY reports DESC LIMIT 5""")],
        pipeline_status=get_handle().status,
    )


@bp.get("/api/admin/feedback")
@admin_required
def list_feedback():
    sql = "SELECT * FROM feedback WHERE 1=1"
    args = []
    label = request.args.get("label")
    if label == "unclassified":
        sql += " AND label IS NULL"
    elif label:
        sql += " AND label = ?"
        args.append(label)
    if request.args.get("unmatched") == "1":
        sql += " AND match_id IS NULL"
    if q := request.args.get("q"):
        sql += " AND text LIKE ?"
        args.append(f"%{q}%")
    sql += " ORDER BY id DESC LIMIT ?"
    args.append(min(int(request.args.get("limit", 200)), 1000))
    return jsonify(items=[dict(r) for r in db.get_db().execute(sql, args)])


@bp.patch("/api/admin/feedback/<int:fid>")
@admin_required
def relabel(fid):
    label = (request.get_json(silent=True) or {}).get("label")
    if label not in LABELS:
        return jsonify(error=f"label must be one of {LABELS}"), 400
    conn = db.get_db()
    conn.execute("UPDATE feedback SET label = ?, label_source = 'admin' WHERE id = ?", (label, fid))
    conn.commit()
    return jsonify(ok=True)


@bp.get("/api/admin/feedback.csv")
@admin_required
def export_feedback():
    rows = db.get_db().execute(
        "SELECT id, text, label, label_source, match_kind, match_id, created_at FROM feedback ORDER BY id")
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "text", "label", "label_source", "match_kind", "match_id", "created_at"])
    w.writerows(tuple(r) for r in rows)
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=feedback.csv"})


@bp.get("/api/admin/suggestions")
@admin_required
def suggestions():
    rows = db.get_db().execute("SELECT * FROM suggestions ORDER BY count DESC, id")
    return jsonify(items=[dict(r) for r in rows])


@bp.get("/api/admin/issues")
@admin_required
def issues():
    rows = db.get_db().execute(
        """SELECT i.*, COUNT(f.id) AS reports FROM issues i
           LEFT JOIN feedback f ON f.match_kind = 'issue' AND f.match_id = i.id
           GROUP BY i.id ORDER BY i.id""")
    return jsonify(items=[dict(r) for r in rows])


@bp.post("/api/admin/issues")
@admin_required
def create_issue():
    """Promote an unmatched bug report to a known issue."""
    body = request.get_json(silent=True) or {}
    title = (body.get("title") or "").strip()
    if not title:
        return jsonify(error="title is required"), 400
    conn = db.get_db()
    iid = db.next_id("issues", "B")
    conn.execute("INSERT INTO issues VALUES (?, ?, 'open', NULL, ?, 'admin', ?)",
                 (iid, title, body.get("component") or None, db.now()))
    if fid := body.get("feedback_id"):
        conn.execute("UPDATE feedback SET match_kind = 'issue', match_id = ? WHERE id = ?", (iid, fid))
    conn.commit()
    return jsonify(id=iid), 201


@bp.patch("/api/admin/issues/<iid>")
@admin_required
def update_issue(iid):
    body = request.get_json(silent=True) or {}
    status = body.get("status")
    if status not in ("open", "fixed"):
        return jsonify(error="status must be open or fixed"), 400
    fixed_in = ((body.get("fixed_in") or "").strip() or None) if status == "fixed" else None
    conn = db.get_db()
    conn.execute("UPDATE issues SET status = ?, fixed_in = ? WHERE id = ?", (status, fixed_in, iid))
    conn.commit()
    return jsonify(ok=True)


@bp.get("/api/admin/model")
@admin_required
def model_status():
    handle = get_handle()
    metrics_path = Path(current_app.config["ML_ARTIFACTS"]) / "metrics.json"
    metrics = json.loads(metrics_path.read_text()) if metrics_path.exists() else None
    return jsonify(status=handle.status, detail=handle.detail, loaded_at=handle.loaded_at,
                   has_proba=hasattr(handle.pipeline, "predict_proba"), metrics=metrics)


@bp.post("/api/admin/model/reload")
@admin_required
def model_reload():
    handle = reload_pipeline()
    return jsonify(status=handle.status, detail=handle.detail)


# ---------------------------------------------------------------- insights (optional, ml/insights.py)
@bp.get("/api/admin/insights")
@admin_required
def insights():
    return jsonify(current_app.extensions.get("insights") or {"status": "not_generated"})


@bp.post("/api/admin/insights")
@admin_required
def generate_insights():
    conn = db.get_db()
    suggestions = [dict(r) for r in conn.execute(
        "SELECT id, text, count, source FROM suggestions ORDER BY count DESC, id")]
    queries = [r[0] for r in conn.execute(
        "SELECT text FROM feedback WHERE label = 'query' ORDER BY id DESC LIMIT 200")]
    result = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "n_suggestions": len(suggestions), "n_queries": len(queries)}
    try:
        module = importlib.reload(importlib.import_module("ml.insights"))
        text = module.generate_insights(suggestions, queries)
        if not isinstance(text, str):
            raise TypeError(f"generate_insights() returned {type(text).__name__}, expected str")
        result.update(status="ready", markdown=text)
    except NotImplementedError:
        result.update(status="not_implemented")
    except Exception:
        result.update(status="error", error=traceback.format_exc(limit=3))
    current_app.extensions["insights"] = result
    return jsonify(result)
