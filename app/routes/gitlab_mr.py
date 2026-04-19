from sqlalchemy.exc import SQLAlchemyError

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms import DeleteMergeRequestForm, MergeActionForm
from app.models import GitLabMergeRequest, Setting
from app.services.gitlab_service import GitLabService, GitLabServiceError
from app.services.version_service import VersionService

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
    mrs = GitLabMergeRequest.query.order_by(GitLabMergeRequest.created_at.desc()).all()
    return render_template("gitlab/index.html", mrs=mrs)


@gitlab_bp.route("/<int:mr_id>", methods=["GET", "POST"])
@login_required
def detail(mr_id):
    mr = GitLabMergeRequest.query.get_or_404(mr_id)

    merge_form = MergeActionForm(prefix="merge")
    delete_form = DeleteMergeRequestForm(prefix="delete")
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

    can_delete = current_user.is_admin or mr.created_by == current_user.id

    if request.method == "POST" and merge_form.submit.data and merge_form.validate():
        if details and not details.get("user", {}).get("can_merge", False):
            abort(403)
        try:
            service = _service()
            merge = service.merge_request(
                mr.project_id, mr.gitlab_mr_iid, squash=merge_form.squash.data
            )
            merged_successfully = merge.get("state") == "merged"
            mr.status = merge.get("state", "merged")

            if merged_successfully:
                VersionService.increment_build(
                    user_id=current_user.id,
                    reason=f"merge_request_{mr.gitlab_mr_iid}",
                )
            else:
                db.session.commit()

            flash("Merge erfolgreich ausgeführt.", "success")
        except GitLabServiceError as exc:
            flash(f"Merge fehlgeschlagen: {exc}", "danger")
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception(
                "Merge erfolgreich in GitLab, aber lokales Update fehlgeschlagen (mr_id=%s)",
                mr.id,
            )
            flash(
                "Merge in GitLab war erfolgreich, aber die lokale Speicherung inkl. Build-Erhöhung ist fehlgeschlagen.",
                "warning",
            )
        return redirect(url_for("gitlab.detail", mr_id=mr.id))

    if request.method == "POST" and delete_form.submit.data and delete_form.validate():
        if not can_delete:
            abort(403)
        try:
            service = _service()
            service.delete_merge_request(mr.project_id, mr.gitlab_mr_iid)
            db.session.delete(mr)
            db.session.commit()
            flash("Merge Request wurde gelöscht.", "success")
            return redirect(url_for("gitlab.index"))
        except GitLabServiceError as exc:
            db.session.rollback()
            flash(f"Löschen fehlgeschlagen: {exc}", "danger")
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("Lokales Löschen fehlgeschlagen (mr_id=%s)", mr.id)
            flash("Merge Request konnte lokal nicht gelöscht werden.", "danger")

    return render_template(
        "gitlab/detail.html",
        mr=mr,
        details=details,
        changes=changes,
        error=error,
        merge_form=merge_form,
        delete_form=delete_form,
        can_delete=can_delete,
        can_merge=details.get("user", {}).get("can_merge", True) if details else False,
    )
