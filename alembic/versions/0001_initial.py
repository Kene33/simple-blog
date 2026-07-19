"""create the initial PostgreSQL schema"""
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
    CREATE TABLE users (id UUID NOT NULL, username VARCHAR(50) NOT NULL, username_normalized VARCHAR(50) NOT NULL, email VARCHAR(320) NOT NULL, email_normalized VARCHAR(320) NOT NULL, password_hash VARCHAR(255) NOT NULL, role VARCHAR(20) DEFAULT 'user' NOT NULL, avatar_media_id UUID, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, disabled_at TIMESTAMP WITH TIME ZONE, PRIMARY KEY (id), UNIQUE (username_normalized), UNIQUE (email_normalized));
    CREATE TABLE tags (id UUID NOT NULL, name VARCHAR(50) NOT NULL, name_normalized VARCHAR(50) NOT NULL, PRIMARY KEY (id), UNIQUE (name_normalized));
    CREATE TABLE media (id UUID NOT NULL, owner_id UUID NOT NULL, kind VARCHAR(20) NOT NULL, mime_type VARCHAR(100) NOT NULL, size_bytes BIGINT NOT NULL, storage_key VARCHAR(500) NOT NULL, status VARCHAR(20) DEFAULT 'pending' NOT NULL, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, attached_at TIMESTAMP WITH TIME ZONE, deleted_at TIMESTAMP WITH TIME ZONE, PRIMARY KEY (id), UNIQUE (storage_key));
    CREATE TABLE refresh_sessions (id UUID NOT NULL, user_id UUID NOT NULL, token_hash VARCHAR(255) NOT NULL, expires_at TIMESTAMP WITH TIME ZONE NOT NULL, revoked_at TIMESTAMP WITH TIME ZONE, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, last_used_at TIMESTAMP WITH TIME ZONE, PRIMARY KEY (id), FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE, UNIQUE (token_hash));
    CREATE TABLE posts (id UUID NOT NULL, author_id UUID NOT NULL, title VARCHAR(200) NOT NULL, content TEXT NOT NULL, category VARCHAR(80), like_count INTEGER DEFAULT '0' NOT NULL, comment_count INTEGER DEFAULT '0' NOT NULL, share_count INTEGER DEFAULT '0' NOT NULL, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, deleted_at TIMESTAMP WITH TIME ZONE, PRIMARY KEY (id), FOREIGN KEY(author_id) REFERENCES users (id) ON DELETE RESTRICT);
    CREATE TABLE post_tags (post_id UUID NOT NULL, tag_id UUID NOT NULL, PRIMARY KEY (post_id, tag_id), FOREIGN KEY(post_id) REFERENCES posts (id) ON DELETE CASCADE, FOREIGN KEY(tag_id) REFERENCES tags (id) ON DELETE CASCADE);
    CREATE TABLE post_media (post_id UUID NOT NULL, media_id UUID NOT NULL, position INTEGER NOT NULL, PRIMARY KEY (post_id, media_id), CONSTRAINT uq_post_media_position UNIQUE (post_id, position), FOREIGN KEY(post_id) REFERENCES posts (id) ON DELETE CASCADE, FOREIGN KEY(media_id) REFERENCES media (id) ON DELETE CASCADE);
    CREATE TABLE comments (id UUID NOT NULL, post_id UUID NOT NULL, author_id UUID NOT NULL, parent_id UUID, body TEXT NOT NULL, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, deleted_at TIMESTAMP WITH TIME ZONE, PRIMARY KEY (id), FOREIGN KEY(post_id) REFERENCES posts (id) ON DELETE CASCADE, FOREIGN KEY(author_id) REFERENCES users (id) ON DELETE RESTRICT, FOREIGN KEY(parent_id) REFERENCES comments (id) ON DELETE RESTRICT);
    CREATE TABLE post_likes (post_id UUID NOT NULL, user_id UUID NOT NULL, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, PRIMARY KEY (post_id, user_id), FOREIGN KEY(post_id) REFERENCES posts (id) ON DELETE CASCADE, FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE);
    CREATE TABLE share_events (id UUID NOT NULL, post_id UUID NOT NULL, user_id UUID, channel VARCHAR(20) NOT NULL, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, PRIMARY KEY (id), FOREIGN KEY(post_id) REFERENCES posts (id) ON DELETE CASCADE, FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE SET NULL);
    CREATE TABLE reports (id UUID NOT NULL, reporter_id UUID NOT NULL, post_id UUID, comment_id UUID, reason VARCHAR(50) NOT NULL, details TEXT, status VARCHAR(20) DEFAULT 'open' NOT NULL, resolution TEXT, created_at TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL, resolved_at TIMESTAMP WITH TIME ZONE, PRIMARY KEY (id), CONSTRAINT ck_reports_one_target CHECK ((post_id IS NOT NULL) <> (comment_id IS NOT NULL)), FOREIGN KEY(reporter_id) REFERENCES users (id) ON DELETE RESTRICT, FOREIGN KEY(post_id) REFERENCES posts (id) ON DELETE CASCADE, FOREIGN KEY(comment_id) REFERENCES comments (id) ON DELETE CASCADE);
    CREATE INDEX ix_posts_created_at_id ON posts (created_at DESC, id DESC);
    CREATE INDEX ix_posts_category_created_at_id ON posts (category, created_at DESC, id DESC);
    CREATE INDEX ix_posts_author_created_at_id ON posts (author_id, created_at DESC, id DESC);
    CREATE INDEX ix_post_tags_tag_id_post_id ON post_tags (tag_id, post_id);
    CREATE INDEX ix_media_owner_status_created_at ON media (owner_id, status, created_at);
    CREATE INDEX ix_comments_author_created_at ON comments (author_id, created_at DESC);
    CREATE INDEX ix_comments_post_parent_created_id ON comments (post_id, parent_id, created_at, id);
    CREATE INDEX ix_reports_status_created_at ON reports (status, created_at);
    ALTER TABLE users ADD FOREIGN KEY(avatar_media_id) REFERENCES media (id) ON DELETE SET NULL;
    ALTER TABLE media ADD FOREIGN KEY(owner_id) REFERENCES users (id) ON DELETE RESTRICT;
    """)


def downgrade() -> None:
    op.execute("""
    DROP TABLE reports;
    DROP TABLE share_events;
    DROP TABLE post_likes;
    DROP TABLE comments;
    DROP TABLE post_media;
    DROP TABLE post_tags;
    DROP TABLE posts;
    DROP TABLE refresh_sessions;
    DROP TABLE media;
    DROP TABLE tags;
    DROP TABLE users;
    """)
