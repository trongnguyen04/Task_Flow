from datetime import date

from flask import Blueprint, jsonify, request, session

from ..auth import current_user
from ..extensions import db
from ..models import PRIORITIES, STATUSES, Project, ProjectMember, Task, TaskHistory, User
from ..queries import member_project_ids, ordered_tasks, visible_projects_for
from ..services import notify_assignment, parse_date


api_bp = Blueprint("api", __name__)


@api_bp.get("/session")
def session_check():
    user = current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    return jsonify({"ok": True})


@api_bp.get("/projects")
def projects():
    user = current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    query = Project.query
    if user.role == "Member":
        project_ids = member_project_ids(user.id)
        query = query.filter(Project.id.in_(project_ids)) if project_ids else query.filter(False)

    items = query.order_by(Project.created_at.desc()).all()
    return jsonify([
        {"id": i.id, "name": i.name, "description": i.description, "status": i.status}
        for i in items
    ])


@api_bp.get("/tasks")
def tasks():
    user = current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    query = Task.query
    if user.role == "Member":
        query = query.filter(Task.assignee_id == user.id)

    if request.args.get("project_id"):
        query = query.filter_by(project_id=request.args.get("project_id", type=int))
    priority = request.args.get("priority")
    if priority and priority in PRIORITIES:
        query = query.filter_by(priority=priority)
    status = request.args.get("status")
    if status and status in STATUSES:
        query = query.filter_by(status=status)
    if request.args.get("assignee_id") and user.role == "Admin":
        query = query.filter_by(assignee_id=request.args.get("assignee_id", type=int))

    items = ordered_tasks(query).all()
    return jsonify([_task_to_dict(i) for i in items])


@api_bp.post("/tasks")
def create_task():
    user = current_user()
    if not user or user.role != "Admin":
        return jsonify({"error": "Forbidden"}), 403

    data = request.get_json() or {}

    project_id = _to_int(data.get("project_id"))
    title = (data.get("title") or "").strip()
    if not project_id:
        return jsonify({"error": "project_id is required"}), 400
    if not title:
        return jsonify({"error": "title is required"}), 400
    if not db.session.get(Project, project_id):
        return jsonify({"error": "Project not found"}), 404

    due_raw = (data.get("due_date") or "").strip()
    if not due_raw:
        return jsonify({"error": "due_date is required"}), 400
    due_date = parse_date(due_raw)
    if not due_date:
        return jsonify({"error": "Invalid due_date"}), 400
    if due_date < date.today():
        return jsonify({"error": "due_date cannot be in the past"}), 400

    priority = data.get("priority", "Medium")
    if priority not in PRIORITIES:
        priority = "Medium"
    status = data.get("status", "Todo")
    if status not in STATUSES:
        status = "Todo"

    assignee_id, assignee_error = _validated_assignee_id(
        data.get("assignee_id"),
        project_id,
    )
    if assignee_error:
        return jsonify({"error": assignee_error}), 400

    task = Task(
        project_id=project_id,
        title=title,
        description=data.get("description"),
        priority=priority,
        status=status,
        assignee_id=assignee_id,
        created_by_id=session.get("user_id"),
        due_date=due_date,
    )
    db.session.add(task)
    db.session.flush()
    notify_assignment(task)
    db.session.commit()
    return jsonify(_task_to_dict(task)), 201


@api_bp.patch("/tasks/<int:task_id>")
def update_task(task_id):
    user = current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    task = db.get_or_404(Task, task_id)
    data = request.get_json() or {}

    if user.role == "Member":
        if task.assignee_id != user.id or set(data.keys()) - {"status"}:
            return jsonify({"error": "Forbidden"}), 403
        new_status = data.get("status")
        if new_status not in STATUSES:
            return jsonify({"error": "Invalid status"}), 400
        if new_status != task.status:
            db.session.add(TaskHistory(
                task_id=task.id,
                changed_by_id=user.id,
                field="Trạng thái",
                old_value=task.status,
                new_value=new_status,
            ))
            task.status = new_status
        db.session.commit()
        return jsonify(_task_to_dict(task))

    if user.role != "Admin":
        return jsonify({"error": "Forbidden"}), 403

    old_assignee_id = task.assignee_id
    user_id = session.get("user_id")
    changes = []

    if "status" in data:
        if data["status"] not in STATUSES:
            return jsonify({"error": "Invalid status"}), 400
        if data["status"] != task.status:
            changes.append(("Trạng thái", task.status, data["status"]))
            task.status = data["status"]
    if "priority" in data:
        if data["priority"] in PRIORITIES and data["priority"] != task.priority:
            changes.append(("Ưu tiên", task.priority, data["priority"]))
            task.priority = data["priority"]
    if "assignee_id" in data:
        new_assignee_id, assignee_error = _validated_assignee_id(
            data.get("assignee_id"),
            task.project_id,
        )
        if assignee_error:
            return jsonify({"error": assignee_error}), 400
        if new_assignee_id != task.assignee_id:
            old_name = task.assignee.full_name if task.assignee else None
            new_user = db.session.get(User, new_assignee_id) if new_assignee_id else None
            changes.append(("Người phụ trách", old_name, new_user.full_name if new_user else None))
            task.assignee_id = new_assignee_id

    for label, old_val, new_val in changes:
        old_str = str(old_val) if old_val is not None else ""
        new_str = str(new_val) if new_val is not None else ""
        db.session.add(TaskHistory(
            task_id=task.id,
            changed_by_id=user_id,
            field=label,
            old_value=old_str[:200] or None,
            new_value=new_str[:200] or None,
        ))

    if task.assignee_id and task.assignee_id != old_assignee_id:
        notify_assignment(task)
    db.session.commit()
    return jsonify(_task_to_dict(task))


@api_bp.get("/users")
def users():
    user = current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401
    if user.role != "Admin":
        return jsonify({"error": "Forbidden"}), 403

    items = User.query.filter_by(is_active=True).order_by(User.full_name).all()
    return jsonify([
        {"id": i.id, "full_name": i.full_name, "email": i.email, "role": i.role}
        for i in items
    ])


@api_bp.get("/dashboard")
def dashboard():
    user = current_user()
    if not user:
        return jsonify({"error": "Unauthorized"}), 401

    query = Task.query
    if user.role == "Member":
        query = query.filter(Task.assignee_id == user.id)

    return jsonify({
        "projects": len(visible_projects_for(user)),
        "tasks": query.count(),
        "todo": query.filter_by(status="Todo").count(),
        "doing": query.filter_by(status="Doing").count(),
        "done": query.filter_by(status="Done").count(),
        "critical": query.filter_by(priority="Critical").count(),
    })


def _task_to_dict(task):
    return {
        "id": task.id,
        "project_id": task.project_id,
        "project_name": task.project.name if task.project else None,
        "title": task.title,
        "description": task.description,
        "priority": task.priority,
        "status": task.status,
        "assignee_id": task.assignee_id,
        "assignee_name": task.assignee.full_name if task.assignee else None,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "updated_at": task.updated_at.isoformat() if task.updated_at else None,
    }


def _to_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _validated_assignee_id(value, project_id):
    assignee_id = _to_int(value)
    if value in (None, ""):
        return None, "assignee_id is required"
    if not assignee_id:
        return None, "Invalid assignee_id"

    assignee = User.query.filter_by(id=assignee_id, is_active=True).first()
    if not assignee:
        return None, "Assignee not found or inactive"

    membership = ProjectMember.query.filter_by(
        project_id=project_id,
        user_id=assignee_id,
    ).first()
    if not membership:
        return None, "Assignee is not a member of this project"

    return assignee_id, None

