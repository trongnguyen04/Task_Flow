from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from time import time

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from ..extensions import db
from ..models import PasswordResetToken, User
from ..security import validate_password


auth_bp = Blueprint("auth", __name__)

_failed_attempts: dict[str, list[float]] = defaultdict(list)
_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 300
_RESET_TOKEN_MINUTES = 30


def _is_rate_limited(ip: str) -> bool:
    now = time()
    attempts = [t for t in _failed_attempts[ip] if now - t < _WINDOW_SECONDS]
    _failed_attempts[ip] = attempts
    return len(attempts) >= _MAX_ATTEMPTS


def _record_failure(ip: str) -> None:
    _failed_attempts[ip].append(time())


def _hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now_like(value=None):
    now = datetime.now(timezone.utc)
    if value is not None and value.tzinfo is None:
        return now.replace(tzinfo=None)
    return now


def _create_reset_token(user: User) -> str:
    now = _now_like()
    PasswordResetToken.query.filter_by(user_id=user.id, used_at=None).update(
        {"used_at": now}
    )

    raw_token = secrets.token_urlsafe(32)
    db.session.add(
        PasswordResetToken(
            user_id=user.id,
            token_hash=_hash_reset_token(raw_token),
            expires_at=now + timedelta(minutes=_RESET_TOKEN_MINUTES),
        )
    )
    db.session.commit()
    return raw_token


def _get_valid_reset_token(token: str):
    reset_token = PasswordResetToken.query.filter_by(
        token_hash=_hash_reset_token(token),
    ).first()
    if not reset_token or reset_token.used_at:
        return None
    if reset_token.expires_at < _now_like(reset_token.expires_at):
        return None
    if not reset_token.user or not reset_token.user.is_active:
        return None
    return reset_token


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        ip = request.remote_addr or "unknown"

        if _is_rate_limited(ip):
            flash("Quá nhiều lần thử đăng nhập. Vui lòng thử lại sau 5 phút.", "danger")
            return render_template("auth/login.html")

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email, is_active=True).first()

        if not user:
            _record_failure(ip)
            flash("Email hoặc mật khẩu không đúng.", "danger")
        elif not user.check_password(password):
            _record_failure(ip)
            flash("Email hoặc mật khẩu không đúng.", "danger")
        else:
            session.permanent = True
            session["user_id"] = user.id
            session["user_role"] = user.role
            session["user_name"] = user.full_name
            flash("Đăng nhập thành công.", "success")
            if user.role == "Member":
                return redirect(url_for("tasks.my_tasks"))
            return redirect(url_for("projects.index"))

    return render_template("auth/login.html")


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if session.get("user_id"):
        return redirect(url_for("projects.index"))

    reset_url = None
    email = ""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email, is_active=True).first()

        flash(
            "Nếu email tồn tại trong hệ thống, bạn sẽ nhận được hướng dẫn đặt lại mật khẩu.",
            "info",
        )
        if user:
            token = _create_reset_token(user)
            reset_url = url_for("auth.reset_password", token=token, _external=True)

    return render_template(
        "auth/forgot_password.html",
        email=email,
        reset_url=reset_url,
        reset_minutes=_RESET_TOKEN_MINUTES,
    )


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if session.get("user_id"):
        session.clear()

    reset_token = _get_valid_reset_token(token)
    if not reset_token:
        flash("Link đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.", "danger")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        new_password = request.form.get("new_password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not new_password:
            flash("Vui lòng nhập mật khẩu mới.", "danger")
            return render_template("auth/reset_password.html", token=token)
        if new_password != confirm_password:
            flash("Xác nhận mật khẩu không khớp.", "danger")
            return render_template("auth/reset_password.html", token=token)

        pw_error = validate_password(new_password)
        if pw_error:
            flash(pw_error, "danger")
            return render_template("auth/reset_password.html", token=token)

        reset_token.user.set_password(new_password)
        reset_token.used_at = _now_like(reset_token.expires_at)
        db.session.commit()

        flash("Đã đặt lại mật khẩu. Vui lòng đăng nhập bằng mật khẩu mới.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", token=token)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Đã đăng xuất.", "info")
    return redirect(url_for("auth.login"))
