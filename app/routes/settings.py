from flask import Blueprint, current_app, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.decorators import admin_required
from app.extensions import db
from app.forms import GeneralSettingsForm, GitLabConfigForm
from app.models import AuditLog, Setting
from app.services.gitlab_service import GitLabService, GitLabServiceError

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


@settings_bp.route("", methods=["GET", "POST"])
@login_required
@admin_required
def index():
    form = GeneralSettingsForm()

    if form.validate_on_submit():
        mail_password = (form.mail_password.data or "").strip()
        _save_setting("mail_default_sender", form.mail_default_sender.data.strip())
        _save_setting("app_base_url", form.app_base_url.data.strip())
        _save_setting("mail_server", form.mail_server.data.strip())
        _save_setting("mail_port", form.mail_port.data.strip())
        _save_setting("mail_username", (form.mail_username.data or "").strip())
        _save_setting("mail_use_tls", "true" if form.mail_use_tls.data else "false")
        _save_setting("mail_use_ssl", "true" if form.mail_use_ssl.data else "false")
        if mail_password:
            _save_setting("mail_password", mail_password)

        db.session.add(
            AuditLog(
                user_id=current_user.id,
                action="settings_update",
                details="Allgemeine Einstellungen geändert",
            )
        )
        db.session.commit()
        flash("Einstellungen gespeichert.", "success")
        return redirect(url_for("settings.index"))

    form.app_base_url.data = _setting_or_config("app_base_url", "APP_BASE_URL")
    form.mail_default_sender.data = _setting_or_config("mail_default_sender", "MAIL_DEFAULT_SENDER")
    form.mail_server.data = _setting_or_config("mail_server", "MAIL_SERVER")
    form.mail_port.data = str(_setting_or_config("mail_port", "MAIL_PORT"))
    form.mail_username.data = _setting_or_config("mail_username", "MAIL_USERNAME")
    form.mail_password.data = ""
    form.mail_use_tls.data = _setting_bool_or_config("mail_use_tls", "MAIL_USE_TLS")
    form.mail_use_ssl.data = _setting_bool_or_config("mail_use_ssl", "MAIL_USE_SSL")

    return render_template("settings/index.html", form=form)


@settings_bp.route("/gitlab", methods=["GET", "POST"])
@login_required
@admin_required
def gitlab():
    form = GitLabConfigForm()

    current_url = Setting.query.filter_by(key="gitlab_url").first()
    current_project = Setting.query.filter_by(key="gitlab_project_id").first()
    if form.validate_on_submit():
        _save_setting("gitlab_url", form.gitlab_url.data)
        _save_setting("gitlab_project_id", form.gitlab_project_id.data)

        db.session.add(
            AuditLog(user_id=current_user.id, action="gitlab_config", details="GitLab-Konfig geändert")
        )
        db.session.commit()
        flash("GitLab-Konfiguration gespeichert.", "success")
        return redirect(url_for("settings.gitlab"))

    if current_url:
        form.gitlab_url.data = current_url.value
    if current_project:
        form.gitlab_project_id.data = current_project.value

    return render_template("settings/gitlab.html", form=form)


@settings_bp.route("/gitlab/test", methods=["POST"])
@login_required
@admin_required
def test_gitlab():
    url = Setting.query.filter_by(key="gitlab_url").first()
    token = (current_user.gitlab_token or "").strip()

    if not url or not url.value or not token:
        flash("GitLab URL und persönlicher API Token im Benutzerprofil müssen gesetzt sein.", "danger")
        return redirect(url_for("settings.gitlab"))

    try:
        service = GitLabService(url.value, token)
        user = service.test_connection()
        flash(f"Verbindung erfolgreich. Eingeloggt als {user.get('username')}", "success")
    except GitLabServiceError as exc:
        flash(f"Verbindung fehlgeschlagen: {exc}", "danger")

    return redirect(url_for("settings.gitlab"))


def _save_setting(key, value):
    setting = Setting.query.filter_by(key=key).first()
    if setting:
        setting.value = value
    else:
        db.session.add(Setting(key=key, value=value))


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
