from ..extensions import db


class ProjectMember(db.Model):
    __tablename__ = "project_members"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    role_in_project = db.Column(db.String(60), nullable=False, default="Member")

    project = db.relationship("Project", back_populates="members")
    user = db.relationship("User", back_populates="project_memberships")

    __table_args__ = (
        db.UniqueConstraint("project_id", "user_id", name="uq_project_member"),
    )
