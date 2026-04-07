from __future__ import annotations

import sqlite3
from pathlib import Path

from harness_recall.ir import Session


class SessionIndex:
    def __init__(self, db_path: Path | str):
        self.db_path = str(db_path)
        self._init_db()
        self._conn = self._create_connection()

    def _init_db(self):
        conn = self._create_connection()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                source_file TEXT NOT NULL,
                source_file_mtime REAL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                project_dir TEXT,
                model TEXT,
                model_provider TEXT,
                cli_version TEXT,
                git_branch TEXT,
                git_commit TEXT,
                git_repo_url TEXT,
                title TEXT,
                parent_session_id TEXT,
                agent_name TEXT,
                agent_role TEXT,
                total_input_tokens INTEGER,
                total_output_tokens INTEGER
            );

            CREATE TABLE IF NOT EXISTS turns (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                sequence_num INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT,
                timestamp TEXT,
                reasoning TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE TABLE IF NOT EXISTS tool_calls (
                id TEXT PRIMARY KEY,
                turn_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                name TEXT NOT NULL,
                arguments TEXT,
                output TEXT,
                FOREIGN KEY (turn_id) REFERENCES turns(id),
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE INDEX IF NOT EXISTS idx_sessions_started_at ON sessions(started_at);
            CREATE INDEX IF NOT EXISTS idx_sessions_source ON sessions(source);
            CREATE INDEX IF NOT EXISTS idx_sessions_project_dir ON sessions(project_dir);
            CREATE INDEX IF NOT EXISTS idx_turns_session_id ON turns(session_id);
            CREATE INDEX IF NOT EXISTS idx_tool_calls_session_id ON tool_calls(session_id);
            CREATE INDEX IF NOT EXISTS idx_tool_calls_name ON tool_calls(name);
        """)
        # FTS5 table — separate statement because CREATE VIRTUAL TABLE IF NOT EXISTS
        # doesn't work reliably with executescript
        try:
            conn.execute("""
                CREATE VIRTUAL TABLE turns_fts USING fts5(
                    content,
                    content='turns',
                    content_rowid='rowid',
                    tokenize='porter unicode61'
                )
            """)
        except sqlite3.OperationalError:
            pass  # Already exists
        conn.commit()
        conn.close()

    def _create_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _get_conn(self) -> sqlite3.Connection:
        return self._conn

    def close(self) -> None:
        self._conn.close()

    def add_session(self, session: Session) -> None:
        conn = self._get_conn()
        # Remove existing session data if re-indexing
        self._remove_session_data(conn, session.id)

        total_input = sum(t.token_usage.input_tokens for t in session.turns if t.token_usage)
        total_output = sum(t.token_usage.output_tokens for t in session.turns if t.token_usage)

        conn.execute("""
            INSERT INTO sessions (id, source, source_file, source_file_mtime,
                started_at, ended_at, project_dir, model, model_provider,
                cli_version, git_branch, git_commit, git_repo_url, title,
                parent_session_id, agent_name, agent_role,
                total_input_tokens, total_output_tokens)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session.id, session.source, session.source_file, session.source_file_mtime,
            session.started_at.isoformat(), session.ended_at.isoformat() if session.ended_at else None,
            session.project_dir, session.model, session.model_provider,
            session.cli_version, session.git_branch, session.git_commit, session.git_repo_url,
            session.title, session.parent_session_id, session.agent_name, session.agent_role,
            total_input or None, total_output or None,
        ))

        for i, turn in enumerate(session.turns):
            input_t = turn.token_usage.input_tokens if turn.token_usage else None
            output_t = turn.token_usage.output_tokens if turn.token_usage else None
            conn.execute("""
                INSERT INTO turns (id, session_id, sequence_num, role, content,
                    timestamp, reasoning, input_tokens, output_tokens)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                turn.id, session.id, i, turn.role, turn.content,
                turn.timestamp.isoformat(), turn.reasoning, input_t, output_t,
            ))
            # Populate FTS
            rowid = conn.execute("SELECT rowid FROM turns WHERE id = ?", (turn.id,)).fetchone()[0]
            conn.execute("INSERT INTO turns_fts(rowid, content) VALUES (?, ?)", (rowid, turn.content or ""))

            for tc in turn.tool_calls:
                conn.execute("""
                    INSERT INTO tool_calls (id, turn_id, session_id, name, arguments, output)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (tc.id, turn.id, session.id, tc.name, tc.arguments, tc.output))

        conn.commit()

    def remove_session(self, session_id: str) -> None:
        conn = self._get_conn()
        self._remove_session_data(conn, session_id)
        conn.commit()

    def _remove_session_data(self, conn: sqlite3.Connection, session_id: str) -> None:
        # Remove FTS entries for turns
        rows = conn.execute("SELECT rowid, content FROM turns WHERE session_id = ?", (session_id,)).fetchall()
        for row in rows:
            conn.execute("INSERT INTO turns_fts(turns_fts, rowid, content) VALUES('delete', ?, ?)", (row[0], row[1] or ""))
        conn.execute("DELETE FROM tool_calls WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM turns WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))

    def list_sessions(self, source: str | None = None, after: str | None = None,
                      project: str | None = None, limit: int = 25) -> list[dict]:
        conn = self._get_conn()
        query = "SELECT * FROM sessions WHERE 1=1"
        params: list = []
        if source:
            query += " AND source = ?"
            params.append(source)
        if after:
            query += " AND started_at >= ?"
            params.append(after)
        if project:
            query += " AND project_dir LIKE ?"
            params.append(f"%{project}%")
        query += " ORDER BY started_at DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]

    def search(self, query: str, source: str | None = None,
               tool: str | None = None, limit: int = 25) -> list[dict]:
        conn = self._get_conn()
        sql = """
            SELECT t.session_id, t.content, t.role, t.timestamp,
                   s.title, s.source, s.started_at, s.model,
                   snippet(turns_fts, 0, '>>>', '<<<', '...', 40) as snippet,
                   rank
            FROM turns_fts
            JOIN turns t ON t.rowid = turns_fts.rowid
            JOIN sessions s ON s.id = t.session_id
            WHERE turns_fts MATCH ?
        """
        params: list = [query]
        if source:
            sql += " AND s.source = ?"
            params.append(source)
        if tool:
            sql += " AND t.id IN (SELECT turn_id FROM tool_calls WHERE name = ?)"
            params.append(tool)
        sql += " ORDER BY rank LIMIT ?"
        params.append(limit)
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def get_session(self, session_id: str) -> dict | None:
        conn = self._get_conn()
        # First try exact match
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        if row:
            return dict(row)
        # Then try prefix match — only return if unambiguous (exactly one match)
        rows = conn.execute("SELECT * FROM sessions WHERE id LIKE ?",
                            (f"{session_id}%",)).fetchall()
        if len(rows) == 1:
            return dict(rows[0])
        return None

    def find_sessions_by_prefix(self, prefix: str) -> list[dict]:
        """Return all sessions whose ID starts with the given prefix."""
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM sessions WHERE id LIKE ?",
                            (f"{prefix}%",)).fetchall()
        return [dict(r) for r in rows]

    def get_session_turns(self, session_id: str) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM turns WHERE session_id = ? ORDER BY sequence_num",
            (session_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_tool_calls(self, session_id: str) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM tool_calls WHERE session_id = ? ORDER BY rowid",
            (session_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    def needs_reindex(self, source_file: str, current_mtime: float) -> bool:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT source_file_mtime FROM sessions WHERE source_file = ?",
            (source_file,)
        ).fetchone()
        if row is None:
            return True
        return row[0] != current_mtime

    def stats(self) -> dict:
        conn = self._get_conn()
        total = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        turns = conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
        sources = {}
        for row in conn.execute("SELECT source, COUNT(*) FROM sessions GROUP BY source"):
            sources[row[0]] = row[1]
        db_size = Path(self.db_path).stat().st_size if Path(self.db_path).exists() else 0
        return {
            "total_sessions": total,
            "total_turns": turns,
            "sources": sources,
            "db_size_bytes": db_size,
        }
