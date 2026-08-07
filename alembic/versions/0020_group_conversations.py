"""add group conversations"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0020_group_conversations"
down_revision = "0019_message_media"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_conversations_direct_key", "conversations", type_="check")
    op.alter_column("conversations", "direct_key", existing_type=sa.String(length=80), nullable=True)
    op.add_column("conversations", sa.Column("kind", sa.String(length=20), server_default="direct", nullable=False))
    op.add_column("conversations", sa.Column("title", sa.String(length=120), nullable=True))
    op.add_column("conversations", sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_check_constraint("ck_conversations_kind", "conversations", "kind IN ('direct', 'group')")
    op.create_foreign_key("fk_conversations_created_by_id_users", "conversations", "users", ["created_by_id"], ["id"], ondelete="SET NULL")
    op.add_column("conversation_members", sa.Column("role", sa.String(length=20), server_default="member", nullable=False))


def downgrade() -> None:
    op.drop_column("conversation_members", "role")
    op.drop_constraint("fk_conversations_created_by_id_users", "conversations", type_="foreignkey")
    op.drop_constraint("ck_conversations_kind", "conversations", type_="check")
    op.drop_column("conversations", "created_by_id")
    op.drop_column("conversations", "title")
    op.drop_column("conversations", "kind")
    op.alter_column("conversations", "direct_key", existing_type=sa.String(length=80), nullable=False)
    op.create_check_constraint("ck_conversations_direct_key", "conversations", "length(direct_key) > 0")
