"""count authenticated shares once per account"""

from alembic import op

revision = "0013_unique_account_shares"
down_revision = "0012_moderator_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DELETE FROM share_events WHERE id IN (SELECT id FROM (SELECT id, row_number() OVER (PARTITION BY post_id, user_id ORDER BY created_at, id) AS rn FROM share_events WHERE user_id IS NOT NULL) duplicates WHERE rn > 1)")
    op.execute("UPDATE posts SET share_count = COALESCE(counts.total, 0) FROM (SELECT post_id, count(*) AS total FROM share_events GROUP BY post_id) counts WHERE posts.id = counts.post_id")
    op.execute("UPDATE posts SET share_count = 0 WHERE id NOT IN (SELECT post_id FROM share_events)")
    op.execute("CREATE UNIQUE INDEX uq_share_events_post_user ON share_events (post_id, user_id)")


def downgrade() -> None:
    op.execute("DROP INDEX uq_share_events_post_user")
