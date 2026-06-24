import logging
import os
from flask import Flask, jsonify, render_template
from flask_cors import CORS
from flask_login import LoginManager, login_required
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config

# ── logging ──────────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    handlers=[
        logging.FileHandler("logs/rcai.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    CORS(app, origins=Config.CORS_ORIGINS, supports_credentials=True)

    # ── init DB ──────────────────────────────────────────────────────────────
    from database.connection import init_db
    with app.app_context():
        try:
            init_db()
            logger.info("DB ready.")
        except Exception as e:
            logger.error(f"DB init failed: {e}")

    # ── auth ─────────────────────────────────────────────────────────────────
    login_manager = LoginManager()
    login_manager.login_view = "auth.login_page"
    login_manager.init_app(app)

    from services.auth_service import get_user_by_id

    @login_manager.user_loader
    def load_user(user_id):
        return get_user_by_id(user_id)

    # ── rate limiting (protects /login + /signup from brute force) ──────────
    limiter = Limiter(get_remote_address, app=app, default_limits=[])
    app.extensions["limiter"] = limiter

    # ── blueprints ───────────────────────────────────────────────────────────
    from routes.auth       import bp as auth_bp
    from routes.incidents  import bp as incidents_bp
    from routes.analytics  import bp as analytics_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(incidents_bp)
    app.register_blueprint(analytics_bp)

    limiter.limit("10 per minute")(auth_bp)

    # ── health check ─────────────────────────────────────────────────────────
    @app.route("/health")
    def health():
        return jsonify({"status": "ok", "service": "RCAI"}), 200

    @app.route("/")
    @login_required
    def index():
        return render_template("index.html")

    # ── global error handlers ─────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(_):
        return jsonify({"success": False, "error": "Route not found"}), 404

    @app.errorhandler(500)
    def server_error(e):
        logger.error(f"500: {e}")
        return jsonify({"success": False, "error": "Internal server error"}), 500

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=Config.DEBUG)
