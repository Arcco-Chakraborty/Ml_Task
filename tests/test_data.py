"""Sanity checks on the provided dataset (raw, as exported: not cleaned)."""
from ml.data import load_issues, load_suggestions, load_train


def test_train_set():
    df = load_train()
    assert len(df) >= 450
    assert (df["label"].str.strip() != "").all()
    assert df["id"].is_unique and df["text"].is_unique


def test_duplicate_annotations_point_at_real_entries():
    df = load_train()
    ids = {s["id"] for s in load_suggestions()} | {b["id"] for b in load_issues()}
    assert set(df.loc[df["duplicate_of"] != "", "duplicate_of"]) <= ids


def test_issue_fields():
    for i in load_issues():
        assert i["status"] in ("open", "fixed")
        assert (i["fixed_in"] is not None) == (i["status"] == "fixed")
