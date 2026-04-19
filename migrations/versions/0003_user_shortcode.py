"""add shortcode to users

Revision ID: 0003_user_shortcode
Revises: 0002_app_version_settings
Create Date: 2026-04-19
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_user_shortcode"
down_revision = "0002_app_version_settings"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("shortcode", sa.String(length=3), nullable=True))
    op.create_unique_constraint("uq_users_shortcode", "users", ["shortcode"])


def downgrade():
    op.drop_constraint("uq_users_shortcode", "users", type_="unique")
    op.drop_column("users", "shortcode")
