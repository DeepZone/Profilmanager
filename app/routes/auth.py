from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.forms import LoginForm
from app.models import AuditLog, User
from app.extensions import db

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.active and user.check_password(form.password.data):
            login_user(user)
            db.session.add(AuditLog(user_id=user.id, action="login", details="Benutzer Login"))
            db.session.commit()
            return redirect(url_for("dashboard.index"))
        flash("Ungültige Anmeldedaten oder Benutzer deaktiviert.", "danger")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    db.session.add(AuditLog(user_id=current_user.id, action="logout", details="Benutzer Logout"))
    db.session.commit()
    logout_user()
    flash("Erfolgreich abgemeldet.", "success")
    return redirect(url_for("auth.login"))
