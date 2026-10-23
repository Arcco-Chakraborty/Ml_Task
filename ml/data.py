"""Helpers for loading the provided dataset."""
import json
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_train() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "train.csv", keep_default_na=False)


def load_suggestions() -> list[dict]:
    return json.loads((DATA_DIR / "suggestions.json").read_text(encoding="utf-8"))


def load_issues() -> list[dict]:
    return json.loads((DATA_DIR / "known_issues.json").read_text(encoding="utf-8"))
