"""Checks that YOUR FeedbackPipeline keeps to the contract the app relies on.

These are skipped until ml/pipeline.py is implemented.
"""
import pytest

from ml.data import load_issues, load_suggestions, load_train
from ml.pipeline import LABELS, FeedbackPipeline


@pytest.fixture(scope="module")
def trained():
    pipe = FeedbackPipeline()
    try:
        pipe.train(load_train())
    except NotImplementedError:
        pytest.skip("FeedbackPipeline.train is not implemented yet")
    return pipe


SAMPLES = [
    "How do I change the units to Fahrenheit?",
    "Please add a dark mode",
    "The radar map is completely blank",
    "",
    "🌧️🌧️🌧️",
]


@pytest.mark.parametrize("text", SAMPLES)
def test_classify_returns_a_label(trained, text):
    assert trained.classify(text) in LABELS


def test_match_suggestion_returns_known_id_or_none(trained):
    suggestions = load_suggestions()
    ids = {s["id"] for s in suggestions}
    for text in SAMPLES:
        assert trained.match_suggestion(text, suggestions) in ids | {None}


def test_match_issue_returns_known_id_or_none(trained):
    issues = load_issues()
    ids = {i["id"] for i in issues}
    for text in SAMPLES:
        assert trained.match_issue(text, issues) in ids | {None}


def test_matching_uses_the_list_it_is_given(trained):
    # new entries appear at runtime; ids must come from the list passed in
    custom = [{"id": "S77", "text": "Add a bird migration tracker", "count": 1}]
    assert trained.match_suggestion("Add a bird migration tracker", custom) in {"S77", None}
    assert trained.match_suggestion("anything", []) is None


def test_save_load_roundtrip(trained, tmp_path):
    trained.save(tmp_path)
    loaded = FeedbackPipeline.load(tmp_path)
    for text in SAMPLES:
        assert loaded.classify(text) == trained.classify(text)
