"""add moderator role and moderation audit log"""

from alembic import op

revision = "0012_moderator_roles"
down_revision = "0011_account_moderation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE users DROP CONSTRAINT ck_users_role")
    op.execute("ALTER TABLE users ADD CONSTRAINT ck_users_role CHECK (role IN ('user', 'moderator', 'admin'))")
    op.execute("CREATE TABLE moderation_actions (id UUID PRIMARY KEY, actor_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT, action VARCHAR(50) NOT NULL, target_type VARCHAR(30) NOT NULL, target_id UUID NOT NULL, reason TEXT, created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now())")
    op.execute("CREATE INDEX ix_moderation_actions_created_at_id ON moderation_actions (created_at, id)")


def downgrade() -> None:
    op.execute("UPDATE users SET role = 'user' WHERE role = 'moderator'")
    op.execute("DROP INDEX ix_moderation_actions_created_at_id")
    op.execute("DROP TABLE moderation_actions")
    op.execute("ALTER TABLE users DROP CONSTRAINT ck_users_role")
    op.execute("ALTER TABLE users ADD CONSTRAINT ck_users_role CHECK (role IN ('user', 'admin'))")
