from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from ..auth import current_user, login_required, roles_required
from ..extensions import db
from ..models import PRIORITIES, PROJECT_STATUSES, STATUSES, Project, ProjectMember, Task, User
from ..queries import member_project_ids, ordered_tasks, visible_projects_for
from ..services import parse_date


projects_bp = Blueprint("projects", __name__, url_prefix="/projects")
PER_PAGE = 20
PROJECT_NAME_MAX_LENGTH = 200


@projects_bp.route("/")
@login_required
def index():
    user = current_user()
    keyword = request.args.get("keyword", "").strip()
    status_filter = request.args.get("status", "").strip()
    page = request.args.get("page", 1, type=int)
    query = Project.query

    if user.role == "Member":
        project_ids = member_project_ids(user.id)
        query = query.filter(Project.id.in_(project_ids)) if project_ids else query.filter(False)

    if keyword:
        query = query.filter(Project.name.ilike(f"%{keyword}%"))
    if status_filter in PROJECT_STATUSES:
        query = query.filter(Project.status == status_filter)

    pagination = query.order_by(Project.created_at.desc(), Project.id.desc()).paginate(
        page=page,
        per_page=PER_PAGE,
        error_out=False,
    )
    projects = pagination.items
    for project in projects:
        project.visible_task_count = _visible_task_count(project, user)

    return render_template(
        "projects/index.html",
        projects=projects,
        keyword=keyword,
        status_filter=status_filter,
        project_statuses=PROJECT_STATUSES,
        pagination=pagination,
        page_url=_page_url("projects.index"),
    )


@projects_bp.route("/<int:project_id>/tasks")
@login_required
def tasks(project_id):
    user = current_user()
    project = db.get_or_404(Project, project_id)
    page = request.args.get("page", 1, type=int)

    if user.role == "Member" and project.id not in member_project_ids(user.id):
        flash("Bạn không có quyền xem dự án.", "danger")
        return redirect(url_for("projects.index"))

    keyword = request.args.get("keyword", "").strip()
    query = Task.query.filter_by(project_id=project_id)
    if user.role == "Member":
        query = query.filter(Task.assignee_id == user.id)
    if keyword:
        query = query.filter(Task.title.ilike(f"%{keyword}%"))

    pagination = ordered_tasks(query).paginate(
        page=page,
        per_page=PER_PAGE,
        error_out=False,
    )
    return render_template(
        "projects/tasks.html",
        project=project,
        tasks=pagination.items,
        keyword=keyword,
        priorities=PRIORITIES,
        statuses=STATUSES,
        pagination=pagination,
        page_url=_page_url("projects.tasks", project_id=project.id),
    )


@projects_bp.route("/create", methods=["GET", "POST"])
@roles_required("Admin")
def create():
    if request.method == "POST":
        form_data = _project_form_data()
        error = _validate_project_form(form_data)
        if error:
            flash(error, "danger")
            return render_project_form(project=None, prefill=form_data)

        project = Project(
            name=form_data["name"],
            description=form_data["description"],
            status=form_data["status"],
            end_date=form_data["deadline"],
        )
        db.session.add(project)
        db.session.commit()
        flash("Đã tạo dự án mới.", "success")
        return redirect(url_for("projects.index"))

    return render_project_form(project=None)


@projects_bp.route("/<int:project_id>/edit", methods=["GET", "POST"])
@roles_required("Admin")
def edit(project_id):
    project = db.get_or_404(Project, project_id)

    if request.method == "POST":
        form_data = _project_form_data()
        error = _validate_project_form(form_data)
        if error:
            flash(error, "danger")
            return render_project_form(project=project, prefill=form_data)

        project.name = form_data["name"]
        project.description = form_data["description"]
        project.end_date = form_data["deadline"]
        new_status = request.form.get("status", project.status)
        if new_status in PROJECT_STATUSES:
            project.status = new_status
        db.session.commit()
        flash("Đã cập nhật dự án.", "success")
        return redirect(url_for("projects.index"))

    return render_project_form(project=project)


@projects_bp.route("/<int:project_id>/members", methods=["GET", "POST"])
@roles_required("Admin")
def members(project_id):
    project = db.get_or_404(Project, project_id)
    users = User.query.filter_by(is_active=True).order_by(User.full_name).all()

    if request.method == "POST":
        try:
            user_id = int(request.form["user_id"])
        except (KeyError, ValueError):
            flash("Thành viên không hợp lệ.", "danger")
            return redirect(url_for("projects.members", project_id=project.id))
        role_in_project = request.form.get("role_in_project", "Member").strip()[:50] or "Member"
        exists = ProjectMember.query.filter_by(project_id=project.id, user_id=user_id).first()
        if not exists:
            db.session.add(
                ProjectMember(
                    project_id=project.id,
                    user_id=user_id,
                    role_in_project=role_in_project,
                )
            )
            db.session.commit()
            flash("Đã thêm thành viên vào dự án.", "success")
        else:
            flash("Thành viên đã có trong dự án.", "warning")
        return redirect(url_for("projects.members", project_id=project.id))

    return render_template("projects/members.html", project=project, users=users)


@projects_bp.route("/<int:project_id>/members/<int:member_id>/remove", methods=["POST"])
@roles_required("Admin")
def remove_member(project_id, member_id):
    member = ProjectMember.query.filter_by(id=member_id, project_id=project_id).first()
    if not member:
        abort(404)
    db.session.delete(member)
    db.session.commit()
    flash("Đã xóa thành viên khỏi dự án.", "success")
    return redirect(url_for("projects.members", project_id=project_id))


@projects_bp.route("/<int:project_id>/delete", methods=["POST"])
@roles_required("Admin")
def delete(project_id):
    project = db.get_or_404(Project, project_id)
    db.session.delete(project)
    db.session.commit()
    flash("Đã xóa dự án.", "success")
    return redirect(url_for("projects.index"))


def render_project_form(project=None, prefill=None):
    return render_template(
        "projects/form.html",
        project=project,
        prefill=prefill or {},
        max_name_length=PROJECT_NAME_MAX_LENGTH,
        today=date.today().isoformat(),
        project_statuses=PROJECT_STATUSES,
    )


def _project_form_data():
    return {
        "name": request.form.get("name", "").strip(),
        "description": request.form.get("description", "").strip(),
        "deadline": parse_date(request.form.get("deadline")),
        "deadline_raw": request.form.get("deadline", ""),
        "status": request.form.get("status", "Active"),
    }


def _validate_project_form(form_data):
    if not form_data["name"]:
        return "Vui lòng nhập tên dự án."
    if len(form_data["name"]) > PROJECT_NAME_MAX_LENGTH:
        return f"Tên dự án không được vượt quá {PROJECT_NAME_MAX_LENGTH} ký tự."
    if not form_data["deadline_raw"]:
        return "Vui lòng chọn deadline."
    if not form_data["deadline"]:
        return "Deadline không hợp lệ."
    if form_data["deadline"] and form_data["deadline"] < date.today():
        return "Deadline không được là ngày trong quá khứ."
    if form_data["status"] not in PROJECT_STATUSES:
        form_data["status"] = "Active"
    return None


def _visible_task_count(project, user):
    if user.role == "Admin":
        return len(project.tasks)
    return Task.query.filter_by(project_id=project.id, assignee_id=user.id).count()


def _page_url(endpoint, **route_values):
    def build(page_number):
        args = request.args.to_dict(flat=True)
        args["page"] = page_number
        return url_for(endpoint, **route_values, **args)

    return build
