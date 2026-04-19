"""allow profile deletion by nulling dependent references

Revision ID: 0006_profile_delete_set_null_ref
Revises: 0005_user_delete_set_null_refs
Create Date: 2026-04-19
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_profile_delete_set_null_ref"
down_revision = "0005_user_delete_set_null_refs"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("profile_files") as batch_op:
        batch_op.drop_constraint("profile_files_profile_id_fkey", type_="foreignkey")
        batch_op.alter_column("profile_id", existing_type=sa.Integer(), nullable=True)
        batch_op.create_foreign_key(
            "profile_files_profile_id_fkey", "profiles", ["profile_id"], ["id"], ondelete="SET NULL"
        )

    with op.batch_alter_table("gitlab_merge_requests") as batch_op:
        batch_op.drop_constraint("gitlab_merge_requests_profile_id_fkey", type_="foreignkey")
        batch_op.alter_column("profile_id", existing_type=sa.Integer(), nullable=True)
        batch_op.create_foreign_key(
            "gitlab_merge_requests_profile_id_fkey",
            "profiles",
            ["profile_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade():
    with op.batch_alter_table("gitlab_merge_requests") as batch_op:
        batch_op.drop_constraint("gitlab_merge_requests_profile_id_fkey", type_="foreignkey")
        batch_op.alter_column("profile_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            "gitlab_merge_requests_profile_id_fkey", "profiles", ["profile_id"], ["id"]
        )

    with op.batch_alter_table("profile_files") as batch_op:
        batch_op.drop_constraint("profile_files_profile_id_fkey", type_="foreignkey")
        batch_op.alter_column("profile_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key("profile_files_profile_id_fkey", "profiles", ["profile_id"], ["id"])
