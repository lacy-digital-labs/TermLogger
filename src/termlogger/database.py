"""SQLite database operations for TermLogger."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

from .models import Contest, Mode, QSO


class Database:
    """SQLite database manager for QSO logging."""

    def __init__(self, db_path: str):
        """Initialize database connection."""
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection context manager."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # QSOs table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS qsos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    callsign TEXT NOT NULL,
                    frequency REAL NOT NULL,
                    mode TEXT NOT NULL,
                    rst_sent TEXT DEFAULT '59',
                    rst_received TEXT DEFAULT '59',
                    datetime_utc TEXT NOT NULL,
                    notes TEXT DEFAULT '',
                    contest_id INTEGER,
                    exchange_sent TEXT,
                    exchange_received TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (contest_id) REFERENCES contests(id)
                )
            """)

            # Contests table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS contests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    start_time TEXT,
                    end_time TEXT,
                    exchange_format TEXT DEFAULT 'RST+SN',
                    active INTEGER DEFAULT 0
                )
            """)

            # Config table for key-value storage
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS config (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            """)

            # Create indexes for common queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_qsos_callsign
                ON qsos(callsign)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_qsos_datetime
                ON qsos(datetime_utc)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_qsos_contest
                ON qsos(contest_id)
            """)

            conn.commit()

    def add_qso(self, qso: QSO) -> int:
        """Add a new QSO to the database. Returns the new QSO ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO qsos (
                    callsign, frequency, mode, rst_sent, rst_received,
                    datetime_utc, notes, contest_id, exchange_sent, exchange_received
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    qso.callsign.upper(),
                    qso.frequency,
                    qso.mode.value,
                    qso.rst_sent,
                    qso.rst_received,
                    qso.datetime_utc.isoformat(),
                    qso.notes,
                    qso.contest_id,
                    qso.exchange_sent,
                    qso.exchange_received,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_qso(self, qso_id: int) -> Optional[QSO]:
        """Get a QSO by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM qsos WHERE id = ?", (qso_id,))
            row = cursor.fetchone()
            return self._row_to_qso(row) if row else None

    def get_all_qsos(
        self, limit: int = 100, offset: int = 0, contest_id: Optional[int] = None
    ) -> list[QSO]:
        """Get QSOs with pagination."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if contest_id is not None:
                cursor.execute(
                    """
                    SELECT * FROM qsos
                    WHERE contest_id = ?
                    ORDER BY datetime_utc DESC
                    LIMIT ? OFFSET ?
                """,
                    (contest_id, limit, offset),
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM qsos
                    ORDER BY datetime_utc DESC
                    LIMIT ? OFFSET ?
                """,
                    (limit, offset),
                )
            return [self._row_to_qso(row) for row in cursor.fetchall()]

    def get_recent_qsos(self, count: int = 50) -> list[QSO]:
        """Get the most recent QSOs."""
        return self.get_all_qsos(limit=count)

    def search_qsos(self, callsign: str) -> list[QSO]:
        """Search for QSOs by callsign (partial match)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM qsos
                WHERE callsign LIKE ?
                ORDER BY datetime_utc DESC
            """,
                (f"%{callsign.upper()}%",),
            )
            return [self._row_to_qso(row) for row in cursor.fetchall()]

    def check_dupe(
        self,
        callsign: str,
        band: Optional[str] = None,
        mode: Optional[str] = None,
        contest_id: Optional[int] = None,
    ) -> bool:
        """Check if a QSO is a duplicate (same callsign, optionally same band/mode)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            query = "SELECT COUNT(*) FROM qsos WHERE UPPER(callsign) = ?"
            params = [callsign.upper()]

            if mode:
                query += " AND mode = ?"
                params.append(mode)

            if contest_id is not None:
                query += " AND contest_id = ?"
                params.append(contest_id)

            cursor.execute(query, params)
            count = cursor.fetchone()[0]
            return count > 0

    def update_qso(self, qso: QSO) -> bool:
        """Update an existing QSO."""
        if qso.id is None:
            return False

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE qsos SET
                    callsign = ?, frequency = ?, mode = ?,
                    rst_sent = ?, rst_received = ?, datetime_utc = ?,
                    notes = ?, contest_id = ?, exchange_sent = ?, exchange_received = ?
                WHERE id = ?
            """,
                (
                    qso.callsign.upper(),
                    qso.frequency,
                    qso.mode.value,
                    qso.rst_sent,
                    qso.rst_received,
                    qso.datetime_utc.isoformat(),
                    qso.notes,
                    qso.contest_id,
                    qso.exchange_sent,
                    qso.exchange_received,
                    qso.id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_qso(self, qso_id: int) -> bool:
        """Delete a QSO by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM qsos WHERE id = ?", (qso_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_qso_count(self, contest_id: Optional[int] = None) -> int:
        """Get total QSO count."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if contest_id is not None:
                cursor.execute(
                    "SELECT COUNT(*) FROM qsos WHERE contest_id = ?", (contest_id,)
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM qsos")
            return cursor.fetchone()[0]

    def _row_to_qso(self, row: sqlite3.Row) -> QSO:
        """Convert a database row to a QSO object."""
        return QSO(
            id=row["id"],
            callsign=row["callsign"],
            frequency=row["frequency"],
            mode=Mode(row["mode"]),
            rst_sent=row["rst_sent"],
            rst_received=row["rst_received"],
            datetime_utc=datetime.fromisoformat(row["datetime_utc"]),
            notes=row["notes"] or "",
            contest_id=row["contest_id"],
            exchange_sent=row["exchange_sent"],
            exchange_received=row["exchange_received"],
            created_at=datetime.fromisoformat(row["created_at"])
            if row["created_at"]
            else None,
        )

    # Contest methods
    def add_contest(self, contest: Contest) -> int:
        """Add a new contest. Returns the new contest ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO contests (name, start_time, end_time, exchange_format, active)
                VALUES (?, ?, ?, ?, ?)
            """,
                (
                    contest.name,
                    contest.start_time.isoformat() if contest.start_time else None,
                    contest.end_time.isoformat() if contest.end_time else None,
                    contest.exchange_format,
                    1 if contest.active else 0,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_active_contest(self) -> Optional[Contest]:
        """Get the currently active contest."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM contests WHERE active = 1 LIMIT 1")
            row = cursor.fetchone()
            if row:
                return Contest(
                    id=row["id"],
                    name=row["name"],
                    start_time=datetime.fromisoformat(row["start_time"])
                    if row["start_time"]
                    else None,
                    end_time=datetime.fromisoformat(row["end_time"])
                    if row["end_time"]
                    else None,
                    exchange_format=row["exchange_format"],
                    active=bool(row["active"]),
                )
            return None
