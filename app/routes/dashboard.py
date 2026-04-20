from flask import Blueprint, render_template
from flask_login import current_user, login_required
from sqlalchemy import func

from app.constants.european_countries import get_country_by_iso_code
from app.extensions import db
from app.models import GitLabMergeRequest, Profile, Setting, User
from app.services.gitlab_service import GitLabService, GitLabServiceError

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    total_profile_count = Profile.query.count()
    my_profile_count = Profile.query.filter_by(user_id=current_user.id).count()

    if current_user.is_admin:
        user_count = User.query.count()
        mr_count = GitLabMergeRequest.query.filter_by(status="opened").count()
        country_counts_query = (
            db.session.query(Profile.country_code, func.count(Profile.id))
            .group_by(Profile.country_code)
            .order_by(func.count(Profile.id).desc())
            .all()
        )
    else:
        user_count = None
        mr_count = (
            GitLabMergeRequest.query.join(Profile)
            .filter(Profile.user_id == current_user.id)
            .filter(GitLabMergeRequest.status == "opened")
            .count()
        )
        country_counts_query = (
            db.session.query(Profile.country_code, func.count(Profile.id))
            .filter(Profile.user_id == current_user.id)
            .group_by(Profile.country_code)
            .order_by(func.count(Profile.id).desc())
            .all()
        )

    country_distribution = []
    for country_code, count in country_counts_query:
        country = get_country_by_iso_code(country_code)
        if country:
            label = f"{country.flag_emoji} {country.country_name}"
        elif country_code:
            label = country_code
        else:
            label = "Ohne Land"
        country_distribution.append({"label": label, "count": count})

    gitlab_url = Setting.query.filter_by(key="gitlab_url").first()
    token = (current_user.gitlab_token or "").strip()
    gitlab_status = {
        "label": "Nicht verbunden",
        "state": "danger",
        "message": "Kein persönlicher API-Token hinterlegt.",
    }
    if gitlab_url and gitlab_url.value and token:
        try:
            service = GitLabService(gitlab_url.value, token)
            service.test_connection()
            gitlab_status = {
                "label": "Verbunden",
                "state": "success",
                "message": "GitLab-Verbindung ist aktiv.",
            }
        except GitLabServiceError as exc:
            gitlab_status = {
                "label": "Fehler",
                "state": "danger",
                "message": f"GitLab-Verbindung fehlgeschlagen: {exc}",
            }
    elif not gitlab_url or not gitlab_url.value:
        gitlab_status = {
            "label": "Nicht konfiguriert",
            "state": "warning",
            "message": "GitLab-URL ist nicht gesetzt.",
        }

    user_info = {
        "username": current_user.username,
        "shortcode": current_user.shortcode,
        "role": current_user.role.name if current_user.role else "-",
        "gitlab_status": gitlab_status,
    }

    return render_template(
        "dashboard.html",
        total_profile_count=total_profile_count,
        my_profile_count=my_profile_count,
        user_count=user_count,
        mr_count=mr_count,
        country_distribution=country_distribution,
        user_info=user_info,
    )
