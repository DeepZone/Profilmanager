from flask import Blueprint, abort, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.decorators import admin_required
from app.extensions import db
from app.forms import MergeActionForm
from app.models import GitLabMergeRequest, Profile, Setting
from app.services.gitlab_service import GitLabService, GitLabServiceError

gitlab_bp = Blueprint("gitlab", __name__, url_prefix="/merge-requests")


def _service():
    url = Setting.query.filter_by(key="gitlab_url").first()
    token = Setting.query.filter_by(key="gitlab_token").first()
    if not url or not token or not url.value or not token.value:
        raise GitLabServiceError("GitLab Konfiguration fehlt")
    return GitLabService(url.value, token.value)


@gitlab_bp.route("/")
@login_required
def index():
    if current_user.is_admin:
        mrs = GitLabMergeRequest.query.order_by(GitLabMergeRequest.created_at.desc()).all()
    else:
        mrs = (
            GitLabMergeRequest.query.join(Profile)
            .filter(Profile.user_id == current_user.id)
            .order_by(GitLabMergeRequest.created_at.desc())
            .all()
        )
    return render_template("gitlab/index.html", mrs=mrs)


@gitlab_bp.route("/<int:mr_id>", methods=["GET", "POST"])
@login_required
def detail(mr_id):
    mr = GitLabMergeRequest.query.get_or_404(mr_id)
    if not current_user.is_admin and mr.profile.user_id != current_user.id:
        abort(403)

    form = MergeActionForm()
    details = None
    changes = []
    error = None

    try:
        service = _service()
        details = service.get_merge_request(mr.project_id, mr.gitlab_mr_iid)
        diff_payload = service.get_merge_request_changes(mr.project_id, mr.gitlab_mr_iid)
        changes = diff_payload.get("changes", [])
    except GitLabServiceError as exc:
        error = str(exc)

    if form.validate_on_submit():
        if not current_user.is_admin:
            abort(403)
        try:
            service = _service()
            merge = service.merge_request(mr.project_id, mr.gitlab_mr_iid, squash=form.squash.data)
            mr.status = merge.get("state", "merged")
            db.session.commit()
            flash("Merge erfolgreich ausgeführt.", "success")
        except GitLabServiceError as exc:
            flash(f"Merge fehlgeschlagen: {exc}", "danger")
        return redirect(url_for("gitlab.detail", mr_id=mr.id))

    return render_template(
        "gitlab/detail.html", mr=mr, details=details, changes=changes, error=error, form=form
    )
