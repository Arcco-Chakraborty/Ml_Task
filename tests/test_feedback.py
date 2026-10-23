import pytest

from app.feedback import db


def post(client, text):
    return client.post("/api/feedback", json={"text": text})


def suggestion(app, sid):
    with app.app_context():
        return next(s for s in db.list_suggestions() if s["id"] == sid)


def test_duplicate_suggestion_bumps_count(app, client, fake_pipeline):
    before = suggestion(app, "S01")["count"]
    fake_pipeline.answers["please add a night theme"] = ("suggestion", "S01")
    data = post(client, "please add a night theme").get_json()
    assert data["label"] == "suggestion"
    assert data["match"] == {"kind": "suggestion", "id": "S01", "new": False}
    assert suggestion(app, "S01")["count"] == before + 1
    assert f"{before} other people" in data["reply"]


def test_new_suggestion_is_added(app, client, fake_pipeline):
    fake_pipeline.answers["add a bird migration tracker"] = ("suggestion", None)
    data = post(client, "add a bird migration tracker").get_json()
    assert data["match"] == {"kind": "suggestion", "id": "S33", "new": True}
    s = suggestion(app, "S33")
    assert s["text"] == "add a bird migration tracker" and s["count"] == 1
    assert "added it to our suggestions board" in data["reply"]

    # the next similar message can now match the new entry
    fake_pipeline.answers["bird migration tracker pls"] = ("suggestion", "S33")
    post(client, "bird migration tracker pls")
    assert suggestion(app, "S33")["count"] == 2


def test_known_fixed_bug_tells_user_the_version(client, fake_pipeline):
    fake_pipeline.answers["fahrenheit keeps coming back"] = ("bug", "B03")
    data = post(client, "fahrenheit keeps coming back").get_json()
    assert data["match"]["id"] == "B03"
    assert "fixed in version 2.2.4" in data["reply"]


def test_known_open_bug_says_being_worked_on(client, fake_pipeline):
    fake_pipeline.answers["radar is grey"] = ("bug", "B04")
    first = post(client, "radar is grey").get_json()
    assert "working on a fix" in first["reply"]
    assert "one of 1 people" in first["reply"]
    fake_pipeline.answers["radar is blank"] = ("bug", "B04")
    assert "one of 2 people" in post(client, "radar is blank").get_json()["reply"]


def test_unknown_bug_is_logged(client, fake_pipeline):
    fake_pipeline.answers["share button does nothing"] = ("bug", None)
    data = post(client, "share button does nothing").get_json()
    assert data["label"] == "bug" and data["match"] is None
    assert "logged it" in data["reply"]


def test_query_reply(client):
    data = post(client, "how do I add a city?").get_json()
    assert data["label"] == "query"
    assert "question" in data["reply"]


def test_junk_asks_for_more_detail(client, fake_pipeline):
    fake_pipeline.answers["asdfghjkl"] = ("junk", None)
    data = post(client, "asdfghjkl").get_json()
    assert data["label"] == "junk" and data["match"] is None
    assert "tell us a bit more" in data["reply"]


@pytest.mark.parametrize("text", ["", "  ", "hi", "x" * 2001])
def test_rejects_bad_input(client, text):
    assert post(client, text).status_code == 400


def test_unimplemented_pipeline_still_accepts_feedback(app, client, monkeypatch):
    class NotYet:
        def classify(self, text):
            raise NotImplementedError("FeedbackPipeline.classify")

    app.extensions["feedback_pipeline"].pipeline = NotYet()
    data = post(client, "the radar is blank").get_json()
    assert data["label"] is None
    assert "received it" in data["reply"]
    with app.app_context():
        row = db.get_db().execute("SELECT * FROM feedback").fetchone()
    assert row["pipeline_error"].startswith("NotImplementedError")


def test_bad_pipeline_output_is_contained(app, client, fake_pipeline):
    fake_pipeline.answers["weird"] = ("suggestion", "S999")
    data = post(client, "weird").get_json()
    assert data["label"] == "suggestion" and data["match"] is None
    with app.app_context():
        assert all(s["id"] != "S999" for s in db.list_suggestions())
        row = db.get_db().execute("SELECT pipeline_error FROM feedback").fetchone()
    assert "unknown id" in row[0]


# ---------------------------------------------------------------- admin
def test_admin_requires_login(client):
    assert client.get("/api/admin/summary").status_code == 401
    assert client.get("/admin").status_code == 302
    assert client.post("/admin/login", data={"password": "nope"}).status_code == 200  # re-renders form


def test_admin_summary_and_relabel(admin, fake_pipeline):
    fake_pipeline.answers["radar is grey"] = ("bug", "B04")
    post(admin, "radar is grey")
    post(admin, "how do I add a city?")
    s = admin.get("/api/admin/summary").get_json()
    assert s["total"] == 2 and s["by_label"] == {"bug": 1, "query": 1}
    assert s["top_issues"][0]["id"] == "B04"

    items = admin.get("/api/admin/feedback?label=query").get_json()["items"]
    assert admin.patch(f"/api/admin/feedback/{items[0]['id']}", json={"label": "suggestion"}).status_code == 200
    row = admin.get("/api/admin/feedback?label=suggestion").get_json()["items"][0]
    assert row["label_source"] == "admin"
    assert admin.patch(f"/api/admin/feedback/{row['id']}", json={"label": "spam"}).status_code == 400


def test_admin_issue_status_and_promote(admin, fake_pipeline):
    assert admin.patch("/api/admin/issues/B04", json={"status": "fixed", "fixed_in": "2.4.2"}).status_code == 200
    b04 = next(i for i in admin.get("/api/admin/issues").get_json()["items"] if i["id"] == "B04")
    assert (b04["status"], b04["fixed_in"]) == ("fixed", "2.4.2")

    fake_pipeline.answers["share crashes"] = ("bug", None)
    fid = post(admin, "share crashes").get_json()["id"]
    resp = admin.post("/api/admin/issues", json={"title": "Share button crashes", "feedback_id": fid})
    assert resp.status_code == 201 and resp.get_json()["id"] == "B25"
    assert admin.get("/api/admin/feedback?label=bug&unmatched=1").get_json()["items"] == []


def test_admin_export_csv(admin):
    post(admin, "how do I add a city?")
    resp = admin.get("/api/admin/feedback.csv")
    assert resp.mimetype == "text/csv"
    assert "how do I add a city?" in resp.get_data(as_text=True)


def test_admin_model_tab(admin):
    data = admin.get("/api/admin/model").get_json()
    assert data["status"] == "ready" and data["metrics"] is None


def test_pages_render(client, admin):
    assert client.get("/").status_code == 200
    assert client.get("/feedback").status_code == 200
    assert admin.get("/admin").status_code == 200
