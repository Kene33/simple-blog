"""add post status for server drafts"""

from alembic import op

revision = "0006_post_status"
down_revision = "0005_report_open_uniqueness"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE posts ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'published'")
    op.execute("ALTER TABLE posts ADD CONSTRAINT ck_posts_status CHECK (status IN ('draft', 'published'))")
    op.create_index("ix_posts_author_status_updated_at", "posts", ["author_id", "status", "updated_at", "id"])


def downgrade() -> None:
    op.drop_index("ix_posts_author_status_updated_at", table_name="posts")
    op.drop_constraint("ck_posts_status", "posts", type_="check")
    op.drop_column("posts", "status")
