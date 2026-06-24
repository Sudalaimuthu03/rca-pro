from flask import Blueprint, jsonify
from flask_login import login_required, current_user
from services.analytics_service import get_dashboard_stats

bp = Blueprint("analytics", __name__, url_prefix="/api/analytics")


@bp.route("/dashboard", methods=["GET"])
@login_required
def dashboard():
    return jsonify(get_dashboard_stats(int(current_user.id)))
