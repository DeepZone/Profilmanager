import os
import re

from app import create_app
from app.extensions import db
from app.models import Role, User

app = create_app()


def _default_shortcode(username: str, used_shortcodes: set[str]) -> str:
    letters = re.sub(r"[^A-Za-z]", "", username or "").upper() or "USR"
    base = (letters + "USR")[:3]

    if base not in used_shortcodes:
        return base

    for first in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        for second in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            for third in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                candidate = f"{first}{second}{third}"
                if candidate not in used_shortcodes:
                    return candidate

    raise RuntimeError("Kein freies Benutzerkürzel mehr verfügbar")


@app.cli.command("seed-admin")
def seed_admin():
    admin_role = Role.query.filter_by(name="Admin").first()
    user_role = Role.query.filter_by(name="User").first()

    if not admin_role:
        admin_role = Role(name="Admin", description="Administrator")
        db.session.add(admin_role)
    if not user_role:
        user_role = Role(name="User", description="Standardbenutzer")
        db.session.add(user_role)

    db.session.flush()

    username = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
    email = os.getenv("DEFAULT_ADMIN_EMAIL", "admin@example.com")
    password = os.getenv("DEFAULT_ADMIN_PASSWORD", "Admin123!")

    if not User.query.filter_by(username=username).first():
        used_shortcodes = {u.shortcode for u in User.query.filter(User.shortcode.isnot(None)).all()}
        admin = User(
            username=username,
            email=email,
            role=admin_role,
            active=True,
            shortcode=_default_shortcode(username, used_shortcodes),
        )
        admin.set_password(password)
        db.session.add(admin)

    db.session.commit()
    print("Admin-Seed abgeschlossen")
