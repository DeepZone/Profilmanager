"""allow user deletion by nulling dependent references

Revision ID: 0005_user_delete_set_null_refs
Revises: 0004_shortcode_backfill_provider
Create Date: 2026-04-19
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_user_delete_set_null_refs"
down_revision = "0004_shortcode_backfill_provider"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("profiles") as batch_op:
        batch_op.drop_constraint("profiles_user_id_fkey", type_="foreignkey")
        batch_op.alter_column("user_id", existing_type=sa.Integer(), nullable=True)
        batch_op.create_foreign_key(
            "profiles_user_id_fkey", "users", ["user_id"], ["id"], ondelete="SET NULL"
        )

    with op.batch_alter_table("gitlab_merge_requests") as batch_op:
        batch_op.drop_constraint("gitlab_merge_requests_created_by_fkey", type_="foreignkey")
        batch_op.alter_column("created_by", existing_type=sa.Integer(), nullable=True)
        batch_op.create_foreign_key(
            "gitlab_merge_requests_created_by_fkey",
            "users",
            ["created_by"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("audit_log") as batch_op:
        batch_op.drop_constraint("audit_log_user_id_fkey", type_="foreignkey")
        batch_op.alter_column("user_id", existing_type=sa.Integer(), nullable=True)
        batch_op.create_foreign_key(
            "audit_log_user_id_fkey", "users", ["user_id"], ["id"], ondelete="SET NULL"
        )


def downgrade():
    with op.batch_alter_table("audit_log") as batch_op:
        batch_op.drop_constraint("audit_log_user_id_fkey", type_="foreignkey")
        batch_op.alter_column("user_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key("audit_log_user_id_fkey", "users", ["user_id"], ["id"])

    with op.batch_alter_table("gitlab_merge_requests") as batch_op:
        batch_op.drop_constraint("gitlab_merge_requests_created_by_fkey", type_="foreignkey")
        batch_op.alter_column("created_by", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key(
            "gitlab_merge_requests_created_by_fkey", "users", ["created_by"], ["id"]
        )

    with op.batch_alter_table("profiles") as batch_op:
        batch_op.drop_constraint("profiles_user_id_fkey", type_="foreignkey")
        batch_op.alter_column("user_id", existing_type=sa.Integer(), nullable=False)
        batch_op.create_foreign_key("profiles_user_id_fkey", "users", ["user_id"], ["id"])
