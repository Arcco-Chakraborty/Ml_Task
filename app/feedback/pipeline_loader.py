"""Loads the participant's FeedbackPipeline (ml/pipeline.py) for the app.

status:
  ready      - trained artifacts loaded from ml/artifacts/
  untrained  - no artifacts yet; an untrained FeedbackPipeline() is used
               (calls will usually raise NotImplementedError until you build it)
  error      - importing or loading failed; see `detail`
"""
import importlib
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone

from flask import current_app


@dataclass
class PipelineHandle:
    status: str
    pipeline: object = None
    detail: str = ""
    loaded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))


def load_handle(artifacts_dir):
    try:
        module = importlib.reload(importlib.import_module("ml.pipeline"))
    except Exception:
        return PipelineHandle("error", detail=traceback.format_exc())
    cls = module.FeedbackPipeline
    try:
        return PipelineHandle("ready", cls.load(artifacts_dir), detail=f"loaded from {artifacts_dir}")
    except FileNotFoundError:
        try:
            return PipelineHandle("untrained", cls(), detail="no trained artifacts found; run `python -m ml.train`")
        except Exception:
            return PipelineHandle("error", detail=traceback.format_exc())
    except Exception:
        return PipelineHandle("error", detail=traceback.format_exc())


def init_pipeline(app):
    injected = app.config.get("PIPELINE")  # tests can inject a ready-made object
    if injected is not None:
        app.extensions["feedback_pipeline"] = PipelineHandle("ready", injected, detail="injected")
    else:
        app.extensions["feedback_pipeline"] = load_handle(app.config["ML_ARTIFACTS"])


def get_handle():
    return current_app.extensions["feedback_pipeline"]


def reload_pipeline():
    init_pipeline(current_app)
    return get_handle()
