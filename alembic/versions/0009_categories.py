"""add category approval workflow"""

from alembic import op

revision = "0009_categories"
down_revision = "0008_profile_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE TABLE categories (id UUID PRIMARY KEY, name VARCHAR(50) NOT NULL, name_normalized VARCHAR(50) NOT NULL UNIQUE, status VARCHAR(20) NOT NULL DEFAULT 'approved', created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(), updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(), CONSTRAINT ck_categories_status CHECK (status IN ('approved', 'pending', 'rejected')))")
    op.execute("CREATE TABLE category_requests (id UUID PRIMARY KEY, requester_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT, category_id UUID NOT NULL REFERENCES categories(id) ON DELETE CASCADE, status VARCHAR(20) NOT NULL DEFAULT 'pending', resolution TEXT, created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(), resolved_at TIMESTAMP WITH TIME ZONE, CONSTRAINT ck_category_requests_status CHECK (status IN ('pending', 'approved', 'rejected')))")
    op.execute("CREATE INDEX ix_category_requests_status_created_at ON category_requests (status, created_at)")
    op.execute("ALTER TABLE posts ADD COLUMN category_id UUID REFERENCES categories(id) ON DELETE RESTRICT")
    op.execute("ALTER TABLE posts ADD COLUMN category_request_id UUID REFERENCES category_requests(id) ON DELETE SET NULL")
    op.execute("ALTER TABLE posts DROP CONSTRAINT ck_posts_status")
    op.execute("ALTER TABLE posts ADD CONSTRAINT ck_posts_status CHECK (status IN ('draft', 'published', 'pending_category', 'needs_category_change'))")
    op.execute("INSERT INTO categories (id, name, name_normalized, status) SELECT gen_random_uuid(), min(category), lower(category), 'approved' FROM posts WHERE category IS NOT NULL AND btrim(category) <> '' GROUP BY lower(category) ON CONFLICT (name_normalized) DO NOTHING")
    op.execute("UPDATE posts SET category_id = categories.id FROM categories WHERE lower(posts.category) = categories.name_normalized AND posts.category_id IS NULL")
    op.execute("CREATE INDEX ix_posts_category_id_created_at ON posts (category_id, created_at DESC, id DESC)")


def downgrade() -> None:
    op.execute("DROP INDEX ix_posts_category_id_created_at")
    op.execute("ALTER TABLE posts DROP CONSTRAINT ck_posts_status")
    op.execute("ALTER TABLE posts ADD CONSTRAINT ck_posts_status CHECK (status IN ('draft', 'published'))")
    op.execute("ALTER TABLE posts DROP COLUMN category_request_id")
    op.execute("ALTER TABLE posts DROP COLUMN category_id")
    op.execute("DROP TABLE category_requests")
    op.execute("DROP TABLE categories")
