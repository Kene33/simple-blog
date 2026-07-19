"""enforce unique open reports"""

from alembic import op

revision = "0005_report_open_uniqueness"
down_revision = "0004_media_purpose"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE UNIQUE INDEX uq_reports_open_post ON reports (reporter_id, post_id) WHERE status = 'open' AND post_id IS NOT NULL")
    op.execute("CREATE UNIQUE INDEX uq_reports_open_comment ON reports (reporter_id, comment_id) WHERE status = 'open' AND comment_id IS NOT NULL")
    op.execute("ALTER TABLE reports ADD CONSTRAINT ck_reports_status CHECK (status IN ('open', 'resolved', 'rejected'))")


def downgrade() -> None:
    op.execute("ALTER TABLE reports DROP CONSTRAINT ck_reports_status")
    op.execute("DROP INDEX uq_reports_open_comment")
    op.execute("DROP INDEX uq_reports_open_post")
