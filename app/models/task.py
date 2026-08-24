from ..extensions import db
from .base import _utcnow


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    priority = db.Column(db.String(30), nullable=False, default="Medium")
    status = db.Column(db.String(30), nullable=False, default="Todo")
    assignee_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    due_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )

    project = db.relationship("Project", back_populates="tasks")
    assignee = db.relationship(
        "User",
        foreign_keys=[assignee_id],
        back_populates="assigned_tasks",
    )
    created_by = db.relationship("User", foreign_keys=[created_by_id])
    notifications = db.relationship("Notification", back_populates="task", cascade="all, delete-orphan")
    history = db.relationship("TaskHistory", back_populates="task", cascade="all, delete-orphan")
