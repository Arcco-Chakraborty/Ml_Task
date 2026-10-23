"""Train on the full training set and save to ml/artifacts/ (the app loads it from there).

    python -m ml.train
"""
from pathlib import Path

from ml.data import load_train
from ml.pipeline import FeedbackPipeline

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"


def main():
    df = load_train()
    pipeline = FeedbackPipeline()
    pipeline.train(df)
    pipeline.save(ARTIFACTS)
    print(f"trained on {len(df)} messages -> {ARTIFACTS}")
    print("restart the app (or press 'Reload model' in the admin dashboard) to use it")


if __name__ == "__main__":
    main()
