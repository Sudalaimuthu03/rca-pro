from flask import Blueprint, request, jsonify, render_template, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from services.auth_service import signup as do_signup, login as do_login

bp = Blueprint("auth", __name__)


# ── pages ────────────────────────────────────────────────────────────────────

@bp.route("/login", methods=["GET"])
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return render_template("login.html")


@bp.route("/signup", methods=["GET"])
def signup_page():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return render_template("signup.html")


# ── api ──────────────────────────────────────────────────────────────────────

@bp.route("/api/auth/signup", methods=["POST"])
def signup_api():
    data = request.get_json(silent=True) or {}
    result = do_signup(data)
    if not result["success"]:
        return jsonify(result), 400
    login_user(result["user"], remember=True)
    return jsonify({"success": True, "user": {"name": result["user"].name, "email": result["user"].email}}), 201


@bp.route("/api/auth/login", methods=["POST"])
def login_api():
    data = request.get_json(silent=True) or {}
    result = do_login(data.get("email", ""), data.get("password", ""))
    if not result["success"]:
        return jsonify(result), 401
    login_user(result["user"], remember=bool(data.get("remember")))
    return jsonify({"success": True, "user": {"name": result["user"].name, "email": result["user"].email}})


@bp.route("/api/auth/logout", methods=["POST"])
@login_required
def logout_api():
    logout_user()
    return jsonify({"success": True})


@bp.route("/api/auth/me", methods=["GET"])
@login_required
def me():
    return jsonify({"success": True, "user": {"name": current_user.name, "email": current_user.email}})
