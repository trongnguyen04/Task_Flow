from sqlalchemy import case

from .models import Project, ProjectMember, Task


def priority_order():
    return case(
        (Task.priority == "Critical", 0),
        (Task.priority == "High", 1),
        (Task.priority == "Medium", 2),
        (Task.priority == "Low", 3),
        else_=4,
    )


def ordered_tasks(query):
    return query.order_by(
        priority_order(),
        Task.due_date.is_(None),
        Task.due_date.asc(),
        Task.updated_at.desc(),
    )


def visible_task_query(user):
    query = Task.query
    if user.role == "Member":
        query = query.filter(Task.assignee_id == user.id)
    return query


def member_project_ids(user_id):
    member_ids = {
        project_id
        for (project_id,) in ProjectMember.query.with_entities(ProjectMember.project_id)
        .filter(ProjectMember.user_id == user_id)
        .all()
    }
    assigned_ids = {
        project_id
        for (project_id,) in Task.query.with_entities(Task.project_id)
        .filter(Task.assignee_id == user_id)
        .distinct()
        .all()
    }
    return member_ids | assigned_ids


def visible_projects_for(user):
    if user.role == "Admin":
        return Project.query.order_by(Project.name).all()

    project_ids = member_project_ids(user.id)
    if not project_ids:
        return []
    return Project.query.filter(Project.id.in_(project_ids)).order_by(Project.name).all()


def formally_joined_projects(user):
    """Projects where the user is an explicit ProjectMember (excludes task-only involvement)."""
    if user.role == "Admin":
        return Project.query.order_by(Project.name).all()

    ids = {
        project_id
        for (project_id,) in ProjectMember.query
        .with_entities(ProjectMember.project_id)
        .filter(ProjectMember.user_id == user.id)
        .all()
    }
    if not ids:
        return []
    return Project.query.filter(Project.id.in_(ids)).order_by(Project.name).all()
