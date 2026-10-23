"""
=====================================================================
  YOUR CODE GOES HERE.  This is the only file you *have* to edit.
=====================================================================

The web app (feedback page + admin dashboard), `ml/train.py`,
`scripts/evaluate.py` and the organisers' hidden-test runner all talk to
your model through this one class. Keep the method names and signatures
exactly as they are; everything inside them is up to you. You can add
helper modules under `ml/`, extra methods, and extra dependencies
(add them to requirements.txt).

How the app uses it, for every message a user submits:

    label = pipeline.classify(text)                  # "query" | "suggestion" | "bug" | "junk"
    if label == "suggestion":
        sid = pipeline.match_suggestion(text, suggestions)
        # sid is an id from `suggestions`  -> that suggestion's count += 1
        # sid is None                      -> the message is added as a NEW suggestion
    elif label == "bug":
        bid = pipeline.match_issue(text, issues)
        # bid is an id from `issues`       -> user is told "fixed in vX" / "being worked on"
        # bid is None                      -> logged as a new, unknown bug
    # "query" and "junk" need no matching ("junk" = nothing to act on: keyboard mash,
    # "test", bare greetings, spam, off-topic, praise with no content)

`suggestions` and `issues` are passed in on every call because they change
while the app runs: new suggestions get added, issue statuses change.
Never hard-code ids. Match against whatever list you are given.

    suggestions: [{"id": "S01", "text": "Add a dark mode / night theme", "count": 41}, ...]
    issues:      [{"id": "B04", "title": "Radar map is blank / shows only grey tiles",
                   "status": "open", "fixed_in": None, "component": "web-frontend"}, ...]

Rules: train your own model. No calling ChatGPT, Gemini or any other
hosted LLM to classify or match. Pre-trained embedding models you run
locally (e.g. sentence-transformers) are fine for the similarity part.
"""
from __future__ import annotations

import pickle
from pathlib import Path

import pandas as pd

LABELS = ("query", "suggestion", "bug", "junk")


class FeedbackPipeline:
    def __init__(self):
        # Put your vectoriser / model / thresholds here.
        pass

    # ------------------------------------------------------------------ training
    def train(self, df: pd.DataFrame) -> None:
        """Fit everything you need.

        df columns:
            id            "TR0001", ...
            text          the raw user message
            label         "query" | "suggestion" | "bug" | "junk"
            duplicate_of  "S07" / "B12" if the message is a duplicate of a list
                          entry, "" otherwise. Useful for tuning your matcher.

        `ml.data.load_suggestions()` / `ml.data.load_issues()` give you the
        starting lists if you want them at training time.
        """
        raise NotImplementedError("FeedbackPipeline.train")

    # ------------------------------------------------------------------ inference
    def classify(self, text: str) -> str:
        """Return one of LABELS."""
        raise NotImplementedError("FeedbackPipeline.classify")

    def match_suggestion(self, text: str, suggestions: list[dict]) -> str | None:
        """Return the id of the suggestion this message duplicates, or None if it's new."""
        raise NotImplementedError("FeedbackPipeline.match_suggestion")

    def match_issue(self, text: str, issues: list[dict]) -> str | None:
        """Return the id of the known issue this bug report matches, or None."""
        raise NotImplementedError("FeedbackPipeline.match_issue")

    # Optional: implement this and the admin dashboard will show model confidence.
    # def predict_proba(self, text: str) -> dict[str, float]:
    #     return {"query": 0.1, "suggestion": 0.7, "bug": 0.2}

    # ------------------------------------------------------------------ persistence
    # The default pickles the whole object. Override if you need something else
    # (e.g. an embedding model that should be re-loaded rather than pickled).
    def save(self, directory: str | Path) -> None:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        with open(directory / "pipeline.pkl", "wb") as f:
            pickle.dump(self, f)

    @classmethod
    def load(cls, directory: str | Path) -> "FeedbackPipeline":
        with open(Path(directory) / "pipeline.pkl", "rb") as f:
            return pickle.load(f)
