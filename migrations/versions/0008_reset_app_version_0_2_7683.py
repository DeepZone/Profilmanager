"""set app version baseline to 0.2.7683

Revision ID: 0008_reset_app_version_0_2_7683
Revises: 0007_user_gitlab_token
Create Date: 2026-04-20
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_reset_app_version_0_2_7683"
down_revision = "0007_user_gitlab_token"
branch_labels = None
depends_on = None


def _upsert_setting(connection, key: str, value: str):
    settings = sa.table(
        "settings",
        sa.column("key", sa.String(length=120)),
        sa.column("value", sa.Text()),
        sa.column("updated_at", sa.DateTime()),
    )

    exists = connection.execute(
        sa.select(settings.c.key).where(settings.c.key == key).limit(1)
    ).first()

    if exists:
        connection.execute(
            settings.update()
            .where(settings.c.key == key)
            .values(value=value, updated_at=sa.func.now())
        )
    else:
        connection.execute(
            settings.insert().values(key=key, value=value, updated_at=sa.func.now())
        )


def upgrade():
    connection = op.get_bind()
    _upsert_setting(connection, "app_version_major", "0")
    _upsert_setting(connection, "app_version_minor", "2")
    _upsert_setting(connection, "app_version_build", "7683")


def downgrade():
    connection = op.get_bind()
    _upsert_setting(connection, "app_version_major", "1")
    _upsert_setting(connection, "app_version_minor", "1")
    _upsert_setting(connection, "app_version_build", "0")
