from flask import Blueprint, render_template
from flask_login import current_user, login_required

from app.models import GitLabMergeRequest, Profile, User

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    if current_user.is_admin:
        profile_count = Profile.query.count()
        user_count = User.query.count()
        mr_count = GitLabMergeRequest.query.count()
    else:
        profile_count = Profile.query.filter_by(user_id=current_user.id).count()
        user_count = None
        mr_count = (
            GitLabMergeRequest.query.join(Profile)
            .filter(Profile.user_id == current_user.id)
            .count()
        )

    return render_template(
        "dashboard.html",
        profile_count=profile_count,
        user_count=user_count,
        mr_count=mr_count,
    )
