from datetime import date

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from sqlalchemy import func
from sqlalchemy.orm import joinedload

from ..auth import current_user, login_required
from ..extensions import db
from ..models import PRIORITIES, Notification, Project, Task, User
from ..queries import formally_joined_projects, member_project_ids, ordered_tasks, visible_projects_for, visible_task_query


main_bp = Blueprint("main", __name__)
KANBAN_PER_PAGE = 20
KANBAN_STATUSES = (
    ("Todo", "todo"),
    ("Doing", "doing"),
    ("Done", "done"),
)


@main_bp.route("/")
def home():
    if session.get("user_id"):
        return redirect(url_for("projects.index"))
    return render_template("home.html")


@main_bp.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    view = request.args.get("view", "summary")
    task_query = visible_task_query(user)
    visible_projects = visible_projects_for(user)

    today = date.today()
    stats = {
        "projects": len(visible_projects),
        "tasks": task_query.count(),
        "todo": task_query.filter_by(status="Todo").count(),
        "doing": task_query.filter_by(status="Doing").count(),
        "done": task_query.filter_by(status="Done").count(),
        "critical": task_query.filter_by(priority="Critical").count(),
        "overdue": task_query.filter(Task.due_date < today, Task.status != "Done").count(),
    }

    priority_counts = dict(
        task_query
        .with_entities(Task.priority, func.count(Task.id))
        .group_by(Task.priority)
        .all()
    )
    assignee_counts = _db_assignee_counts(user)
    project_overview = _project_overview(user, visible_projects)
    project_progress = [
        {
            "name": item["name"],
            "done": item["done"],
            "total": item["total"],
            "percent": item["percent"],
        }
        for item in project_overview
    ]
    active_project_overview = [
        item for item in project_overview if item["status"] == "Active"
    ]
    critical_alerts = [
        item for item in project_overview if item["critical_open"] > 0
    ]

    return render_template(
        "dashboard/index.html",
        view=view,
        stats=stats,
        priorities=PRIORITIES,
        priority_counts=priority_counts,
        assignee_counts=assignee_counts,
        project_progress=project_progress,
        project_overview=active_project_overview,
        critical_alerts=critical_alerts,
    )


@main_bp.route("/kanban")
@login_required
def kanban():
    user = current_user()
    project_id = request.args.get("project_id", type=int)
    query = visible_task_query(user)
    current_project = None
    if project_id:
        if user.role == "Member" and project_id not in member_project_ids(user.id):
            abort(403)
        query = query.filter_by(project_id=project_id)
        current_project = db.get_or_404(Project, project_id)
    projects = formally_joined_projects(user)
    status_counts = dict(
        query.with_entities(Task.status, func.count(Task.id))
        .group_by(Task.status)
        .all()
    )
    page = max(request.args.get("page", 1, type=int) or 1, 1)
    pagination = (
        ordered_tasks(query)
        .options(joinedload(Task.assignee))
        .paginate(page=page, per_page=KANBAN_PER_PAGE, error_out=False)
    )
    grouped = {
        status_label: [task for task in pagination.items if task.status == status_label]
        for status_label, _ in KANBAN_STATUSES
    }

    return render_template(
        "kanban/index.html",
        grouped=grouped,
        kanban_statuses=KANBAN_STATUSES,
        status_counts=status_counts,
        pagination=pagination,
        page_url=_kanban_page_url,
        projects=projects,
        current_project=current_project,
    )


def _kanban_page_url(page_number):
    args = request.args.to_dict(flat=True)
    args["page"] = page_number
    return url_for("main.kanban", **args)


@main_bp.route("/notifications")
@login_required
def notifications():
    user = current_user()
    page = request.args.get("page", 1, type=int)
    pagination = (
        Notification.query.filter_by(user_id=user.id)
        .order_by(Notification.created_at.desc())
        .paginate(page=page, per_page=20, error_out=False)
    )
    return render_template(
        "notifications/index.html",
        notifications=pagination.items,
        pagination=pagination,
        page_url=lambda p: url_for("main.notifications", page=p),
    )


@main_bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notification_id):
    user = current_user()
    notification = db.get_or_404(Notification, notification_id)
    if notification.user_id != user.id:
        flash("Bạn không có quyền cập nhật thông báo này.", "danger")
        return redirect(url_for("main.notifications"))

    notification.is_read = True
    db.session.commit()
    return redirect(request.referrer or url_for("main.notifications"))


@main_bp.route("/notifications/<int:notification_id>/open")
@login_required
def open_notification(notification_id):
    user = current_user()
    notification = db.get_or_404(Notification, notification_id)
    if notification.user_id != user.id:
        flash("Bạn không có quyền xem thông báo này.", "danger")
        return redirect(url_for("main.notifications"))

    notification.is_read = True
    db.session.commit()

    if notification.task:
        return redirect(url_for("projects.tasks", project_id=notification.task.project_id))
    return redirect(url_for("main.notifications"))


@main_bp.route("/notifications/read-all", methods=["POST"])
@login_required
def mark_all_notifications_read():
    user = current_user()
    Notification.query.filter_by(user_id=user.id, is_read=False).update({"is_read": True})
    db.session.commit()
    flash("Đã đánh dấu tất cả thông báo là đã đọc.", "success")
    return redirect(url_for("main.notifications"))


def _db_assignee_counts(user):
    query = (
        Task.query.with_entities(User.full_name, func.count(Task.id))
        .outerjoin(User, Task.assignee_id == User.id)
        .filter(Task.assignee_id.isnot(None))
    )
    if user.role == "Member":
        query = query.filter(Task.assignee_id == user.id)

    rows = (
        query.group_by(User.full_name)
        .order_by(func.count(Task.id).desc())
        .limit(5)
        .all()
    )
    return [{"name": name, "count": count} for name, count in rows]


def _project_overview(user, projects):
    if not projects:
        return []

    project_ids = [p.id for p in projects]
    query = Task.query.filter(Task.project_id.in_(project_ids))
    if user.role == "Member":
        query = query.filter(Task.assignee_id == user.id)

    tasks_by_project = {}
    for task in query.all():
        tasks_by_project.setdefault(task.project_id, []).append(task)

    items = []
    for project in projects:
        tasks = tasks_by_project.get(project.id, [])
        total = len(tasks)
        done = sum(1 for t in tasks if t.status == "Done")
        critical_open = sum(1 for t in tasks if t.priority == "Critical" and t.status != "Done")
        percent = int((done / total) * 100) if total else 0
        items.append(
            {
                "id": project.id,
                "name": project.name,
                "status": project.status,
                "done": done,
                "total": total,
                "percent": percent,
                "critical_open": critical_open,
                "deadline": project.end_date,
            }
        )

    return sorted(items, key=lambda item: item["percent"], reverse=True)
