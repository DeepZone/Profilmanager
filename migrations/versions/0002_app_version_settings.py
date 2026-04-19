"""add app version settings

Revision ID: 0002_app_version_settings
Revises: 0001_initial
Create Date: 2026-04-19
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_app_version_settings"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def _insert_setting_if_missing(connection, key: str, value: str):
    settings = sa.table(
        "settings",
        sa.column("key", sa.String(length=120)),
        sa.column("value", sa.Text()),
        sa.column("updated_at", sa.DateTime()),
    )

    exists = connection.execute(
        sa.select(settings.c.key).where(settings.c.key == key).limit(1)
    ).first()
    if not exists:
        connection.execute(
            settings.insert().values(key=key, value=value, updated_at=sa.func.now())
        )


def upgrade():
    connection = op.get_bind()
    _insert_setting_if_missing(connection, "app_version_major", "1")
    _insert_setting_if_missing(connection, "app_version_minor", "1")
    _insert_setting_if_missing(connection, "app_version_build", "0")


def downgrade():
    connection = op.get_bind()
    settings = sa.table("settings", sa.column("key", sa.String(length=120)))
    connection.execute(
        settings.delete().where(
            settings.c.key.in_([
                "app_version_major",
                "app_version_minor",
                "app_version_build",
            ])
        )
    )
