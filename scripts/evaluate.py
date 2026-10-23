"""Evaluate your pipeline on a held-out part of the training data.

    python -m scripts.evaluate                 # 80/20 stratified split
    python -m scripts.evaluate --test-size 0.3 --seed 7
    python -m scripts.evaluate --errors 30     # print more mistakes

Trains a FRESH FeedbackPipeline on the training part, runs the held-out part
through the same stateful flow as the app, prints accuracy, confusion matrix
and duplicate-detection scores, and writes ml/artifacts/metrics.json (shown
in the admin dashboard's Model tab).

This does not touch the model the app uses; run `python -m ml.train` for that.
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from sklearn.model_selection import train_test_split

from ml.data import load_issues, load_suggestions, load_train
from ml.harness import format_report, score, simulate
from ml.pipeline import LABELS, FeedbackPipeline

ARTIFACTS = Path(__file__).resolve().parent.parent / "ml" / "artifacts"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test-size", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--errors", type=int, default=15, help="how many mistakes to print")
    args = ap.parse_args()

    df = load_train()
    unknown = sorted(set(df["label"]) - set(LABELS))
    if unknown:
        raise SystemExit(
            f"data/train.csv has label spellings that aren't one of {LABELS}: {unknown[:8]}"
            f"{' ...' if len(unknown) > 8 else ''}\n"
            "The file is a raw export. Clean the labels where the data is loaded (ml/data.py load_train(), "
            "which train.py and this script both use), then run this again.")
    train_df, eval_df = train_test_split(df, test_size=args.test_size, random_state=args.seed,
                                         stratify=df["label"])
    eval_df = eval_df.sort_values("id")

    pipeline = FeedbackPipeline()
    pipeline.train(train_df.reset_index(drop=True))
    preds = simulate(pipeline, zip(eval_df["id"], eval_df["text"]), load_suggestions(), load_issues())
    metrics = score(eval_df.to_dict("records"), preds)

    print(format_report(metrics))
    if metrics["errors"] and args.errors:
        print(f"\nsome mistakes ({min(args.errors, len(metrics['errors']))} of {len(metrics['errors'])}):")
        for e in metrics["errors"][: args.errors]:
            print(f"  [{e['kind']:<9}] gold={e['gold']:<10} pred={e['pred']:<10} {e['text']}")

    metrics.update({
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_train": len(train_df),
        "test_size": args.test_size,
        "seed": args.seed,
    })
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(f"\nwrote {ARTIFACTS / 'metrics.json'}")


if __name__ == "__main__":
    main()
