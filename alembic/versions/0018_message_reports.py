"""allow reports to target messages"""

import sqlalchemy as sa

from alembic import op

revision = "0018_message_reports"
down_revision = "0017_user_blocks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reports", sa.Column("message_id", sa.UUID(), nullable=True))
    op.create_foreign_key("fk_reports_message_id_messages", "reports", "messages", ["message_id"], ["id"], ondelete="CASCADE")
    op.drop_constraint("ck_reports_one_target", "reports", type_="check")
    op.create_check_constraint(
        "ck_reports_one_target",
        "(post_id IS NOT NULL AND comment_id IS NULL AND message_id IS NULL) OR (post_id IS NULL AND comment_id IS NOT NULL AND message_id IS NULL) OR (post_id IS NULL AND comment_id IS NULL AND message_id IS NOT NULL)",
        "reports",
    )


def downgrade() -> None:
    op.drop_constraint("ck_reports_one_target", "reports", type_="check")
    op.create_check_constraint("ck_reports_one_target", "(post_id IS NOT NULL) <> (comment_id IS NOT NULL)", "reports")
    op.drop_constraint("fk_reports_message_id_messages", "reports", type_="foreignkey")
    op.drop_column("reports", "message_id")
