"""add authentication constraints and indexes"""
from alembic import op

revision = "0002_auth_constraints"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD CONSTRAINT ck_users_role CHECK (role IN ('user', 'admin'))")
    op.execute("ALTER TABLE users ALTER COLUMN username TYPE VARCHAR(30)")
    op.execute("ALTER TABLE users ALTER COLUMN username_normalized TYPE VARCHAR(30)")
    op.execute("CREATE INDEX ix_refresh_sessions_user_id ON refresh_sessions (user_id)")
    op.execute("CREATE INDEX ix_refresh_sessions_expires_at ON refresh_sessions (expires_at)")


def downgrade() -> None:
    op.execute("DROP INDEX ix_refresh_sessions_expires_at")
    op.execute("DROP INDEX ix_refresh_sessions_user_id")
    op.execute("ALTER TABLE users DROP CONSTRAINT ck_users_role")
    op.execute("ALTER TABLE users ALTER COLUMN username TYPE VARCHAR(50)")
    op.execute("ALTER TABLE users ALTER COLUMN username_normalized TYPE VARCHAR(50)")
