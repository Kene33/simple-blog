"""add public user status"""

from alembic import op

revision = "0014_user_status"
down_revision = "0013_unique_account_shares"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN status VARCHAR(20) NOT NULL DEFAULT 'active'")
    op.execute("UPDATE users SET status = 'banned' WHERE disabled_at IS NOT NULL")
    op.execute("ALTER TABLE users ADD CONSTRAINT ck_users_status CHECK (status IN ('active', 'banned', 'deleted'))")


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP CONSTRAINT ck_users_status")
    op.execute("ALTER TABLE users DROP COLUMN status")
