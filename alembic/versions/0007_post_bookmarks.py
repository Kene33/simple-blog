"""add post bookmarks"""

from alembic import op
from sqlalchemy import Column, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

revision = "0007_post_bookmarks"
down_revision = "0006_post_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "post_bookmarks",
        Column("post_id", UUID(as_uuid=True), ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True),
        Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    )


def downgrade() -> None:
    op.drop_table("post_bookmarks")
