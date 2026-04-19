from sqlalchemy.exc import IntegrityError
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.decorators import admin_required
from app.extensions import db
from app.forms import SelfProfileForm, UserForm
from app.models import AuditLog, Role, User

users_bp = Blueprint("users", __name__, url_prefix="/users")


def _normalize_shortcode(value: str) -> str:
    return (value or "").strip().lower()


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
    form.submit.render_kw = {"disabled": True}
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
        submitted_shortcode = _normalize_shortcode(form.shortcode.data)

        if user.id == current_user.id and user.shortcode != submitted_shortcode:
            flash("Kein User darf sein eigenes Kürzel ändern", "danger")
            return render_template("users/form.html", form=form, title="Benutzer bearbeiten")

        user.username = form.username.data
        user.email = form.email.data
        user.active = form.active.data
        user.role = role
        user.shortcode = submitted_shortcode
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

    db.session.delete(user)
    db.session.add(
        AuditLog(user_id=current_user.id, action="user_delete", details=f"User {user.username}")
    )
    db.session.commit()
    flash("Benutzer gelöscht.", "success")
    return redirect(url_for("users.index"))
