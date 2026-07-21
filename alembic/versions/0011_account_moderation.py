"""add account moderation and password reset tokens"""

from alembic import op

revision = "0011_account_moderation"
down_revision = "0010_visibility"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN muted_until TIMESTAMP WITH TIME ZONE")
    op.execute("ALTER TABLE users ADD COLUMN moderation_reason TEXT")
    op.execute("CREATE TABLE password_reset_tokens (id UUID PRIMARY KEY, user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE, token_hash VARCHAR(255) NOT NULL UNIQUE, expires_at TIMESTAMP WITH TIME ZONE NOT NULL, used_at TIMESTAMP WITH TIME ZONE, created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now())")
    op.execute("CREATE INDEX ix_password_reset_tokens_user_expires_at ON password_reset_tokens (user_id, expires_at)")


def downgrade() -> None:
    op.execute("DROP INDEX ix_password_reset_tokens_user_expires_at")
    op.execute("DROP TABLE password_reset_tokens")
    op.execute("ALTER TABLE users DROP COLUMN moderation_reason")
    op.execute("ALTER TABLE users DROP COLUMN muted_until")
