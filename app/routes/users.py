from sqlalchemy.exc import IntegrityError
from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.decorators import admin_required
from app.extensions import db
from app.forms import SelfProfileForm, UserForm
from app.models import AuditLog, GitLabMergeRequest, Profile, Role, User

users_bp = Blueprint("users", __name__, url_prefix="/users")


def _normalize_shortcode(value: str) -> str:
    return (value or "").strip().upper()


@users_bp.route("/")
@login_required
@admin_required
def index():
    q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    query = User.query
    if q:
        query = query.filter(User.username.ilike(f"%{q}%"))
    pagination = query.order_by(User.created_at.desc()).paginate(page=page, per_page=15)
    return render_template("users/index.html", pagination=pagination, q=q)


@users_bp.route("/me")
@login_required
def me():
    form = SelfProfileForm(obj=current_user)
    if form.validate_on_submit():
        password_change_requested = any(
            bool((value or "").strip())
            for value in [
                form.current_password.data,
                form.new_password.data,
                form.confirm_new_password.data,
            ]
        )
        submitted_token = (form.gitlab_token.data or "").strip()
        token_changed = bool(submitted_token) and submitted_token != (current_user.gitlab_token or "")
        if submitted_token:
            current_user.gitlab_token = submitted_token

        if password_change_requested:
            if not current_user.check_password(form.current_password.data):
                flash("Aktuelles Passwort ist nicht korrekt.", "danger")
                return render_template("users/me.html", form=form)

            current_user.set_password(form.new_password.data)
            db.session.add(
                AuditLog(
                    user_id=current_user.id,
                    action="user_password_change",
                    details=f"User {current_user.username} changed own password",
                )
            )

        if token_changed:
            db.session.add(
                AuditLog(
                    user_id=current_user.id,
                    action="user_gitlab_token_change",
                    details=f"User {current_user.username} changed own GitLab token",
                )
            )

        if not password_change_requested and not token_changed:
            flash("Keine Änderungen erkannt.", "info")
            return redirect(url_for("users.me"))

        db.session.add(
            AuditLog(user_id=current_user.id, action="user_profile_edit", details="Own profile updated")
        )
        db.session.commit()
        if password_change_requested and token_changed:
            flash("Passwort und GitLab API Token erfolgreich gespeichert.", "success")
        elif password_change_requested:
            flash("Passwort erfolgreich geändert.", "success")
        else:
            flash("GitLab API Token erfolgreich gespeichert.", "success")
        return redirect(url_for("users.me"))

    return render_template("users/me.html", form=form)


@users_bp.route("/new", methods=["GET", "POST"])
@login_required
@admin_required
def create():
    form = UserForm()
    if form.validate_on_submit():
        if not form.password.data:
            flash("Passwort ist für neue Benutzer erforderlich.", "danger")
            return render_template("users/form.html", form=form, title="Benutzer erstellen")

        role = Role.query.filter_by(name=form.role.data).first()
        user = User(
            username=form.username.data,
            email=form.email.data,
            shortcode=_normalize_shortcode(form.shortcode.data),
            active=form.active.data,
            role=role,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.add(
            AuditLog(user_id=current_user.id, action="user_create", details=f"User {user.username}")
        )

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Dieses Kürzel ist bereits vergeben", "danger")
            return render_template("users/form.html", form=form, title="Benutzer erstellen")

        flash("Benutzer erstellt.", "success")
        return redirect(url_for("users.index"))
    return render_template("users/form.html", form=form, title="Benutzer erstellen")


@users_bp.route("/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@admin_required
def edit(user_id):
    user = User.query.get_or_404(user_id)
    form = UserForm(obj=user)
    form.user_id = user.id
    form.role.data = user.role.name

    if form.validate_on_submit():
        role = Role.query.filter_by(name=form.role.data).first()

        user.username = form.username.data
        user.email = form.email.data
        user.active = form.active.data
        user.role = role
        user.shortcode = _normalize_shortcode(form.shortcode.data)
        if form.password.data:
            user.set_password(form.password.data)

        db.session.add(
            AuditLog(user_id=current_user.id, action="user_edit", details=f"User {user.username}")
        )

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("Dieses Kürzel ist bereits vergeben", "danger")
            return render_template("users/form.html", form=form, title="Benutzer bearbeiten")

        flash("Benutzer aktualisiert.", "success")
        return redirect(url_for("users.index"))

    return render_template("users/form.html", form=form, title="Benutzer bearbeiten")


@users_bp.route("/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        flash("Sie können sich nicht selbst löschen.", "danger")
        return redirect(url_for("users.index"))

    Profile.query.filter_by(user_id=user.id).update({"user_id": None}, synchronize_session=False)
    GitLabMergeRequest.query.filter_by(created_by=user.id).update(
        {"created_by": None}, synchronize_session=False
    )
    AuditLog.query.filter_by(user_id=user.id).update({"user_id": None}, synchronize_session=False)
    db.session.delete(user)
    db.session.add(
        AuditLog(user_id=current_user.id, action="user_delete", details=f"User {user.username}")
    )
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Benutzer konnte nicht gelöscht werden.", "danger")
        return redirect(url_for("users.index"))

    flash("Benutzer gelöscht.", "success")
    return redirect(url_for("users.index"))
