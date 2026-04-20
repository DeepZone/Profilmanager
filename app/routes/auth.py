from flask import Blueprint, current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.forms import ForgotPasswordForm, LoginForm, ResetPasswordForm
from app.models import AuditLog, User
from app.extensions import db
from app.services.email_service import EmailService
from app.services.reset_password_service import ResetPasswordService

auth_bp = Blueprint("auth", __name__)


def _send_reset_mail(user: User, reset_url: str) -> None:
    subject = "Passwort zurücksetzen"
    body = (
        f"Hallo {user.username},\n\n"
        "über den folgenden Link kannst du dein Passwort zurücksetzen:\n"
        f"{reset_url}\n\n"
        "Wenn du das nicht angefordert hast, kannst du diese E-Mail ignorieren."
    )

    EmailService.send_mail(
        smtp_host=current_app.config["MAIL_SERVER"],
        smtp_port=current_app.config["MAIL_PORT"],
        sender=current_app.config["MAIL_DEFAULT_SENDER"],
        recipient=user.email,
        subject=subject,
        body=body,
        username=current_app.config.get("MAIL_USERNAME"),
        password=current_app.config.get("MAIL_PASSWORD"),
        use_tls=current_app.config["MAIL_USE_TLS"],
        use_ssl=current_app.config["MAIL_USE_SSL"],
    )


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


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = ForgotPasswordForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        if user and user.active and current_app.config["MAIL_ENABLED"]:
            token = ResetPasswordService.create_token(current_app.config["SECRET_KEY"], user.id)
            reset_url = f"{current_app.config['APP_BASE_URL'].rstrip('/')}" + url_for(
                "auth.reset_password", token=token
            )
            try:
                _send_reset_mail(user, reset_url)
                db.session.add(
                    AuditLog(
                        user_id=user.id,
                        action="password_reset_requested",
                        details="Passwort-Reset-Link angefordert",
                    )
                )
                db.session.commit()
            except Exception:
                current_app.logger.exception("Senden der Reset-E-Mail fehlgeschlagen")

        flash(
            "Wenn die E-Mail-Adresse existiert, wurde ein Link zum Zurücksetzen versendet.",
            "info",
        )
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html", form=form)


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    user_id = ResetPasswordService.resolve_user_id(
        secret_key=current_app.config["SECRET_KEY"],
        token=token,
        max_age_seconds=current_app.config["RESET_PASSWORD_TOKEN_MAX_AGE"],
    )

    if not user_id:
        flash("Der Link ist ungültig oder abgelaufen.", "danger")
        return redirect(url_for("auth.forgot_password"))

    user = User.query.get(user_id)
    if not user or not user.active:
        flash("Der Link ist ungültig oder abgelaufen.", "danger")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.add(
            AuditLog(user_id=user.id, action="password_reset_done", details="Passwort via Reset-Link geändert")
        )
        db.session.commit()
        flash("Passwort erfolgreich geändert. Du kannst dich jetzt anmelden.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/reset_password.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    db.session.add(AuditLog(user_id=current_user.id, action="logout", details="Benutzer Logout"))
    db.session.commit()
    logout_user()
    flash("Erfolgreich abgemeldet.", "success")
    return redirect(url_for("auth.login"))
