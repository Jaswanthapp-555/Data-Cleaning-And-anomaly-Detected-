"""Flask application factory."""
import os
from flask import Flask, send_from_directory
from flask_cors import CORS
from .routes import upload, analysis, cleaning, visualization, comparison, reports


def create_app():
    app = Flask(
        __name__,
        static_folder=os.path.join(os.path.dirname(__file__), "..", "frontend"),
        static_url_path="/static",
    )
    app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(24).hex())
    app.config["UPLOAD_FOLDER"] = os.path.join(os.path.dirname(__file__), "..", "uploads")
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    CORS(app)

    # Register blueprints
    app.register_blueprint(upload.bp)
    app.register_blueprint(analysis.bp)
    app.register_blueprint(cleaning.bp)
    app.register_blueprint(visualization.bp)
    app.register_blueprint(comparison.bp)
    app.register_blueprint(reports.bp)

    @app.route("/")
    def index():
        return send_from_directory(
            os.path.join(os.path.dirname(__file__), "..", "frontend"),
            "index.html",
        )

    @app.errorhandler(413)
    def too_large(e):
        return {"error": "File too large. Maximum size is 100 MB."}, 413

    @app.after_request
    def add_no_cache_headers(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=5000, debug=True)


