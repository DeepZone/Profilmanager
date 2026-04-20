"""add personal gitlab token to users

Revision ID: 0007_user_gitlab_token
Revises: 0006_profile_delete_set_null_ref
Create Date: 2026-04-20
"""

from alembic import op
import sqlalchemy as sa


revision = "0007_user_gitlab_token"
down_revision = "0006_profile_delete_set_null_ref"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("gitlab_token", sa.String(length=255), nullable=True))


def downgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("gitlab_token")
