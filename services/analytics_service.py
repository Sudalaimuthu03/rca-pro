from database.connection import execute_query


def get_dashboard_stats(user_id: int) -> dict:
    summary = execute_query(
        """
        SELECT
            COUNT(*) FILTER (WHERE status = 'OPEN')        AS open_count,
            COUNT(*) FILTER (WHERE status = 'IN_PROGRESS') AS in_progress_count,
            COUNT(*) FILTER (WHERE status = 'RESOLVED')    AS resolved_count,
            COUNT(*) FILTER (WHERE status = 'CLOSED')      AS closed_count,
            COUNT(*) FILTER (WHERE severity = 'CRITICAL')  AS critical_count,
            COUNT(*)                                       AS total_count
        FROM incidents
        WHERE user_id = %s
        """,
        (user_id,), fetch="one"
    )

    avg_resolution = execute_query(
        """
        SELECT ROUND(
            AVG(EXTRACT(EPOCH FROM (resolved_at - created_at)) / 60)::numeric, 2
        ) AS avg_resolution_minutes
        FROM incidents
        WHERE user_id = %s AND resolved_at IS NOT NULL
        """,
        (user_id,), fetch="one"
    )

    root_cause_dist = execute_query(
        """
        SELECT rc.category, COUNT(*) AS count
        FROM root_causes rc
        JOIN incidents i ON i.id = rc.incident_id
        WHERE i.user_id = %s
        GROUP BY rc.category
        ORDER BY count DESC
        """,
        (user_id,), fetch="all"
    )

    recent = execute_query(
        """
        SELECT id, title, severity, status, created_at
        FROM incidents
        WHERE user_id = %s
        ORDER BY created_at DESC
        LIMIT 10
        """,
        (user_id,), fetch="all"
    )

    daily_trend = execute_query(
        """
        SELECT DATE(created_at) AS day, COUNT(*) AS incidents
        FROM incidents
        WHERE user_id = %s AND created_at >= NOW() - INTERVAL '30 days'
        GROUP BY day
        ORDER BY day
        """,
        (user_id,), fetch="all"
    )

    return {
        "success": True,
        "summary": {
            "open":        summary.get("open_count", 0),
            "in_progress": summary.get("in_progress_count", 0),
            "resolved":    summary.get("resolved_count", 0),
            "closed":      summary.get("closed_count", 0),
            "critical":    summary.get("critical_count", 0),
            "total":       summary.get("total_count", 0),
        },
        "avg_resolution_minutes": float(avg_resolution.get("avg_resolution_minutes") or 0),
        "root_cause_distribution": root_cause_dist,
        "recent_incidents": [
            {**r, "created_at": r["created_at"].isoformat()} for r in recent
        ],
        "daily_trend": [
            {"day": str(r["day"]), "incidents": r["incidents"]} for r in daily_trend
        ],
    }
