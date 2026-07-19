"""add posts full-text search index"""
from alembic import op

revision = "0003_posts_search"
down_revision = "0002_auth_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE INDEX ix_posts_search ON posts USING GIN (to_tsvector('simple', title || ' ' || content))")


def downgrade() -> None:
    op.execute("DROP INDEX ix_posts_search")
