"""enforce shortcode and add profile provider/country fields

Revision ID: 0004_shortcode_backfill_and_profile_provider_fields
Revises: 0003_user_shortcode
Create Date: 2026-04-19
"""

import re

from alembic import op
import sqlalchemy as sa


revision = "0004_shortcode_backfill_and_profile_provider_fields"
down_revision = "0003_user_shortcode"
branch_labels = None
depends_on = None


def _letters_only(value: str | None) -> str:
    return re.sub(r"[^A-Za-z]", "", value or "").upper()


def _generate_shortcode(preferred: str, used: set[str]) -> str:
    candidate = (preferred + "USR")[:3]
    if candidate and candidate not in used and len(candidate) == 3:
        return candidate

    for first in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        for second in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            for third in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
                generated = f"{first}{second}{third}"
                if generated not in used:
                    return generated

    raise RuntimeError("Keine freien 3-Buchstaben-Kürzel mehr verfügbar")


def upgrade():
    op.add_column("profiles", sa.Column("provider", sa.String(length=120), nullable=True))
    op.add_column("profiles", sa.Column("country_code", sa.String(length=2), nullable=True))
    op.add_column("profiles", sa.Column("dial_code", sa.String(length=10), nullable=True))

    bind = op.get_bind()
    meta = sa.MetaData()
    users = sa.Table(
        "users",
        meta,
        sa.Column("id", sa.Integer),
        sa.Column("username", sa.String(80)),
        sa.Column("email", sa.String(120)),
        sa.Column("shortcode", sa.String(3)),
    )

    rows = bind.execute(sa.select(users.c.id, users.c.username, users.c.email, users.c.shortcode)).fetchall()
    used_shortcodes: set[str] = set()

    for row in rows:
        preferred = _letters_only(row.shortcode) or _letters_only(row.username) or _letters_only(row.email)
        preferred = preferred[:3]
        normalized = _generate_shortcode(preferred, used_shortcodes)
        used_shortcodes.add(normalized)

        bind.execute(
            users.update().where(users.c.id == row.id).values(shortcode=normalized)
        )

    op.alter_column("users", "shortcode", existing_type=sa.String(length=3), nullable=False)


def downgrade():
    op.alter_column("users", "shortcode", existing_type=sa.String(length=3), nullable=True)
    op.drop_column("profiles", "dial_code")
    op.drop_column("profiles", "country_code")
    op.drop_column("profiles", "provider")
