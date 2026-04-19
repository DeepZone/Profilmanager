from flask import Blueprint, render_template
from flask_login import current_user, login_required
from sqlalchemy import func

from app.constants.european_countries import get_country_by_iso_code
from app.extensions import db
from app.models import GitLabMergeRequest, Profile, User

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    if current_user.is_admin:
        profile_count = Profile.query.count()
        user_count = User.query.count()
        mr_count = GitLabMergeRequest.query.filter_by(status="opened").count()
        country_counts_query = (
            db.session.query(Profile.country_code, func.count(Profile.id))
            .group_by(Profile.country_code)
            .order_by(func.count(Profile.id).desc())
            .all()
        )
    else:
        profile_count = Profile.query.filter_by(user_id=current_user.id).count()
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

    return render_template(
        "dashboard.html",
        profile_count=profile_count,
        user_count=user_count,
        mr_count=mr_count,
        country_distribution=country_distribution,
    )
