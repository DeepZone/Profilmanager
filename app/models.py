from datetime import datetime

import bcrypt
from flask_login import UserMixin

from app.extensions import db


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255))

    users = db.relationship("User", back_populates="role")


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    shortcode = db.Column(db.String(3), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)

    role = db.relationship("Role", back_populates="users")
    profiles = db.relationship("Profile", back_populates="owner")

    def set_password(self, password: str):
        self.password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    def check_password(self, password: str) -> bool:
        return bcrypt.checkpw(password.encode(), self.password_hash.encode())

    @property
    def is_admin(self) -> bool:
        return self.role and self.role.name == "Admin"

    @property
    def is_active(self):
        return self.active


class Profile(db.Model):
    __tablename__ = "profiles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    provider = db.Column(db.String(120), nullable=True)
    country_code = db.Column(db.String(2), nullable=True)
    dial_code = db.Column(db.String(10), nullable=True)
    description = db.Column(db.Text)
    comment = db.Column(db.Text)
    current_version = db.Column(db.Integer, default=1, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    owner = db.relationship("User", back_populates="profiles")
    files = db.relationship(
        "ProfileFile", back_populates="profile", cascade="all, delete-orphan"
    )
    merge_requests = db.relationship("GitLabMergeRequest", back_populates="profile")


class ProfileFile(db.Model):
    __tablename__ = "profile_files"

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("profiles.id"), nullable=False)
    version = db.Column(db.Integer, nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(500), nullable=False)
    mime_type = db.Column(db.String(120))
    file_size = db.Column(db.Integer, nullable=False)
    sha256 = db.Column(db.String(64), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    profile = db.relationship("Profile", back_populates="files")


class Setting(db.Model):
    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(120), unique=True, nullable=False)
    value = db.Column(db.Text)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )


class GitLabMergeRequest(db.Model):
    __tablename__ = "gitlab_merge_requests"

    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey("profiles.id"), nullable=False)
    created_by = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    project_id = db.Column(db.Integer, nullable=False)
    branch_name = db.Column(db.String(255), nullable=False)
    target_branch = db.Column(db.String(255), nullable=False)
    commit_sha = db.Column(db.String(64))
    gitlab_mr_iid = db.Column(db.Integer, nullable=False)
    gitlab_mr_id = db.Column(db.Integer, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), nullable=False, default="opened")
    web_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    profile = db.relationship("Profile", back_populates="merge_requests")


class AuditLog(db.Model):
    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = db.Column(db.String(120), nullable=False)
    details = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
