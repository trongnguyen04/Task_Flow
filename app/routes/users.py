from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from ..auth import login_required, roles_required
from ..extensions import db
from ..models import Task, TaskHistory, USER_ROLES, User
from ..security import validate_password


users_bp = Blueprint("users", __name__, url_prefix="/users")

@users_bp.route("/")
@roles_required("Admin")
def index():
    keyword = request.args.get("keyword", "").strip()
    role = request.args.get("role", "").strip()
    status = request.args.get("status", "").strip()

    query = User.query
    if keyword:
        like = f"%{keyword}%"
        query = query.filter((User.full_name.ilike(like)) | (User.email.ilike(like)))
    if role:
        query = query.filter(User.role == role)
    if status == "active":
        query = query.filter(User.is_active.is_(True))
    elif status == "inactive":
        query = query.filter(User.is_active.is_(False))

    users = query.order_by(User.created_at.desc()).all()
    return render_template(
        "users/index.html",
        users=users,
        roles=USER_ROLES,
        filters=request.args,
    )


@users_bp.route("/create", methods=["GET", "POST"])
@roles_required("Admin")
def create():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if User.query.filter_by(email=email).first():
            flash("Email đã tồn tại trong hệ thống.", "danger")
            return render_user_form(prefill=request.form)

        if not password:
            flash("Vui lòng nhập mật khẩu.", "danger")
            return render_user_form(prefill=request.form)

        if not confirm_password:
            flash("Vui lòng xác nhận mật khẩu.", "danger")
            return render_user_form(prefill=request.form)
        if password != confirm_password:
            flash("Xác nhận mật khẩu không khớp.", "danger")
            return render_user_form(prefill=request.form)

        pw_error = validate_password(password)
        if pw_error:
            flash(pw_error, "danger")
            return render_user_form(prefill=request.form)

        user = User(
            full_name=request.form["full_name"].strip(),
            email=email,
            role=request.form.get("role", "Member"),
            is_active=bool(request.form.get("is_active")),
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash("Đã tạo người dùng mới.", "success")
        return redirect(url_for("users.index"))

    return render_user_form()


@users_bp.route("/<int:user_id>/edit", methods=["GET", "POST"])
@roles_required("Admin")
def edit(user_id):
    user = db.get_or_404(User, user_id)

    if request.method == "POST":
        email = request.form["email"].strip().lower()
        existing = User.query.filter(User.email == email, User.id != user.id).first()
        if existing:
            flash("Email đã được sử dụng bởi người dùng khác.", "danger")
            return render_user_form(user)

        user.full_name = request.form["full_name"].strip()
        user.email = email
        user.role = request.form.get("role", "Member")
        user.is_active = bool(request.form.get("is_active"))

        new_password = request.form.get("password", "").strip()
        confirm_password = request.form.get("confirm_password", "").strip()
        if new_password:
            if not confirm_password:
                flash("Vui lòng xác nhận mật khẩu mới.", "danger")
                return render_user_form(user)
            if new_password != confirm_password:
                flash("Xác nhận mật khẩu mới không khớp.", "danger")
                return render_user_form(user)
            pw_error = validate_password(new_password)
            if pw_error:
                flash(pw_error, "danger")
                return render_user_form(user)
            user.set_password(new_password)

        db.session.commit()
        flash("Đã cập nhật người dùng.", "success")
        return redirect(url_for("users.index"))

    return render_user_form(user)


@users_bp.route("/<int:user_id>/toggle", methods=["POST"])
@roles_required("Admin")
def toggle(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == session.get("user_id"):
        flash("Không thể khóa tài khoản đang đăng nhập.", "warning")
        return redirect(url_for("users.index"))

    user.is_active = not user.is_active
    db.session.commit()
    flash("Đã cập nhật trạng thái tài khoản.", "success")
    return redirect(url_for("users.index"))


@users_bp.route("/<int:user_id>/delete", methods=["POST"])
@roles_required("Admin")
def delete(user_id):
    user = db.get_or_404(User, user_id)
    if user.id == session.get("user_id"):
        flash("Không thể xóa tài khoản đang đăng nhập.", "warning")
        return redirect(url_for("users.index"))

    Task.query.filter_by(assignee_id=user.id).update({"assignee_id": None})
    Task.query.filter_by(created_by_id=user.id).update({"created_by_id": None})
    TaskHistory.query.filter_by(changed_by_id=user.id).update({"changed_by_id": None})
    db.session.delete(user)  # notifications and project_memberships cascade automatically
    db.session.commit()
    flash("Đã xóa người dùng.", "success")
    return redirect(url_for("users.index"))


def render_user_form(user=None, prefill=None):
    return render_template("users/form.html", user=user, roles=USER_ROLES, prefill=prefill or {})


@users_bp.route("/profile")
@login_required
def profile_legacy():
    return redirect(url_for("users.profile"))


@users_bp.route("/change-password", methods=["GET", "POST"])
@login_required
def profile():
    from ..auth import current_user
    user = current_user()

    if request.method == "POST":
        current_pw = request.form.get("current_password", "").strip()
        new_pw = request.form.get("new_password", "").strip()
        confirm_pw = request.form.get("confirm_password", "").strip()

        if not user.check_password(current_pw):
            flash("Mật khẩu hiện tại không đúng.", "danger")
            return render_template("users/profile.html", user=user)
        pw_error = validate_password(new_pw)
        if pw_error:
            flash(pw_error, "danger")
            return render_template("users/profile.html", user=user)
        if new_pw != confirm_pw:
            flash("Xác nhận mật khẩu không khớp.", "danger")
            return render_template("users/profile.html", user=user)

        user.set_password(new_pw)
        db.session.commit()
        flash("Đã đổi mật khẩu thành công.", "success")
        return redirect(url_for("users.profile"))

    return render_template("users/profile.html", user=user)
