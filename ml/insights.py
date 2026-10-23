"""
OPTIONAL (brownie points): insights on what users are asking for.

The admin dashboard's Insights tab calls `generate_insights` when an admin presses
"Generate". This is the ONE place an LLM may be used (hosted or local): summarise
the suggestions and questions, spot themes, say what users want most. Classifying
and matching must still be done by your own model in ml/pipeline.py.

Leave it raising NotImplementedError if you're not doing this part; the tab then
just explains how to enable it.

Keep API keys out of the repo: read them from an environment variable
(e.g. os.environ["OPENAI_API_KEY"]) and add any client library to requirements.txt.
"""
from __future__ import annotations


def generate_insights(suggestions: list[dict], queries: list[str]) -> str:
    """Return a short report as Markdown (headings, bullet lists, bold are rendered).

    suggestions: the board right now, most-voted first
                 [{"id": "S01", "text": "Add a dark mode / night theme", "count": 41, "source": "seed"}, ...]
                 source is "seed" (original list) or "user" (added by your pipeline at runtime)
    queries:     the most recent messages your pipeline labelled "query", newest first (up to 200)
    """
    raise NotImplementedError("ml/insights.py: generate_insights")
