from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from services.incident_service import (
    create_incident, get_all_incidents, get_incident_by_id,
    update_incident, resolve_incident, close_incident,
    set_in_progress, delete_incident
)
from services.ai_service import analyze_incident

bp = Blueprint("incidents", __name__, url_prefix="/api/incidents")


def _json(data: dict, status: int = 200):
    return jsonify(data), status


def _uid() -> int:
    return int(current_user.id)


# ── CRUD ────────────────────────────────────────────────────────────────────

@bp.route("", methods=["POST"])
@login_required
def create():
    data = request.get_json(silent=True) or {}
    result = create_incident(_uid(), data)
    return _json(result, 201 if result["success"] else 400)


@bp.route("", methods=["GET"])
@login_required
def list_all():
    status   = request.args.get("status")
    severity = request.args.get("severity")
    # Bug 3 fixed: wrap int() in try/except so bad values return 400, not 500
    try:
        limit  = int(request.args.get("limit",  50))
        offset = int(request.args.get("offset",  0))
    except (ValueError, TypeError):
        return _json({"success": False, "error": "limit and offset must be integers"}, 400)
    return _json(get_all_incidents(_uid(), status, severity, limit, offset))


@bp.route("/<int:incident_id>", methods=["GET"])
@login_required
def get_one(incident_id):
    result = get_incident_by_id(_uid(), incident_id)
    return _json(result, 200 if result["success"] else 404)


@bp.route("/<int:incident_id>", methods=["PUT"])
@login_required
def update(incident_id):
    data   = request.get_json(silent=True) or {}
    result = update_incident(_uid(), incident_id, data)
    return _json(result, 200 if result["success"] else 404)


@bp.route("/<int:incident_id>/resolve", methods=["PUT"])
@login_required
def resolve(incident_id):
    # Bug 1 fixed: calls resolve_incident (RESOLVED + resolved_at)
    result = resolve_incident(_uid(), incident_id)
    return _json(result, 200 if result["success"] else 400)


@bp.route("/<int:incident_id>/close", methods=["PUT"])
@login_required
def close(incident_id):
    # Bug 1 fixed: new /close endpoint sets status=CLOSED
    result = close_incident(_uid(), incident_id)
    return _json(result, 200 if result["success"] else 400)


@bp.route("/<int:incident_id>", methods=["DELETE"])
@login_required
def delete(incident_id):
    result = delete_incident(_uid(), incident_id)
    return _json(result, 200 if result["success"] else 404)


# ── AI analysis ──────────────────────────────────────────────────────────────

@bp.route("/<int:incident_id>/analyze", methods=["POST"])
@login_required
def analyze(incident_id):
    existing = get_incident_by_id(_uid(), incident_id)
    if not existing["success"]:
        return _json(existing, 404)

    incident = existing["incident"]

    # Bug 4 fixed: block re-analysis if a root_cause row already exists
    if incident.get("analysis"):
        return _json(
            {"success": False, "error": "This incident has already been analyzed. Delete it and create a new one to re-analyze."},
            409,
        )

    # Bug 1 fixed: auto-transition to IN_PROGRESS when analysis starts
    set_in_progress(_uid(), incident_id)

    result = analyze_incident(incident_id, _uid(), incident["title"], incident["error_log"])
    return _json(result, 200 if result["success"] else 502)
