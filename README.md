# Cirrus Weather: SUTT AI/ML Task

Cirrus is a small weather web app: search, current conditions, 24-hour chart,
7-day forecast and rain radar. Users send it feedback through a single text
box: questions, suggestions and bug reports, all mixed together.

**The app, the feedback page, the database, the reply templates and the admin
dashboard are already built.** What's missing is the brain: the model that
decides what each message *is*, and whether we've heard it before.

**Your job is `ml/pipeline.py`.**

---

## The task (round 1)

For every message a user submits, your pipeline must:

1. **Classify** it as `query`, `suggestion`, `bug` or `junk` (nothing to act on: keyboard mash, "test", spam, chit-chat).
   Train your own model on `data/train.csv` (1,126 labelled messages; real-looking, messy, with a few wrong labels).
2. **Check for duplicates:**
   - *Suggestion*: is it already on the suggestions board? If yes, the app bumps that entry's count; if no, the app adds it.
   - *Bug*: is it a known issue? If yes, the app tells the user whether it's **fixed** (and in which version) or **being worked on**.

The app then picks a reply template from your answer. Everything else
(storage, counts, replies, dashboard) already works.

| Level | What |
|---|---|
| **Basic** | Trained classifier, so the app files and replies to every message |
| **Good** | Duplicate detection for suggestions and known issues (TF-IDF or embeddings + cosine similarity is enough) |
| **Bonus** | A better model; error analysis using the confusion matrix (`scripts/evaluate.py` produces it; the dashboard's **Model** tab shows it); anything else that makes the system smarter |

**Rules**
- Don't call ChatGPT, Gemini or any other hosted LLM to classify or match. Train your own model (scikit-learn is enough for Basic).
  Pre-trained models that run locally are fine: `sentence-transformers` embeddings, or fine-tuning a small transformer.
- Using AI to help write code is fine, but you must be able to explain all of it in the viva.

**Evaluation.** We run a hidden set of about 360 new messages through *your* `FeedbackPipeline`,
one at a time and in order, exactly like the app does. We score:
- label accuracy and macro-F1
- duplicate detection: right id for real duplicates, *and* new things left as new (there are near-miss traps)

**Submit:** your repo (with `ml/pipeline.py` implemented and the trained model in `ml/artifacts/`), a short
`REPORT.md` (what you tried, what worked, what didn't, and why), and a short demo video.

---

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python run.py                      # http://127.0.0.1:5000
```

| Page | URL |
|---|---|
| Weather app | http://127.0.0.1:5000/ |
| Feedback page | http://127.0.0.1:5000/feedback |
| Admin dashboard | http://127.0.0.1:5000/admin (password `admin`, override with `ADMIN_PASSWORD`) |

Before you implement anything, feedback is stored but marked *unclassified*, and the
dashboard shows a banner saying no model is loaded. That's expected.

## Your workflow

```bash
# 1. implement FeedbackPipeline in ml/pipeline.py

# 2. evaluate on a held-out 20% of train.csv (prints accuracy, confusion matrix,
#    duplicate scores and your mistakes; also feeds the dashboard's Model tab)
python -m scripts.evaluate

# 3. check you kept to the contract the app relies on
pytest tests/test_pipeline_contract.py

# 4. train on all the data and save to ml/artifacts/
python -m ml.train

# 5. run the app (or press "Reload model" in the dashboard) and try it out
python run.py
```

## The contract

```python
class FeedbackPipeline:
    def train(self, df: pd.DataFrame) -> None: ...          # columns: id, text, label, duplicate_of
    def classify(self, text: str) -> str: ...               # "query" | "suggestion" | "bug" | "junk"
    def match_suggestion(self, text, suggestions) -> str | None: ...  # an id from `suggestions`, or None
    def match_issue(self, text, issues) -> str | None: ...            # an id from `issues`, or None
    def save(self, directory) / load(cls, directory)        # default: pickle; override if needed
    # optional: predict_proba(text) -> {label: prob}         # shown as confidence in the dashboard
```

The docstrings in [`ml/pipeline.py`](ml/pipeline.py) have the details. The lists
are passed in on **every call** because they change at runtime: new
suggestions get added, and issues get fixed. Match against what you're given.

## The data

See [`data/LABELING_GUIDE.md`](data/LABELING_GUIDE.md): the label definitions, the rules for the tricky
cases (users rarely phrase things the way the label says), and what counts as a duplicate. **Read it.**
The hidden test is messier than the training data and full of messages whose wording points the wrong way,
plus typos, Hinglish, half-sentences and outright gibberish, so a model that only learns keywords like
"add", "crash" or "how" won't do well.

| File | |
|---|---|
| `data/train.csv` | 1,126 messages (319 query / 333 suggestion / 397 bug / 77 junk); 392 are annotated duplicates of a list entry |
| `data/suggestions.json` | 32 suggestions with vote counts |
| `data/known_issues.json` | 24 known issues: 11 fixed (with version), 13 open |

## Repo map

```
app/                  Flask app (you shouldn't need to touch this)
  weather/            weather API: Open-Meteo forecast + air quality, geocoding, reverse geocoding
  feedback/           feedback flow, SQLite store, reply templates, admin API
  templates/ static/  pages, CSS, JS
ml/
  pipeline.py         ← YOUR CODE
  train.py            trains on all of train.csv, saves to ml/artifacts/
  harness.py          stateful simulation + scoring used by scripts/evaluate.py
  data.py             dataset loaders
  artifacts/          your saved model (+ metrics.json from evaluate)
scripts/evaluate.py   held-out evaluation, confusion matrix, error list
data/                 dataset + labelling guide
tests/                app tests + your pipeline's contract tests
```

Useful extras:
- `flask --app run reset-db` wipes all feedback and re-seeds the suggestions and issues lists.
- The dashboard's **Inbox** lets you correct labels, and **Export CSV** downloads them, in case you want to collect more training data.
- `pytest` runs everything. The app tests use recorded API responses, so they work offline.

## Round 2 (coming later)

In round 2 you'll extend this into an agent that takes the bug reports your pipeline
collects and tries to **fix them in this codebase** and open pull requests. Keep that in
mind: a pipeline that groups bug reports reliably makes round 2 much easier.

---

Weather data: [Open-Meteo](https://open-meteo.com) · Radar: [RainViewer](https://www.rainviewer.com) ·
Maps & reverse geocoding: © [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors.
