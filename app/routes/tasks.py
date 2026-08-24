from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from ..auth import current_user, login_required, roles_required
from ..extensions import db
from ..models import PRIORITIES, STATUSES, Project, ProjectMember, Task, TaskHistory, User
from ..queries import member_project_ids, ordered_tasks, visible_projects_for
from ..services import notify_assignment, parse_date


tasks_bp = Blueprint("tasks", __name__, url_prefix="/tasks")
PER_PAGE = 20


@tasks_bp.route("/")
@login_required
def index():
    user = current_user()
    if user.role == "Member":
        return redirect(url_for("tasks.my_tasks"))

    query = Task.query
    page = request.args.get("page", 1, type=int)

    project_id = request.args.get("project_id", type=int)
    priority = request.args.get("priority")
    status = request.args.get("status")
    assignee_id = request.args.get("assignee_id", type=int)
    keyword = request.args.get("keyword", "").strip()

    if user.role == "Member":
        query = query.filter(Task.assignee_id == user.id)
        assignee_id = user.id

    if project_id:
        if user.role == "Member" and project_id not in member_project_ids(user.id):
            query = query.filter(False)
        else:
            query = query.filter(Task.project_id == project_id)
    if priority and priority in PRIORITIES:
        query = query.filter(Task.priority == priority)
    if status and status in STATUSES:
        query = query.filter(Task.status == status)
    if assignee_id:
        query = query.filter(Task.assignee_id == assignee_id)
    if keyword:
        query = query.filter(Task.title.ilike(f"%{keyword}%"))

    users = [user] if user.role == "Member" else User.query.filter_by(is_active=True).order_by(User.full_name).all()
    pagination = ordered_tasks(query).paginate(
        page=page,
        per_page=PER_PAGE,
        error_out=False,
    )
    return render_template(
        "tasks/index.html",
        tasks=pagination.items,
        projects=visible_projects_for(user),
        users=users,
        priorities=PRIORITIES,
        statuses=STATUSES,
        filters=request.args,
        enable_filters=True,
        page_title="Tìm kiếm & lọc công việc",
        pagination=pagination,
        page_url=_page_url("tasks.index"),
    )


@tasks_bp.route("/my")
@login_required
def my_tasks():
    user = current_user()
    query = Task.query.filter(Task.assignee_id == user.id)
    page = request.args.get("page", 1, type=int)

    project_id = request.args.get("project_id", type=int)
    priority = request.args.get("priority")
    status = request.args.get("status")
    keyword = request.args.get("keyword", "").strip()

    if project_id:
        if project_id in member_project_ids(user.id):
            query = query.filter(Task.project_id == project_id)
        else:
            query = query.filter(False)
    if priority and priority in PRIORITIES:
        query = query.filter(Task.priority == priority)
    if status and status in STATUSES:
        query = query.filter(Task.status == status)
    if keyword:
        query = query.filter(Task.title.ilike(f"%{keyword}%"))

    pagination = ordered_tasks(query).paginate(
        page=page,
        per_page=PER_PAGE,
        error_out=False,
    )
    return render_template(
        "tasks/index.html",
        tasks=pagination.items,
        projects=visible_projects_for(user),
        users=[user],
        priorities=PRIORITIES,
        statuses=STATUSES,
        filters=request.args,
        enable_filters=True,
        page_title="Việc của tôi",
        pagination=pagination,
        page_url=_page_url("tasks.my_tasks"),
    )


@tasks_bp.route("/create", methods=["GET", "POST"])
@roles_required("Admin")
def create():
    locked_project_id = request.args.get("project_id", type=int)
    if locked_project_id and not db.session.get(Project, locked_project_id):
        flash("Dự án không hợp lệ.", "danger")
        return redirect(url_for("projects.index"))

    if request.method == "POST":
        back_url = request.form.get("back_url") or url_for("tasks.index")

        title = request.form.get("title", "").strip()
        if not title:
            flash("Tên công việc không được để trống.", "danger")
            return render_task_form(
                default_project_id=locked_project_id or _optional_int(request.form.get("project_id")),
                locked_project_id=locked_project_id,
                back_url=back_url,
            )

        due_raw = request.form.get("due_date", "").strip()
        if not due_raw:
            flash("Hạn xử lý không được để trống.", "danger")
            return render_task_form(
                default_project_id=locked_project_id or _optional_int(request.form.get("project_id")),
                locked_project_id=locked_project_id,
                back_url=back_url,
            )

        due = parse_date(due_raw)
        if not due:
            flash("Hạn xử lý không hợp lệ.", "danger")
            return render_task_form(
                default_project_id=locked_project_id or _optional_int(request.form.get("project_id")),
                locked_project_id=locked_project_id,
                back_url=back_url,
            )
        if due and due < date.today():
            flash("Hạn xử lý không được ở trong quá khứ.", "danger")
            return render_task_form(
                default_project_id=locked_project_id or _optional_int(request.form.get("project_id")),
                locked_project_id=locked_project_id,
                back_url=back_url,
            )

        priority = request.form.get("priority", "Medium")
        if priority not in PRIORITIES:
            priority = "Medium"
        status = request.form.get("status", "Todo")
        if status not in STATUSES:
            status = "Todo"

        project_id = locked_project_id or _optional_int(request.form.get("project_id"))
        if not project_id or not db.session.get(Project, project_id):
            flash("Dự án không hợp lệ.", "danger")
            return render_task_form(locked_project_id=locked_project_id, back_url=back_url)

        assignee_id, assignee_error = _validated_assignee_id(
            request.form.get("assignee_id"),
            project_id,
        )
        if assignee_error:
            flash(assignee_error, "danger")
            return render_task_form(
                default_project_id=project_id,
                locked_project_id=locked_project_id,
                back_url=back_url,
            )

        task = Task(
            project_id=project_id,
            title=title,
            description=request.form.get("description"),
            priority=priority,
            status=status,
            assignee_id=assignee_id,
            created_by_id=session.get("user_id"),
            due_date=due,
        )
        db.session.add(task)
        db.session.flush()
        notify_assignment(task)
        db.session.commit()
        flash("Đã tạo công việc mới.", "success")
        return redirect(back_url)

    back_url = request.referrer or url_for("tasks.index")
    return render_task_form(
        default_project_id=locked_project_id,
        locked_project_id=locked_project_id,
        back_url=back_url,
    )


@tasks_bp.route("/<int:task_id>/edit", methods=["GET", "POST"])
@roles_required("Admin")
def edit(task_id):
    task = db.get_or_404(Task, task_id)

    if request.method == "POST":
        back_url = request.form.get("back_url") or url_for("tasks.index")

        title = request.form.get("title", "").strip()
        if not title:
            flash("Tên công việc không được để trống.", "danger")
            return render_task_form(task, back_url=back_url)

        due_raw = request.form.get("due_date", "").strip()
        if not due_raw:
            flash("Hạn xử lý không được để trống.", "danger")
            return render_task_form(task, back_url=back_url)

        due = parse_date(due_raw)
        if not due:
            flash("Hạn xử lý không hợp lệ.", "danger")
            return render_task_form(task, back_url=back_url)
        if due and due < date.today():
            flash("Hạn xử lý không được ở trong quá khứ.", "danger")
            return render_task_form(task, back_url=back_url)

        priority = request.form.get("priority", "Medium")
        if priority not in PRIORITIES:
            priority = "Medium"
        status = request.form.get("status", "Todo")
        if status not in STATUSES:
            status = "Todo"

        new_project_id = _optional_int(request.form.get("project_id"))
        if not new_project_id or not db.session.get(Project, new_project_id):
            flash("Dá»± Ã¡n khÃ´ng há»£p lá»‡.", "danger")
            return render_task_form(task, back_url=back_url)

        new_assignee_id, assignee_error = _validated_assignee_id(
            request.form.get("assignee_id"),
            new_project_id,
        )
        if assignee_error:
            flash(assignee_error, "danger")
            return render_task_form(task, back_url=back_url)
        new_assignee = db.session.get(User, new_assignee_id) if new_assignee_id else None

        # Thu thập giá trị cũ trước khi thay đổi
        old_fields = [
            ("Tên công việc",    task.title,                                    title),
            ("Mô tả",            (task.description or "").strip(),              (request.form.get("description") or "").strip()),
            ("Ưu tiên",          task.priority,                                 priority),
            ("Trạng thái",       task.status,                                   status),
            ("Người phụ trách",  task.assignee.full_name if task.assignee else None,  new_assignee.full_name if new_assignee else None),
            ("Hạn xử lý",        _format_date(task.due_date),                   _format_date(due)),
        ]

        new_project_id = _optional_int(request.form.get("project_id"))
        if not new_project_id or not db.session.get(Project, new_project_id):
            flash("Dự án không hợp lệ.", "danger")
            return render_task_form(task, back_url=back_url)

        old_assignee_id = task.assignee_id
        task.project_id = new_project_id
        task.title = title
        task.description = request.form.get("description")
        task.priority = priority
        task.status = status
        task.assignee_id = new_assignee_id
        task.due_date = due

        _log_changes(task, old_fields, session.get("user_id"))

        if task.assignee_id and task.assignee_id != old_assignee_id:
            notify_assignment(task)

        db.session.commit()
        flash("Đã cập nhật công việc.", "success")
        return redirect(url_for("tasks.edit", task_id=task.id, back_url=back_url, _anchor="history"))

    back_url = request.args.get("back_url") or request.referrer or url_for("tasks.index")
    return render_task_form(task, back_url=back_url)


@tasks_bp.route("/<int:task_id>/delete", methods=["POST"])
@roles_required("Admin")
def delete(task_id):
    task = db.get_or_404(Task, task_id)
    next_url = request.form.get("next") or request.referrer or url_for("tasks.index")
    db.session.delete(task)
    db.session.commit()
    flash("Đã xóa công việc.", "success")
    return redirect(next_url)


@tasks_bp.route("/<int:task_id>/priority", methods=["POST"])
@roles_required("Admin")
def update_priority(task_id):
    task = db.get_or_404(Task, task_id)
    priority = request.form.get("priority", task.priority)
    if priority not in PRIORITIES:
        flash("Mức ưu tiên không hợp lệ.", "danger")
        return redirect(request.referrer or url_for("tasks.index"))

    if priority != task.priority:
        _log_changes(task, [("Ưu tiên", task.priority, priority)], session.get("user_id"))
        task.priority = priority
        db.session.commit()

    flash("Đã cập nhật mức ưu tiên.", "success")
    return redirect(request.referrer or url_for("tasks.index"))


@tasks_bp.route("/<int:task_id>/status", methods=["POST"])
@login_required
def update_status(task_id):
    task = db.get_or_404(Task, task_id)
    user = current_user()
    if user.role != "Admin" and task.assignee_id != user.id:
        flash("Bạn chỉ được cập nhật trạng thái công việc được giao cho mình.", "danger")
        return redirect(request.referrer or url_for("tasks.my_tasks"))

    new_status = request.form.get("status", task.status)
    if new_status not in STATUSES:
        flash("Trạng thái công việc không hợp lệ.", "danger")
        return redirect(request.referrer or url_for("tasks.my_tasks"))

    if new_status != task.status:
        _log_changes(task, [("Trạng thái", task.status, new_status)], user.id)
        task.status = new_status
        db.session.commit()

    flash("Đã cập nhật trạng thái công việc.", "success")
    return redirect(request.referrer or url_for("tasks.index"))


def render_task_form(task=None, default_project_id=None, locked_project_id=None, back_url=None):
    history = []
    if task:
        history = (
            TaskHistory.query.filter_by(task_id=task.id)
            .order_by(TaskHistory.changed_at.desc())
            .all()
        )
    locked_project = db.session.get(Project, locked_project_id) if locked_project_id else None
    projects = [locked_project] if locked_project else Project.query.order_by(Project.name).all()
    users = (
        _project_member_users(locked_project.id)
        if locked_project
        else User.query.filter_by(is_active=True).order_by(User.full_name).all()
    )
    return render_template(
        "tasks/form.html",
        task=task,
        history=history,
        default_project_id=default_project_id,
        locked_project=locked_project,
        back_url=back_url or url_for("tasks.index"),
        projects=projects,
        users=users,
        priorities=PRIORITIES,
        statuses=STATUSES,
    )


def _format_date(d):
    return d.strftime("%d/%m/%Y") if d else None


def _optional_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _validated_assignee_id(value, project_id):
    if value in (None, ""):
        return None, "Người phụ trách không được để trống."

    assignee_id = _optional_int(value)
    if not assignee_id:
        return None, "Người phụ trách không hợp lệ."

    assignee = User.query.filter_by(id=assignee_id, is_active=True).first()
    if not assignee:
        return None, "Người phụ trách không tồn tại hoặc đã bị khóa."

    membership = ProjectMember.query.filter_by(
        project_id=project_id,
        user_id=assignee_id,
    ).first()
    if not membership:
        return None, "Người phụ trách phải là thành viên của dự án."

    return assignee_id, None


def _project_member_users(project_id):
    return (
        User.query.join(ProjectMember, ProjectMember.user_id == User.id)
        .filter(ProjectMember.project_id == project_id, User.is_active.is_(True))
        .order_by(User.full_name)
        .all()
    )


def _log_changes(task, fields, changed_by_id):
    for label, old_val, new_val in fields:
        old_str = (str(old_val) if old_val is not None else "").strip()
        new_str = (str(new_val) if new_val is not None else "").strip()
        if old_str != new_str:
            db.session.add(TaskHistory(
                task_id=task.id,
                changed_by_id=changed_by_id,
                field=label,
                old_value=old_str[:200] if old_str else None,
                new_value=new_str[:200] if new_str else None,
            ))


def _page_url(endpoint):
    def build(page_number):
        args = request.args.to_dict(flat=True)
        args["page"] = page_number
        return url_for(endpoint, **args)

    return build
