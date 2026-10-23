import os
from pathlib import Path

from flask import Flask, render_template

from .version import APP_VERSION

ROOT = Path(__file__).resolve().parent.parent


def create_app(config=None):
    app = Flask(__name__, instance_path=str(ROOT / "instance"))
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-secret-change-me"),
        ADMIN_PASSWORD=os.environ.get("ADMIN_PASSWORD", "admin"),
        DATABASE=str(ROOT / "instance" / "feedback.db"),
        DATA_DIR=str(ROOT / "data"),
        ML_ARTIFACTS=str(ROOT / "ml" / "artifacts"),
        HTTP_TIMEOUT=8,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if config:
        app.config.update(config)
    os.makedirs(app.instance_path, exist_ok=True)

    from .feedback import db
    from .feedback.pipeline_loader import init_pipeline
    from .feedback.routes import bp as feedback_bp
    from .weather.routes import bp as weather_bp

    db.init_app(app)
    init_pipeline(app)
    app.register_blueprint(weather_bp)
    app.register_blueprint(feedback_bp)

    @app.context_processor
    def inject_version():
        return {"app_version": APP_VERSION}

    @app.get("/")
    def index():
        return render_template("index.html")

    return app
