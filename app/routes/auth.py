from flask import Blueprint, current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.forms import ForgotPasswordForm, LoginForm, ResetPasswordForm
from app.models import AuditLog, Setting, User
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
        smtp_host=_setting_or_config("mail_server", "MAIL_SERVER"),
        smtp_port=int(_setting_or_config("mail_port", "MAIL_PORT")),
        sender=_resolve_mail_sender(),
        recipient=user.email,
        subject=subject,
        body=body,
        username=_setting_or_config("mail_username", "MAIL_USERNAME"),
        password=_setting_or_config("mail_password", "MAIL_PASSWORD"),
        use_tls=_setting_bool_or_config("mail_use_tls", "MAIL_USE_TLS"),
        use_ssl=_setting_bool_or_config("mail_use_ssl", "MAIL_USE_SSL"),
    )


def _resolve_mail_sender() -> str:
    sender = _setting_or_config("mail_default_sender", "MAIL_DEFAULT_SENDER")
    return sender.strip()


def _resolve_app_base_url() -> str:
    return str(_setting_or_config("app_base_url", "APP_BASE_URL")).rstrip("/")


def _setting_or_config(setting_key: str, config_key: str):
    configured = Setting.query.filter_by(key=setting_key).first()
    if configured and configured.value not in (None, ""):
        return configured.value
    return current_app.config.get(config_key)


def _setting_bool_or_config(setting_key: str, config_key: str) -> bool:
    configured = Setting.query.filter_by(key=setting_key).first()
    if configured and configured.value is not None:
        return configured.value.strip().lower() == "true"
    return bool(current_app.config.get(config_key))


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
            reset_url = _resolve_app_base_url() + url_for("auth.reset_password", token=token)
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
