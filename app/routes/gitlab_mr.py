from sqlalchemy.exc import SQLAlchemyError

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms import (
    DeleteMergeRequestForm,
    MainBranchActionForm,
    MainBranchDeletePathForm,
    MergeActionForm,
)
from app.models import GitLabMergeRequest, Setting
from app.services.gitlab_service import GitLabService, GitLabServiceError
from app.services.version_service import VersionService

gitlab_bp = Blueprint("gitlab", __name__, url_prefix="/merge-requests")


def _merge_was_successful(merge_response: dict) -> bool:
    if merge_response.get("state") == "merged":
        return True

    # Einige GitLab-Instanzen liefern nach dem Merge nicht sofort state=merged,
    # setzen aber bereits merged_at oder merge_commit_sha.
    return bool(merge_response.get("merged_at") or merge_response.get("merge_commit_sha"))


def _service():
    url = Setting.query.filter_by(key="gitlab_url").first()
    token = Setting.query.filter_by(key="gitlab_token").first()
    if not url or not token or not url.value or not token.value:
        raise GitLabServiceError("GitLab Konfiguration fehlt")
    return GitLabService(url.value, token.value)


@gitlab_bp.route("/")
@login_required
def index():
    mrs = (
        GitLabMergeRequest.query.filter_by(status="opened")
        .order_by(GitLabMergeRequest.created_at.desc())
        .all()
    )
    return render_template("gitlab/index.html", mrs=mrs)


def _distinct_project_ids() -> list[int]:
    project_ids = {
        project_id
        for (project_id,) in db.session.query(GitLabMergeRequest.project_id).distinct().all()
        if project_id
    }

    default_project = Setting.query.filter_by(key="gitlab_project_id").first()
    if default_project and default_project.value:
        try:
            project_ids.add(int(default_project.value))
        except ValueError:
            current_app.logger.warning(
                "Ungültige gitlab_project_id in Settings: %s", default_project.value
            )

    return sorted(project_ids)


def _collect_main_profiles(tree_entries: list[dict]) -> list[dict]:
    profiles: dict[str, dict] = {}
    for entry in tree_entries:
        path = (entry or {}).get("path") or ""
        parts = path.split("/")
        if len(parts) < 2 or not parts[0].startswith("providers-"):
            continue

        profile_root = f"{parts[0]}/{parts[1]}"
        profile_data = profiles.setdefault(
            profile_root,
            {
                "path": profile_root,
                "dial_code": parts[0].removeprefix("providers-"),
                "provider": parts[1],
                "file_count": 0,
            },
        )

        if (entry or {}).get("type") == "blob":
            profile_data["file_count"] += 1

    return sorted(profiles.values(), key=lambda profile: profile["path"].lower())


def _collect_files_for_delete(tree_entries: list[dict], target_path: str, entry_type: str) -> list[str]:
    normalized_target = (target_path or "").strip().strip("/")
    if not normalized_target:
        return []

    if entry_type == "blob":
        return [normalized_target]

    prefix = f"{normalized_target}/"
    return sorted(
        {
            (entry or {}).get("path")
            for entry in tree_entries
            if (entry or {}).get("type") == "blob"
            and (
                ((entry or {}).get("path") == normalized_target)
                or ((entry or {}).get("path") or "").startswith(prefix)
            )
        }
    )


@gitlab_bp.route("/main-branch", methods=["GET", "POST"])
@login_required
def main_branch():
    form = MainBranchActionForm(prefix="main")
    delete_form = MainBranchDeletePathForm(prefix="main_delete")
    action_labels = {"merge": "Merge", "close": "Schließen", "reopen": "Wiederöffnen"}

    if request.method == "POST" and form.submit.data and not form.validate():
        flash("Aktion konnte nicht ausgeführt werden. Bitte Formularangaben prüfen.", "danger")
        return redirect(url_for("gitlab.main_branch"))

    if request.method == "POST" and form.submit.data and form.validate():
        action = form.action.data
        if action not in action_labels:
            abort(400)

        try:
            project_id = int(form.project_id.data)
            mr_iid = int(form.mr_iid.data)
        except (TypeError, ValueError):
            abort(400)

        try:
            service = _service()
            branch = service.get_branch(project_id, "main")
            if not branch.get("can_push", False):
                abort(403)

            if action == "merge":
                service.merge_request(project_id, mr_iid, squash=False)
            else:
                service.change_merge_request_state(project_id, mr_iid, action)

            flash(f"{action_labels[action]} für MR !{mr_iid} wurde ausgeführt.", "success")
        except GitLabServiceError as exc:
            flash(f"Aktion fehlgeschlagen: {exc}", "danger")

        return redirect(url_for("gitlab.main_branch"))

    if request.method == "POST" and delete_form.submit.data and not delete_form.validate():
        flash("Löschen konnte nicht ausgeführt werden. Bitte Anfrage erneut senden.", "danger")
        return redirect(url_for("gitlab.main_branch"))

    if request.method == "POST" and delete_form.submit.data and delete_form.validate():
        try:
            project_id = int(delete_form.project_id.data)
        except (TypeError, ValueError):
            abort(400)

        target_path = (delete_form.path.data or "").strip()
        entry_type = (delete_form.entry_type.data or "").strip()
        if entry_type not in {"blob", "tree"}:
            abort(400)
        if not target_path:
            abort(400)

        try:
            service = _service()
            branch = service.get_branch(project_id, "main")
            if not branch.get("can_push", False):
                abort(403)

            tree_entries = service.list_repository_tree(project_id, ref="main", recursive=True)
            file_paths = _collect_files_for_delete(tree_entries, target_path, entry_type)
            if not file_paths:
                flash(f"Unterhalb von {target_path} wurden keine löschbaren Dateien gefunden.", "warning")
                return redirect(url_for("gitlab.main_branch"))

            service.create_commit(
                project_id,
                "main",
                f"Main-Branch Verwaltung: Lösche {target_path}",
                [{"action": "delete", "file_path": file_path} for file_path in file_paths],
            )
            flash(f"{target_path} wurde aus main gelöscht ({len(file_paths)} Datei(en)).", "success")
        except GitLabServiceError as exc:
            flash(f"Löschen fehlgeschlagen: {exc}", "danger")

        return redirect(url_for("gitlab.main_branch"))

    projects = []
    error = None

    try:
        service = _service()
        for project_id in _distinct_project_ids():
            branch = service.get_branch(project_id, "main")
            merge_requests = service.list_merge_requests(project_id, state="opened", target_branch="main")
            tree_entries = service.list_repository_tree(project_id, ref="main", recursive=True)
            projects.append(
                {
                    "project_id": project_id,
                    "branch": branch,
                    "can_admin_main": branch.get("can_push", False),
                    "merge_requests": merge_requests,
                    "tree_entries": tree_entries,
                    "profiles": _collect_main_profiles(tree_entries),
                }
            )
    except GitLabServiceError as exc:
        error = str(exc)

    return render_template(
        "gitlab/main_branch.html",
        projects=projects,
        error=error,
        form=form,
        delete_form=delete_form,
    )


@gitlab_bp.route("/main-branch/merge-request-archiv")
@login_required
def main_branch_mr_archive():
    projects = []
    error = None

    try:
        service = _service()
        for project_id in _distinct_project_ids():
            archive_requests = [
                mr
                for mr in service.list_merge_requests(project_id, state="all", target_branch="main")
                if mr.get("state") != "opened"
            ]
            projects.append({"project_id": project_id, "merge_requests": archive_requests})
    except GitLabServiceError as exc:
        error = str(exc)

    return render_template("gitlab/main_branch_mr_archive.html", projects=projects, error=error)


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
            merged_successfully = _merge_was_successful(merge)
            mr.status = "merged" if merged_successfully else merge.get("state", "opened")

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
