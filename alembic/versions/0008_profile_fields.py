"""add profile fields"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0008_profile_fields"
down_revision = "0007_post_bookmarks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("cover_media_id", UUID(as_uuid=True), nullable=True))
    op.add_column("users", sa.Column("display_name", sa.String(length=80), nullable=True))
    op.add_column("users", sa.Column("bio", sa.String(length=500), nullable=True))
    op.create_foreign_key("fk_users_cover_media_id", "users", "media", ["cover_media_id"], ["id"], ondelete="SET NULL")


def downgrade() -> None:
    op.drop_constraint("fk_users_cover_media_id", "users", type_="foreignkey")
    op.drop_column("users", "bio")
    op.drop_column("users", "display_name")
    op.drop_column("users", "cover_media_id")
