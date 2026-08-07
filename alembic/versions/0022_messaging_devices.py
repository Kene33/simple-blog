"""add messaging device public keys"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0022_messaging_devices"
down_revision = "0021_push_subscriptions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("encrypted_body", postgresql.JSON(), nullable=True))
    op.create_table(
        "messaging_devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("public_key", postgresql.JSON(), nullable=False),
        sa.Column("label", sa.String(length=80), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messaging_devices_user_active", "messaging_devices", ["user_id", "revoked_at"])


def downgrade() -> None:
    op.drop_column("messages", "encrypted_body")
    op.drop_index("ix_messaging_devices_user_active", table_name="messaging_devices")
    op.drop_table("messaging_devices")
