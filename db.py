import sqlite3
import threading
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    channel_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    username TEXT,
    text TEXT NOT NULL DEFAULT '',
    link TEXT,
    posted_at INTEGER,
    discussion_chat_id INTEGER,
    discussion_message_id INTEGER,
    PRIMARY KEY (channel_id, message_id)
);

CREATE TABLE IF NOT EXISTS comments (
    discussion_chat_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    channel_id INTEGER NOT NULL,
    channel_message_id INTEGER NOT NULL,
    text TEXT NOT NULL,
    commented_at INTEGER,
    PRIMARY KEY (discussion_chat_id, message_id)
);

CREATE TABLE IF NOT EXISTS reports (
    channel_id INTEGER NOT NULL,
    message_id INTEGER NOT NULL,
    fingerprint TEXT NOT NULL,
    summary TEXT NOT NULL,
    PRIMARY KEY (channel_id, message_id)
);

CREATE INDEX IF NOT EXISTS comments_by_post
    ON comments (channel_id, channel_message_id);
CREATE INDEX IF NOT EXISTS posts_by_discussion
    ON posts (discussion_chat_id, discussion_message_id);
"""


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    def upsert_post(
        self,
        channel_id,
        message_id,
        username=None,
        text="",
        posted_at=None,
        discussion_chat_id=None,
        discussion_message_id=None,
    ):
        username = username.lower() if username else None
        text = text or ""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM posts WHERE channel_id = ? AND message_id = ?",
                (channel_id, message_id),
            ).fetchone()
            if row is None:
                link = _link(username, message_id)
                self._conn.execute(
                    """
                    INSERT INTO posts (
                        channel_id, message_id, username, text, link, posted_at,
                        discussion_chat_id, discussion_message_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        channel_id,
                        message_id,
                        username,
                        text,
                        link,
                        posted_at,
                        discussion_chat_id,
                        discussion_message_id,
                    ),
                )
            else:
                username = username or row["username"]
                link = _link(username, message_id) or row["link"]
                if not text.strip():
                    text = row["text"]
                if discussion_chat_id is None:
                    discussion_chat_id = row["discussion_chat_id"]
                if discussion_message_id is None:
                    discussion_message_id = row["discussion_message_id"]
                posted_at = row["posted_at"] or posted_at
                self._conn.execute(
                    """
                    UPDATE posts
                    SET username = ?, text = ?, link = ?, posted_at = ?,
                        discussion_chat_id = ?, discussion_message_id = ?
                    WHERE channel_id = ? AND message_id = ?
                    """,
                    (
                        username,
                        text,
                        link,
                        posted_at,
                        discussion_chat_id,
                        discussion_message_id,
                        channel_id,
                        message_id,
                    ),
                )
            self._conn.commit()

    def post_by_username(self, username, message_id):
        with self._lock:
            row = self._conn.execute(
                """
                SELECT * FROM posts
                WHERE username = ? AND message_id = ?
                """,
                (username.lower(), message_id),
            ).fetchone()
        return dict(row) if row else None

    def post_by_ids(self, channel_id, message_id):
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM posts WHERE channel_id = ? AND message_id = ?",
                (channel_id, message_id),
            ).fetchone()
        return dict(row) if row else None

    def posts_by_discussion_chat(self, discussion_chat_id):
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT channel_id, message_id FROM posts
                WHERE discussion_chat_id = ?
                ORDER BY posted_at, message_id
                """,
                (discussion_chat_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def post_by_discussion(self, discussion_chat_id, discussion_message_id):
        with self._lock:
            row = self._conn.execute(
                """
                SELECT * FROM posts
                WHERE discussion_chat_id = ? AND discussion_message_id = ?
                """,
                (discussion_chat_id, discussion_message_id),
            ).fetchone()
        return dict(row) if row else None

    def save_comment(
        self,
        discussion_chat_id,
        message_id,
        channel_id,
        channel_message_id,
        text,
        commented_at,
    ):
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO comments (
                    discussion_chat_id, message_id, channel_id,
                    channel_message_id, text, commented_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(discussion_chat_id, message_id) DO UPDATE SET
                    text = excluded.text,
                    channel_id = excluded.channel_id,
                    channel_message_id = excluded.channel_message_id
                """,
                (
                    discussion_chat_id,
                    message_id,
                    channel_id,
                    channel_message_id,
                    text,
                    commented_at,
                ),
            )
            self._conn.commit()

    def comment_target(self, discussion_chat_id, message_id):
        with self._lock:
            row = self._conn.execute(
                """
                SELECT channel_id, channel_message_id FROM comments
                WHERE discussion_chat_id = ? AND message_id = ?
                """,
                (discussion_chat_id, message_id),
            ).fetchone()
        if not row:
            return None
        return row["channel_id"], row["channel_message_id"]

    def comments_for(self, channel_id, message_id):
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT message_id, text, commented_at FROM comments
                WHERE channel_id = ? AND channel_message_id = ?
                ORDER BY commented_at, message_id
                """,
                (channel_id, message_id),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_summary(self, channel_id, message_id, fingerprint):
        with self._lock:
            row = self._conn.execute(
                """
                SELECT summary FROM reports
                WHERE channel_id = ? AND message_id = ? AND fingerprint = ?
                """,
                (channel_id, message_id, fingerprint),
            ).fetchone()
        return row["summary"] if row else None

    def save_summary(self, channel_id, message_id, fingerprint, summary):
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO reports (channel_id, message_id, fingerprint, summary)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(channel_id, message_id) DO UPDATE SET
                    fingerprint = excluded.fingerprint,
                    summary = excluded.summary
                """,
                (channel_id, message_id, fingerprint, summary),
            )
            self._conn.commit()


def _link(username, message_id):
    if not username:
        return None
    return f"https://t.me/{username}/{message_id}"
