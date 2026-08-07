"""add email verification state and tokens"""

from alembic import op

revision = "0015_email_verification"
down_revision = "0014_user_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users ADD COLUMN email_verified BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("""
        CREATE TABLE email_verification_tokens (
            id UUID NOT NULL,
            user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
            token_hash VARCHAR(255) NOT NULL UNIQUE,
            expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
            used_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            PRIMARY KEY (id)
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE email_verification_tokens")
    op.execute("ALTER TABLE users DROP COLUMN email_verified")
