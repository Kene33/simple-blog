"""add media purpose"""

from alembic import op

revision = "0004_media_purpose"
down_revision = "0003_posts_search"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE media ADD COLUMN purpose VARCHAR(20) NOT NULL DEFAULT 'post'")
    op.execute("ALTER TABLE media ADD CONSTRAINT ck_media_purpose CHECK (purpose IN ('post', 'avatar'))")


def downgrade() -> None:
    op.execute("ALTER TABLE media DROP CONSTRAINT ck_media_purpose")
    op.execute("ALTER TABLE media DROP COLUMN purpose")
