from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.decorators import admin_required
from app.extensions import db
from app.forms import AppVersionMajorForm, AppVersionMinorForm, GitLabConfigForm
from app.models import AuditLog, Setting
from app.services.gitlab_service import GitLabService, GitLabServiceError
from app.services.version_service import VersionService, VersionServiceError

settings_bp = Blueprint("settings", __name__, url_prefix="/settings")


@settings_bp.route("/gitlab", methods=["GET", "POST"])
@login_required
@admin_required
def gitlab():
    form = GitLabConfigForm()
    major_form = AppVersionMajorForm(prefix="major")
    minor_form = AppVersionMinorForm(prefix="minor")

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

    version = VersionService.get_version()
    major_form.major.data = version.major
    minor_form.minor.data = version.minor

    return render_template(
        "settings/gitlab.html",
        form=form,
        current_version=version.as_string(),
        major_form=major_form,
        minor_form=minor_form,
    )


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


@settings_bp.route("/version/major", methods=["POST"])
@login_required
@admin_required
def set_major_version():
    form = AppVersionMajorForm(prefix="major")
    if not form.validate_on_submit():
        flash("Ungültiger Wert für MAJOR.", "danger")
        return redirect(url_for("settings.gitlab"))

    try:
        new_version = VersionService.set_major(form.major.data, user_id=current_user.id)
        flash(f"Hauptversion wurde auf {new_version.as_string()} gesetzt.", "success")
    except VersionServiceError as exc:
        flash(f"Version konnte nicht gesetzt werden: {exc}", "danger")

    return redirect(url_for("settings.gitlab"))


@settings_bp.route("/version/minor", methods=["POST"])
@login_required
@admin_required
def set_minor_version():
    form = AppVersionMinorForm(prefix="minor")
    if not form.validate_on_submit():
        flash("Ungültiger Wert für MINOR.", "danger")
        return redirect(url_for("settings.gitlab"))

    try:
        new_version = VersionService.set_minor(form.minor.data, user_id=current_user.id)
        flash(f"Subversion wurde auf {new_version.as_string()} gesetzt.", "success")
    except VersionServiceError as exc:
        flash(f"Version konnte nicht gesetzt werden: {exc}", "danger")

    return redirect(url_for("settings.gitlab"))


def _save_setting(key, value):
    setting = Setting.query.filter_by(key=key).first()
    if setting:
        setting.value = value
    else:
        db.session.add(Setting(key=key, value=value))
