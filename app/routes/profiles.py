import base64
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.constants.european_countries import get_country_by_iso_code
from app.extensions import db
from app.forms import ProfileEditForm, ProfileForm, PushToGitLabForm
from app.models import AuditLog, GitLabMergeRequest, Profile, ProfileFile, Setting
from app.services.gitlab_service import GitLabService, GitLabServiceError
from app.services.repo_structure_service import build_branch_name, build_repo_paths
from app.services.storage_service import StorageService

profiles_bp = Blueprint("profiles", __name__, url_prefix="/profiles")


def _can_access_profile(profile):
    return current_user.is_admin or profile.user_id == current_user.id


def _get_gitlab_service_or_raise():
    url = Setting.query.filter_by(key="gitlab_url").first()
    token = Setting.query.filter_by(key="gitlab_token").first()
    if not url or not url.value or not token or not token.value:
        raise GitLabServiceError("GitLab ist nicht vollständig konfiguriert.")
    return GitLabService(url.value, token.value)


def _get_profile_dependency_counts(profile_id: int) -> dict[str, int]:
    return {
        "dateien": ProfileFile.query.filter_by(profile_id=profile_id).count(),
        "merge_requests": GitLabMergeRequest.query.filter_by(profile_id=profile_id).count(),
    }


def _get_profile_merge_request_status_counts(profile_id: int) -> dict[str, int]:
    opened = GitLabMergeRequest.query.filter_by(profile_id=profile_id, status="opened").count()
    merged = GitLabMergeRequest.query.filter_by(profile_id=profile_id, status="merged").count()
    return {"opened": opened, "merged": merged}


def _get_profile_gitlab_push_context(profile_id: int) -> dict:
    open_mr = (
        GitLabMergeRequest.query.filter_by(profile_id=profile_id, status="opened")
        .order_by(GitLabMergeRequest.created_at.desc())
        .first()
    )
    latest_merged_mr = (
        GitLabMergeRequest.query.filter_by(profile_id=profile_id, status="merged")
        .order_by(GitLabMergeRequest.updated_at.desc())
        .first()
    )
    return {
        "show_push_form": open_mr is None,
        "open_mr": open_mr,
        "latest_merged_mr": latest_merged_mr,
    }


def _get_profile_delete_block_reason(profile: Profile) -> str | None:
    mr_status_counts = _get_profile_merge_request_status_counts(profile.id)
    if mr_status_counts["opened"] > 1:
        return (
            "Profil kann nur gelöscht werden, wenn kein oder nur ein offener Merge Request "
            "vorhanden ist."
        )

    if mr_status_counts["merged"] > 0 and not current_user.is_admin:
        return "Gemergte Profile dürfen nur von einem Admin gelöscht werden."

    return None


def _apply_country_metadata(profile: Profile, selected_iso_code: str) -> None:
    country = get_country_by_iso_code(selected_iso_code)
    if not country:
        raise ValueError("Ungültige Landesvorwahl")

    profile.country_code = country.iso_code
    profile.dial_code = country.dial_code


def _resolve_project_id(explicit_project_id: str | None = None) -> int:
    if explicit_project_id:
        return int(explicit_project_id)

    project_setting = Setting.query.filter_by(key="gitlab_project_id").first()
    if not project_setting or not project_setting.value:
        raise GitLabServiceError("GitLab Projekt-ID fehlt.")
    return int(project_setting.value)


def _push_profile_file_to_gitlab(
    profile: Profile,
    profile_file: ProfileFile,
    commit_message: str,
    mr_title: str,
    project_id: int | None = None,
):
    service = _get_gitlab_service_or_raise()
    resolved_project_id = project_id if project_id is not None else _resolve_project_id()
    branch_name = build_branch_name(
        current_user.shortcode,
        profile.dial_code,
        profile.provider or profile.name,
    )
    target_branch = "main"

    try:
        service.create_branch(resolved_project_id, branch_name, target_branch)
    except GitLabServiceError as exc:
        if "already exists" not in str(exc):
            raise

    with open(profile_file.stored_path, "rb") as file_obj:
        encoded = base64.b64encode(file_obj.read()).decode()

    repo_paths = build_repo_paths(
        profile.dial_code,
        profile.provider or profile.name,
        profile_file.original_filename,
    )

    for directory_key in ("gui_importe", "providerprofile", "tr069_nachlader"):
        keep_file_path = f"{repo_paths[directory_key]}/.gitkeep"
        try:
            service.commit_file(
                resolved_project_id,
                branch_name,
                keep_file_path,
                "",
                f"Ensure folder exists: {repo_paths[directory_key]}",
            )
        except GitLabServiceError as exc:
            if "already exists" not in str(exc):
                raise

    repo_path = repo_paths["upload_path"]
    try:
        service.commit_file(resolved_project_id, branch_name, repo_path, encoded, commit_message)
    except GitLabServiceError:
        service.update_file(resolved_project_id, branch_name, repo_path, encoded, commit_message)

    mr = service.create_merge_request(
        resolved_project_id,
        branch_name,
        target_branch,
        mr_title,
    )
    return mr, resolved_project_id, branch_name, target_branch


def _delete_profile_files_from_git(profile: Profile) -> None:
    files = list(profile.files)
    if not files:
        return

    service = _get_gitlab_service_or_raise()
    project_id = _resolve_project_id()
    repo_paths = {
        build_repo_paths(
            profile.dial_code,
            profile.provider or profile.name,
            profile_file.original_filename,
        )["upload_path"]
        for profile_file in files
    }

    for repo_path in repo_paths:
        try:
            service.delete_file(
                project_id,
                "main",
                repo_path,
                f"Delete profile {profile.name} ({profile.id})",
            )
        except GitLabServiceError as exc:
            error = str(exc).lower()
            if "404" in error or "not found" in error:
                continue
            raise


@profiles_bp.route("/mine")
@login_required
def mine():
    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "updated_at")
    order = request.args.get("order", "desc")
    page = request.args.get("page", 1, type=int)

    query = Profile.query.filter_by(user_id=current_user.id)
    if q:
        query = query.filter(Profile.name.ilike(f"%{q}%"))

    col = getattr(Profile, sort, Profile.updated_at)
    col = col.desc() if order == "desc" else col.asc()
    pagination = query.order_by(col).paginate(page=page, per_page=10)
    return render_template("profiles/mine.html", pagination=pagination, q=q, sort=sort, order=order)


@profiles_bp.route("/all")
@login_required
def all_profiles():
    q = request.args.get("q", "").strip()
    user_id = request.args.get("user_id", type=int)
    page = request.args.get("page", 1, type=int)

    query = Profile.query
    if q:
        query = query.filter(Profile.name.ilike(f"%{q}%"))
    if user_id:
        query = query.filter_by(user_id=user_id)

    pagination = query.order_by(Profile.updated_at.desc()).paginate(page=page, per_page=15)
    return render_template("profiles/all.html", pagination=pagination, q=q, user_id=user_id)


@profiles_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    form = ProfileForm()
    if form.validate_on_submit():
        uploaded_files = [file for file in (form.upload.data or []) if getattr(file, "filename", "")]
        profile = Profile(
            name=form.name.data,
            provider=form.provider.data.strip(),
            description=form.description.data,
            comment=form.comment.data,
            owner=current_user,
            current_version=len(uploaded_files),
        )
        _apply_country_metadata(profile, form.country_code.data)
        db.session.add(profile)
        db.session.flush()

        storage = StorageService(current_app.config["UPLOAD_FOLDER"])
        profile_file = None
        for version, uploaded_file in enumerate(uploaded_files, start=1):
            meta = storage.save_profile_upload(profile.id, version, uploaded_file)
            profile_file = ProfileFile(profile=profile, version=version, **meta)
            db.session.add(profile_file)
        db.session.add(
            AuditLog(
                user_id=current_user.id,
                action="profile_upload",
                details=f"Profil {profile.name} mit {len(uploaded_files)} Datei(en) hochgeladen",
            )
        )
        db.session.commit()

        if form.create_mr.data:
            try:
                mr, project_id, branch_name, target_branch = _push_profile_file_to_gitlab(
                    profile=profile,
                    profile_file=profile_file,
                    commit_message=f"Update profile {profile.name} v{profile_file.version}",
                    mr_title=f"Profile update: {profile.name} v{profile_file.version}",
                )
                db.session.add(
                    GitLabMergeRequest(
                        profile_id=profile.id,
                        created_by=current_user.id,
                        project_id=project_id,
                        branch_name=branch_name,
                        target_branch=target_branch,
                        commit_sha=mr.get("sha"),
                        gitlab_mr_iid=mr["iid"],
                        gitlab_mr_id=mr["id"],
                        title=mr["title"],
                        status=mr["state"],
                        web_url=mr.get("web_url"),
                    )
                )
                db.session.add(
                    AuditLog(
                        user_id=current_user.id,
                        action="gitlab_push",
                        details=f"MR {mr['iid']} für Profil {profile.id} erstellt",
                    )
                )
                db.session.commit()
                flash("Profil erfolgreich hochgeladen und Merge Request erstellt.", "success")
                return redirect(url_for("profiles.detail", profile_id=profile.id))
            except (GitLabServiceError, ValueError, AttributeError) as exc:
                db.session.rollback()
                flash(
                    f"Profil hochgeladen, aber Merge Request konnte nicht erstellt werden: {exc}",
                    "warning",
                )
                return redirect(url_for("profiles.detail", profile_id=profile.id))

        flash("Profil erfolgreich hochgeladen.", "success")
        return redirect(url_for("profiles.mine"))

    return render_template("profiles/upload.html", form=form)


@profiles_bp.route("/<int:profile_id>")
@login_required
def detail(profile_id):
    profile = Profile.query.get_or_404(profile_id)
    if not _can_access_profile(profile):
        abort(403)

    push_form = PushToGitLabForm()
    latest = max(profile.files, key=lambda x: x.version)
    push_form.profile_file_id.data = str(latest.id)
    push_form.branch_name.data = build_branch_name(
        current_user.shortcode,
        profile.dial_code,
        profile.provider or profile.name,
    )
    push_form.commit_message.data = f"Update profile {profile.name} v{latest.version}"
    push_form.mr_title.data = f"Profile update: {profile.name} v{latest.version}"
    push_form.target_branch.data = "main"

    project_setting = Setting.query.filter_by(key="gitlab_project_id").first()
    if project_setting and project_setting.value:
        push_form.project_id.data = project_setting.value

    country = get_country_by_iso_code(profile.country_code)
    dependency_counts = _get_profile_dependency_counts(profile.id)
    gitlab_push_context = _get_profile_gitlab_push_context(profile.id)
    return render_template(
        "profiles/detail.html",
        profile=profile,
        push_form=push_form,
        country=country,
        dependency_counts=dependency_counts,
        gitlab_push_context=gitlab_push_context,
    )


@profiles_bp.route("/<int:profile_id>/download/<int:file_id>")
@login_required
def download(profile_id, file_id):
    profile = Profile.query.get_or_404(profile_id)
    if not _can_access_profile(profile):
        abort(403)

    pf = ProfileFile.query.filter_by(id=file_id, profile_id=profile.id).first_or_404()
    return send_file(pf.stored_path, as_attachment=True, download_name=pf.original_filename)


@profiles_bp.route("/<int:profile_id>/edit", methods=["GET", "POST"])
@login_required
def edit(profile_id):
    profile = Profile.query.get_or_404(profile_id)
    if not _can_access_profile(profile):
        abort(403)

    form = ProfileEditForm(obj=profile)
    if request.method == "GET" and profile.country_code:
        form.country_code.data = profile.country_code

    if form.validate_on_submit():
        uploaded_files = [file for file in (form.upload.data or []) if getattr(file, "filename", "")]
        profile.provider = form.provider.data.strip()
        profile.description = form.description.data
        profile.comment = form.comment.data

        _apply_country_metadata(profile, form.country_code.data)

        if uploaded_files:
            storage = StorageService(current_app.config["UPLOAD_FOLDER"])
            for uploaded_file in uploaded_files:
                profile.current_version += 1
                meta = storage.save_profile_upload(profile.id, profile.current_version, uploaded_file)
                db.session.add(ProfileFile(profile=profile, version=profile.current_version, **meta))

        db.session.add(
            AuditLog(
                user_id=current_user.id,
                action="profile_edit",
                details=f"Profil {profile.id} aktualisiert",
            )
        )
        db.session.commit()
        flash("Profil aktualisiert.", "success")
        return redirect(url_for("profiles.detail", profile_id=profile.id))

    return render_template("profiles/edit.html", profile=profile, form=form)


@profiles_bp.route("/<int:profile_id>/delete", methods=["POST"])
@login_required
def delete(profile_id):
    profile = Profile.query.get_or_404(profile_id)
    if not _can_access_profile(profile):
        abort(403)

    delete_block_reason = _get_profile_delete_block_reason(profile)
    if delete_block_reason:
        flash(delete_block_reason, "danger")
        return redirect(url_for("profiles.detail", profile_id=profile.id))

    delete_dependencies = request.form.get("delete_dependencies") == "1"
    keep_dependencies = request.form.get("keep_dependencies") == "1"
    dependency_counts = _get_profile_dependency_counts(profile.id)
    has_dependencies = any(count > 0 for count in dependency_counts.values())

    if has_dependencies and not delete_dependencies and not keep_dependencies:
        dependencies_text = ", ".join(
            f"{name}: {count}" for name, count in dependency_counts.items() if count > 0
        )
        flash(
            f"Profil hat noch abhängige Daten ({dependencies_text}). "
            "Bitte wähle beim Löschen aus, ob diese ebenfalls gelöscht werden sollen.",
            "warning",
        )
        return redirect(url_for("profiles.detail", profile_id=profile.id))

    if delete_dependencies:
        GitLabMergeRequest.query.filter_by(profile_id=profile.id).delete(synchronize_session=False)
        ProfileFile.query.filter_by(profile_id=profile.id).delete(synchronize_session=False)
    elif keep_dependencies:
        GitLabMergeRequest.query.filter_by(profile_id=profile.id).update(
            {GitLabMergeRequest.profile_id: None}, synchronize_session=False
        )
        ProfileFile.query.filter_by(profile_id=profile.id).update(
            {ProfileFile.profile_id: None}, synchronize_session=False
        )

    try:
        _delete_profile_files_from_git(profile)
    except (GitLabServiceError, ValueError) as exc:
        db.session.rollback()
        flash(f"Profil konnte nicht aus GitLab gelöscht werden: {exc}", "danger")
        return redirect(url_for("profiles.detail", profile_id=profile.id))

    db.session.delete(profile)
    db.session.add(
        AuditLog(
            user_id=current_user.id,
            action="profile_delete",
            details=(
                f"Profil {profile.id} gelöscht "
                f"(abhängige Daten gelöscht: {delete_dependencies}, "
                f"abhängige Daten behalten: {keep_dependencies})"
            ),
        )
    )
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash(
            "Profil konnte nicht gelöscht werden. Bitte prüfe die abhängigen Daten und versuche es erneut.",
            "danger",
        )
        return redirect(url_for("profiles.detail", profile_id=profile.id))

    flash("Profil gelöscht.", "success")
    return redirect(url_for("profiles.mine"))


@profiles_bp.route("/push", methods=["POST"])
@login_required
def push_to_gitlab():
    form = PushToGitLabForm()
    if not form.validate_on_submit():
        flash("Ungültige Eingaben für GitLab Push.", "danger")
        return redirect(request.referrer or url_for("profiles.mine"))

    pf = ProfileFile.query.get_or_404(int(form.profile_file_id.data))
    profile = Profile.query.get_or_404(pf.profile_id)

    if not _can_access_profile(profile):
        abort(403)

    try:
        project_id = _resolve_project_id(form.project_id.data)
        mr, project_id, branch_name, target_branch = _push_profile_file_to_gitlab(
            profile=profile,
            profile_file=pf,
            commit_message=form.commit_message.data,
            mr_title=form.mr_title.data,
            project_id=project_id,
        )

        local_mr = GitLabMergeRequest(
            profile_id=profile.id,
            created_by=current_user.id,
            project_id=project_id,
            branch_name=branch_name,
            target_branch=target_branch,
            commit_sha=mr.get("sha"),
            gitlab_mr_iid=mr["iid"],
            gitlab_mr_id=mr["id"],
            title=mr["title"],
            status=mr["state"],
            web_url=mr.get("web_url"),
        )
        db.session.add(local_mr)
        db.session.add(
            AuditLog(
                user_id=current_user.id,
                action="gitlab_push",
                details=f"MR {mr['iid']} für Profil {profile.id} erstellt",
            )
        )
        db.session.commit()
        flash("Merge Request erfolgreich erstellt.", "success")
    except (GitLabServiceError, ValueError, AttributeError) as exc:
        flash(f"GitLab Fehler: {exc}", "danger")

    return redirect(url_for("profiles.detail", profile_id=profile.id))
