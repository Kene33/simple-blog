"""add user visibility settings"""

from alembic import op

revision = "0010_visibility"
down_revision = "0009_categories"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column in ("profile_visibility", "posts_visibility", "comments_visibility"):
        op.execute(f"ALTER TABLE users ADD COLUMN {column} VARCHAR(20) NOT NULL DEFAULT 'public'")
        op.execute(f"ALTER TABLE users ADD CONSTRAINT ck_users_{column} CHECK ({column} IN ('public', 'private'))")


def downgrade() -> None:
    for column in ("comments_visibility", "posts_visibility", "profile_visibility"):
        op.execute(f"ALTER TABLE users DROP CONSTRAINT ck_users_{column}")
        op.execute(f"ALTER TABLE users DROP COLUMN {column}")
