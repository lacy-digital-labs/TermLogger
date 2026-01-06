"""SQLite database operations for TermLogger."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

from .models import Contest, Log, LogType, Mode, QSO


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

            # Logs table for virtual logs
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    log_type TEXT DEFAULT 'general',
                    pota_ref TEXT,
                    sota_ref TEXT,
                    contest_id INTEGER,
                    my_callsign TEXT,
                    my_gridsquare TEXT,
                    location TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    start_time TEXT,
                    end_time TEXT,
                    is_active INTEGER DEFAULT 0,
                    is_archived INTEGER DEFAULT 0,
                    FOREIGN KEY (contest_id) REFERENCES contests(id)
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

            # Run migrations
            self._migrate_db(conn)

    def _migrate_db(self, conn: sqlite3.Connection) -> None:
        """Run database migrations for schema updates."""
        cursor = conn.cursor()

        # Check if log_id column exists in qsos table
        cursor.execute("PRAGMA table_info(qsos)")
        columns = [col[1] for col in cursor.fetchall()]

        if "log_id" not in columns:
            cursor.execute("ALTER TABLE qsos ADD COLUMN log_id INTEGER")
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_qsos_log
                ON qsos(log_id)
            """)
            conn.commit()

        # Check if source column exists in qsos table
        if "source" not in columns:
            cursor.execute("ALTER TABLE qsos ADD COLUMN source TEXT DEFAULT 'manual'")
            conn.commit()

        # Check if qrz_logid column exists in qsos table
        if "qrz_logid" not in columns:
            cursor.execute("ALTER TABLE qsos ADD COLUMN qrz_logid TEXT")
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_qsos_qrz_logid
                ON qsos(qrz_logid)
            """)
            conn.commit()

        # Check if clublog_uploaded column exists in qsos table
        if "clublog_uploaded" not in columns:
            cursor.execute("ALTER TABLE qsos ADD COLUMN clublog_uploaded INTEGER DEFAULT 0")
            conn.commit()

        # Create index on logs table
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_logs_active
            ON logs(is_active)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_logs_type
            ON logs(log_type)
        """)
        conn.commit()

    def add_qso(self, qso: QSO, log_id: Optional[int] = None) -> int:
        """Add a new QSO to the database. Returns the new QSO ID."""
        # Use provided log_id or the one from the QSO object
        effective_log_id = log_id if log_id is not None else qso.log_id
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO qsos (
                    callsign, frequency, mode, rst_sent, rst_received,
                    datetime_utc, notes, contest_id, exchange_sent, exchange_received,
                    log_id, source
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    effective_log_id,
                    qso.source,
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
        self,
        limit: int = 100,
        offset: int = 0,
        contest_id: Optional[int] = None,
        log_id: Optional[int] = None,
    ) -> list[QSO]:
        """Get QSOs with pagination, optionally filtered by contest or log."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM qsos WHERE 1=1"
            params: list = []

            if contest_id is not None:
                query += " AND contest_id = ?"
                params.append(contest_id)

            if log_id is not None:
                query += " AND log_id = ?"
                params.append(log_id)

            query += " ORDER BY datetime_utc DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            cursor.execute(query, params)
            return [self._row_to_qso(row) for row in cursor.fetchall()]

    def get_recent_qsos(self, count: int = 50, log_id: Optional[int] = None) -> list[QSO]:
        """Get the most recent QSOs, optionally filtered by log."""
        return self.get_all_qsos(limit=count, log_id=log_id)

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
                    notes = ?, contest_id = ?, exchange_sent = ?, exchange_received = ?,
                    log_id = ?
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
                    qso.log_id,
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

    def get_qso_count(
        self, contest_id: Optional[int] = None, log_id: Optional[int] = None
    ) -> int:
        """Get total QSO count, optionally filtered by contest or log."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT COUNT(*) FROM qsos WHERE 1=1"
            params: list = []

            if contest_id is not None:
                query += " AND contest_id = ?"
                params.append(contest_id)

            if log_id is not None:
                query += " AND log_id = ?"
                params.append(log_id)

            cursor.execute(query, params)
            return cursor.fetchone()[0]

    def update_qso_qrz_logid(self, qso_id: int, qrz_logid: str) -> bool:
        """Update the QRZ logid for a QSO after successful upload."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE qsos SET qrz_logid = ? WHERE id = ?",
                (qrz_logid, qso_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_qsos_without_qrz_logid(self, log_id: Optional[int] = None) -> list[QSO]:
        """Get QSOs that haven't been uploaded to QRZ (no qrz_logid)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM qsos WHERE (qrz_logid IS NULL OR qrz_logid = '')"
            params: list = []

            if log_id is not None:
                query += " AND log_id = ?"
                params.append(log_id)

            query += " ORDER BY datetime_utc ASC"
            cursor.execute(query, params)
            return [self._row_to_qso(row) for row in cursor.fetchall()]

    def find_duplicate_qso(
        self, callsign: str, datetime_utc: datetime, frequency: float, log_id: Optional[int] = None
    ) -> Optional[QSO]:
        """Find a duplicate QSO by callsign, datetime, and frequency."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Match within 1 minute and 0.01 MHz
            query = """
                SELECT * FROM qsos
                WHERE UPPER(callsign) = ?
                AND datetime_utc BETWEEN ? AND ?
                AND frequency BETWEEN ? AND ?
            """
            params = [
                callsign.upper(),
                (datetime_utc.replace(second=0, microsecond=0)).isoformat(),
                (datetime_utc.replace(second=59, microsecond=999999)).isoformat(),
                frequency - 0.01,
                frequency + 0.01,
            ]

            if log_id is not None:
                query += " AND log_id = ?"
                params.append(log_id)

            query += " LIMIT 1"
            cursor.execute(query, params)
            row = cursor.fetchone()
            return self._row_to_qso(row) if row else None

    def update_qso_clublog_uploaded(self, qso_id: int, uploaded: bool = True) -> bool:
        """Update the Club Log uploaded status for a QSO."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE qsos SET clublog_uploaded = ? WHERE id = ?",
                (1 if uploaded else 0, qso_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_qsos_not_uploaded_to_clublog(self, log_id: Optional[int] = None) -> list[QSO]:
        """Get QSOs that haven't been uploaded to Club Log."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM qsos WHERE (clublog_uploaded IS NULL OR clublog_uploaded = 0)"
            params: list = []

            if log_id is not None:
                query += " AND log_id = ?"
                params.append(log_id)

            query += " ORDER BY datetime_utc ASC"
            cursor.execute(query, params)
            return [self._row_to_qso(row) for row in cursor.fetchall()]

    def _row_to_qso(self, row: sqlite3.Row) -> QSO:
        """Convert a database row to a QSO object."""
        # Handle log_id which may not exist in older databases during migration
        log_id = None
        try:
            log_id = row["log_id"]
        except (KeyError, IndexError):
            pass

        # Handle source which may not exist in older databases during migration
        source = "manual"
        try:
            source = row["source"]
        except (KeyError, IndexError):
            pass

        # Handle qrz_logid which may not exist in older databases during migration
        qrz_logid = None
        try:
            qrz_logid = row["qrz_logid"]
        except (KeyError, IndexError):
            pass

        # Handle clublog_uploaded which may not exist in older databases during migration
        clublog_uploaded = False
        try:
            clublog_uploaded = bool(row["clublog_uploaded"])
        except (KeyError, IndexError):
            pass

        return QSO(
            id=row["id"],
            callsign=row["callsign"],
            frequency=row["frequency"],
            mode=Mode(row["mode"]),
            rst_sent=row["rst_sent"],
            rst_received=row["rst_received"],
            datetime_utc=datetime.fromisoformat(row["datetime_utc"]),
            notes=row["notes"] or "",
            log_id=log_id,
            source=source,
            qrz_logid=qrz_logid,
            clublog_uploaded=clublog_uploaded,
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

    # Log methods
    def add_log(self, log: Log) -> int:
        """Add a new log. Returns the new log ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO logs (
                    name, description, log_type, pota_ref, sota_ref, contest_id,
                    my_callsign, my_gridsquare, location, start_time, end_time,
                    is_active, is_archived
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    log.name,
                    log.description,
                    log.log_type.value,
                    log.pota_ref,
                    log.sota_ref,
                    log.contest_id,
                    log.my_callsign,
                    log.my_gridsquare,
                    log.location,
                    log.start_time.isoformat() if log.start_time else None,
                    log.end_time.isoformat() if log.end_time else None,
                    1 if log.is_active else 0,
                    1 if log.is_archived else 0,
                ),
            )
            conn.commit()
            return cursor.lastrowid

    def get_log(self, log_id: int) -> Optional[Log]:
        """Get a log by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM logs WHERE id = ?", (log_id,))
            row = cursor.fetchone()
            if row:
                log = self._row_to_log(row)
                log.qso_count = self.get_qso_count(log_id=log_id)
                return log
            return None

    def get_all_logs(
        self, include_archived: bool = False, limit: int = 100
    ) -> list[Log]:
        """Get all logs, optionally including archived ones."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if include_archived:
                cursor.execute(
                    "SELECT * FROM logs ORDER BY created_at DESC LIMIT ?", (limit,)
                )
            else:
                cursor.execute(
                    """
                    SELECT * FROM logs
                    WHERE is_archived = 0
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (limit,),
                )
            logs = [self._row_to_log(row) for row in cursor.fetchall()]
            # Add QSO counts
            for log in logs:
                log.qso_count = self.get_qso_count(log_id=log.id)
            return logs

    def get_active_log(self) -> Optional[Log]:
        """Get the currently active log."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM logs WHERE is_active = 1 LIMIT 1")
            row = cursor.fetchone()
            if row:
                log = self._row_to_log(row)
                log.qso_count = self.get_qso_count(log_id=log.id)
                return log
            return None

    def set_active_log(self, log_id: Optional[int]) -> bool:
        """Set the active log. Pass None to clear active log."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # First, clear any existing active log
            cursor.execute("UPDATE logs SET is_active = 0 WHERE is_active = 1")
            # Then set the new active log if provided
            if log_id is not None:
                cursor.execute(
                    "UPDATE logs SET is_active = 1 WHERE id = ?", (log_id,)
                )
            conn.commit()
            return True

    def update_log(self, log: Log) -> bool:
        """Update an existing log."""
        if log.id is None:
            return False

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE logs SET
                    name = ?, description = ?, log_type = ?, pota_ref = ?,
                    sota_ref = ?, contest_id = ?, my_callsign = ?, my_gridsquare = ?,
                    location = ?, start_time = ?, end_time = ?, is_active = ?,
                    is_archived = ?
                WHERE id = ?
            """,
                (
                    log.name,
                    log.description,
                    log.log_type.value,
                    log.pota_ref,
                    log.sota_ref,
                    log.contest_id,
                    log.my_callsign,
                    log.my_gridsquare,
                    log.location,
                    log.start_time.isoformat() if log.start_time else None,
                    log.end_time.isoformat() if log.end_time else None,
                    1 if log.is_active else 0,
                    1 if log.is_archived else 0,
                    log.id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_log(self, log_id: int, reassign_qsos_to: Optional[int] = None) -> bool:
        """Delete a log. Optionally reassign QSOs to another log."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Reassign or nullify QSOs
            if reassign_qsos_to is not None:
                cursor.execute(
                    "UPDATE qsos SET log_id = ? WHERE log_id = ?",
                    (reassign_qsos_to, log_id),
                )
            else:
                cursor.execute(
                    "UPDATE qsos SET log_id = NULL WHERE log_id = ?", (log_id,)
                )
            # Delete the log
            cursor.execute("DELETE FROM logs WHERE id = ?", (log_id,))
            conn.commit()
            return cursor.rowcount > 0

    def archive_log(self, log_id: int) -> bool:
        """Archive a log (soft delete)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE logs SET is_archived = 1, is_active = 0 WHERE id = ?",
                (log_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def unarchive_log(self, log_id: int) -> bool:
        """Unarchive a log."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE logs SET is_archived = 0 WHERE id = ?",
                (log_id,),
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_archived_logs(self, limit: int = 100) -> list[Log]:
        """Get only archived logs."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM logs
                WHERE is_archived = 1
                ORDER BY created_at DESC
                LIMIT ?
            """,
                (limit,),
            )
            logs = [self._row_to_log(row) for row in cursor.fetchall()]
            # Get QSO counts for each log
            for log in logs:
                if log.id:
                    log.qso_count = self.get_qso_count(log_id=log.id)
            return logs

    def _row_to_log(self, row: sqlite3.Row) -> Log:
        """Convert a database row to a Log object."""
        return Log(
            id=row["id"],
            name=row["name"],
            description=row["description"] or "",
            log_type=LogType(row["log_type"]),
            pota_ref=row["pota_ref"],
            sota_ref=row["sota_ref"],
            contest_id=row["contest_id"],
            my_callsign=row["my_callsign"],
            my_gridsquare=row["my_gridsquare"],
            location=row["location"],
            created_at=datetime.fromisoformat(row["created_at"])
            if row["created_at"]
            else None,
            start_time=datetime.fromisoformat(row["start_time"])
            if row["start_time"]
            else None,
            end_time=datetime.fromisoformat(row["end_time"])
            if row["end_time"]
            else None,
            is_active=bool(row["is_active"]),
            is_archived=bool(row["is_archived"]),
        )
