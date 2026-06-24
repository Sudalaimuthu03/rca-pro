from datetime import datetime, timezone
from database.connection import execute_query


# ── helpers ────────────────────────────────────────────────────────────────

VALID_SEVERITIES = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
VALID_STATUSES   = {"OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"}

# Bug 12 fixed: safe pagination bounds
_LIMIT_MIN  = 1
_LIMIT_MAX  = 200
_OFFSET_MIN = 0


def _validate_incident(data: dict) -> list[str]:
    errors = []
    if not (data.get("title") or "").strip():
        errors.append("title is required")
    if not (data.get("error_log") or "").strip():
        errors.append("error_log is required")
    severity = (data.get("severity") or "").upper()
    if severity and severity not in VALID_SEVERITIES:
        errors.append(f"severity must be one of {sorted(VALID_SEVERITIES)}")
    return errors


# ── public API ──────────────────────────────────────────────────────────────

def create_incident(user_id: int, data: dict) -> dict:
    errors = _validate_incident(data)
    if errors:
        return {"success": False, "errors": errors}

    sql = """
        INSERT INTO incidents (user_id, title, error_log, severity)
        VALUES (%s,%s,%s,%s)
        RETURNING *
    """
    params = (
        user_id,
        data["title"].strip(),
        data["error_log"].strip(),
        (data.get("severity") or "MEDIUM").upper(),
    )
    row = execute_query(sql, params, fetch="one")
    return {"success": True, "incident": _serialize(row)}


def get_all_incidents(user_id: int, status=None, severity=None, limit=50, offset=0) -> dict:
    # Bug 12 fixed: clamp limit and offset to safe bounds
    limit  = max(_LIMIT_MIN,  min(_LIMIT_MAX,  int(limit)))
    offset = max(_OFFSET_MIN, int(offset))

    conditions, params = ["user_id = %s"], [user_id]

    if status:
        conditions.append("status = %s")
        params.append(status.upper())
    if severity:
        conditions.append("severity = %s")
        params.append(severity.upper())

    where = "WHERE " + " AND ".join(conditions)
    sql = f"""
        SELECT * FROM incidents
        {where}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """
    rows = execute_query(sql, params + [limit, offset], fetch="all")
    count_sql = f"SELECT COUNT(*) AS total FROM incidents {where}"
    total = execute_query(count_sql, params, fetch="one")

    return {
        "success": True,
        "incidents": [_serialize(r) for r in rows],
        "total": total["total"] if total else 0,
        "limit": limit,
        "offset": offset,
    }


def get_incident_by_id(user_id: int, incident_id: int) -> dict:
    sql = "SELECT * FROM incidents WHERE id = %s AND user_id = %s"
    row = execute_query(sql, (incident_id, user_id), fetch="one")
    if not row:
        return {"success": False, "error": "Incident not found"}

    rc_sql = "SELECT * FROM root_causes WHERE incident_id = %s ORDER BY created_at DESC LIMIT 1"
    rc = execute_query(rc_sql, (incident_id,), fetch="one")
    if rc and rc.get("created_at"):
        rc["created_at"] = rc["created_at"].isoformat()

    incident = _serialize(row)
    incident["analysis"] = rc
    return {"success": True, "incident": incident}


def update_incident(user_id: int, incident_id: int, data: dict) -> dict:
    existing = execute_query(
        "SELECT id FROM incidents WHERE id = %s AND user_id = %s", (incident_id, user_id), fetch="one"
    )
    if not existing:
        return {"success": False, "error": "Incident not found"}

    # Bug 2 fixed: validate status and severity before writing
    if "status" in data:
        val = (data["status"] or "").upper()
        if val not in VALID_STATUSES:
            return {"success": False, "error": f"status must be one of {sorted(VALID_STATUSES)}"}

    if "severity" in data:
        val = (data["severity"] or "").upper()
        if val not in VALID_SEVERITIES:
            return {"success": False, "error": f"severity must be one of {sorted(VALID_SEVERITIES)}"}

    allowed = ["title", "error_log", "severity", "status"]
    updates, params = [], []
    for field in allowed:
        if field in data:
            val = data[field]
            if field in ("severity", "status"):
                val = val.upper()
            updates.append(f"{field} = %s")
            params.append(val)
            # Bug 10 fixed: if status is being set to RESOLVED via update,
            # also stamp resolved_at so analytics avg_resolution is correct
            if field == "status" and val == "RESOLVED":
                updates.append("resolved_at = %s")
                params.append(datetime.now(timezone.utc))

    if not updates:
        return {"success": False, "error": "No valid fields to update"}

    params += [incident_id, user_id]
    sql = f"UPDATE incidents SET {', '.join(updates)} WHERE id = %s AND user_id = %s RETURNING *"
    row = execute_query(sql, params, fetch="one")
    return {"success": True, "incident": _serialize(row)}


def resolve_incident(user_id: int, incident_id: int) -> dict:
    """Bug 1 fixed: dedicated resolve — sets status=RESOLVED and stamps resolved_at."""
    existing = execute_query(
        "SELECT id, status FROM incidents WHERE id = %s AND user_id = %s", (incident_id, user_id), fetch="one"
    )
    if not existing:
        return {"success": False, "error": "Incident not found"}
    if existing["status"] in ("RESOLVED", "CLOSED"):
        return {"success": False, "error": f"Incident is already {existing['status'].lower()}"}

    sql = """
        UPDATE incidents
        SET status = 'RESOLVED', resolved_at = %s
        WHERE id = %s AND user_id = %s
        RETURNING *
    """
    # Bug 9 fixed: datetime.utcnow() → datetime.now(timezone.utc)
    row = execute_query(sql, (datetime.now(timezone.utc), incident_id, user_id), fetch="one")
    return {"success": True, "incident": _serialize(row)}


def close_incident(user_id: int, incident_id: int) -> dict:
    """Bug 1 fixed: close sets status=CLOSED (not RESOLVED)."""
    existing = execute_query(
        "SELECT id, status FROM incidents WHERE id = %s AND user_id = %s", (incident_id, user_id), fetch="one"
    )
    if not existing:
        return {"success": False, "error": "Incident not found"}
    if existing["status"] == "CLOSED":
        return {"success": False, "error": "Incident is already closed"}

    sql = """
        UPDATE incidents
        SET status = 'CLOSED'
        WHERE id = %s AND user_id = %s
        RETURNING *
    """
    row = execute_query(sql, (incident_id, user_id), fetch="one")
    return {"success": True, "incident": _serialize(row)}


def set_in_progress(user_id: int, incident_id: int) -> dict:
    """Bug 1 fixed: wire IN_PROGRESS — called automatically when /analyze is triggered."""
    existing = execute_query(
        "SELECT id, status FROM incidents WHERE id = %s AND user_id = %s", (incident_id, user_id), fetch="one"
    )
    if not existing:
        return {"success": False, "error": "Incident not found"}
    if existing["status"] != "OPEN":
        return {"success": True, "skipped": True}  # already past OPEN, don't regress

    sql = "UPDATE incidents SET status = 'IN_PROGRESS' WHERE id = %s AND user_id = %s RETURNING *"
    row = execute_query(sql, (incident_id, user_id), fetch="one")
    return {"success": True, "incident": _serialize(row)}


def delete_incident(user_id: int, incident_id: int) -> dict:
    existing = execute_query(
        "SELECT id FROM incidents WHERE id = %s AND user_id = %s", (incident_id, user_id), fetch="one"
    )
    if not existing:
        return {"success": False, "error": "Incident not found"}
    execute_query("DELETE FROM incidents WHERE id = %s AND user_id = %s", (incident_id, user_id))
    return {"success": True, "message": f"Incident {incident_id} deleted"}


# ── serialiser ──────────────────────────────────────────────────────────────

def _serialize(row: dict) -> dict:
    if not row:
        return {}
    result = dict(row)
    for key in ("created_at", "resolved_at"):
        if result.get(key):
            result[key] = result[key].isoformat()
    return result
