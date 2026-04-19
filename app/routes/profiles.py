import base64
from datetime import datetime

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.extensions import db
from app.forms import ProfileEditForm, ProfileForm, PushToGitLabForm
from app.models import AuditLog, Profile, ProfileFile, Setting, GitLabMergeRequest
from app.services.gitlab_service import GitLabService, GitLabServiceError
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
        profile = Profile(
            name=form.name.data,
            description=form.description.data,
            comment=form.comment.data,
            owner=current_user,
            current_version=1,
        )
        db.session.add(profile)
        db.session.flush()

        storage = StorageService(current_app.config["UPLOAD_FOLDER"])
        meta = storage.save_profile_tar(profile.id, 1, form.upload.data)

        profile_file = ProfileFile(profile=profile, version=1, **meta)
        db.session.add(profile_file)
        db.session.add(
            AuditLog(
                user_id=current_user.id,
                action="profile_upload",
                details=f"Profil {profile.name} v1 hochgeladen",
            )
        )
        db.session.commit()
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
    push_form.branch_name.data = f"profile/{profile.id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    push_form.commit_message.data = f"Update profile {profile.name} v{latest.version}"
    push_form.mr_title.data = f"Profile update: {profile.name} v{latest.version}"

    project_setting = Setting.query.filter_by(key="gitlab_project_id").first()
    if project_setting and project_setting.value:
        push_form.project_id.data = project_setting.value

    return render_template("profiles/detail.html", profile=profile, push_form=push_form)


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
    if form.validate_on_submit():
        profile.description = form.description.data
        profile.comment = form.comment.data

        if form.upload.data:
            profile.current_version += 1
            storage = StorageService(current_app.config["UPLOAD_FOLDER"])
            meta = storage.save_profile_tar(profile.id, profile.current_version, form.upload.data)
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
        service = _get_gitlab_service_or_raise()
        project_id = int(form.project_id.data) if form.project_id.data else int(
            Setting.query.filter_by(key="gitlab_project_id").first().value
        )

        try:
            service.create_branch(project_id, form.branch_name.data, form.target_branch.data)
        except GitLabServiceError as exc:
            if "already exists" not in str(exc):
                raise

        with open(pf.stored_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode()

        repo_path = f"profiles/user_{profile.user_id}/{profile.name}/v{pf.version}.tar"
        try:
            service.commit_file(
                project_id, form.branch_name.data, repo_path, encoded, form.commit_message.data
            )
        except GitLabServiceError:
            service.update_file(
                project_id, form.branch_name.data, repo_path, encoded, form.commit_message.data
            )

        mr = service.create_merge_request(
            project_id,
            form.branch_name.data,
            form.target_branch.data,
            form.mr_title.data,
        )

        local_mr = GitLabMergeRequest(
            profile_id=profile.id,
            created_by=current_user.id,
            project_id=project_id,
            branch_name=form.branch_name.data,
            target_branch=form.target_branch.data,
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
