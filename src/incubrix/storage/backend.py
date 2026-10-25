import json
import sqlite3
from typing import Any, Dict, List, Optional
from pathlib import Path
from incubrix.core.config import settings

class SQLiteStorage:
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.DB_PATH
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Media assets
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS assets (
                asset_id TEXT PRIMARY KEY,
                filename TEXT NOT NULL,
                file_path TEXT NOT NULL,
                sha256 TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                duration REAL NOT NULL,
                width INTEGER,
                height INTEGER,
                fps REAL,
                video_codec TEXT,
                audio_codec TEXT,
                channels INTEGER,
                sample_rate INTEGER,
                metadata_json TEXT NOT NULL,
                transcript_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # Editing sessions
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                asset_id TEXT NOT NULL,
                timeline_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (asset_id) REFERENCES assets(asset_id)
            )
            """)

            # History operations for undo/redo/restore
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS operations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                operation_id TEXT NOT NULL,
                operation_type TEXT NOT NULL,
                raw_instruction TEXT,
                payload_json TEXT NOT NULL,
                timeline_before_json TEXT NOT NULL,
                timeline_after_json TEXT NOT NULL,
                is_undone INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
            """)

            # Clarification pending state
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS clarifications (
                session_id TEXT PRIMARY KEY,
                clarification_id TEXT NOT NULL,
                intent_type TEXT NOT NULL,
                prompt TEXT NOT NULL,
                options_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
            """)

            # Render jobs and manifests
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS render_jobs (
                job_id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                asset_id TEXT NOT NULL,
                status TEXT NOT NULL,
                progress REAL DEFAULT 0.0,
                error_message TEXT,
                output_path TEXT,
                manifest_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
            """)
            conn.commit()

    # Asset operations
    def save_asset(self, asset: Dict[str, Any]):
        with self._get_connection() as conn:
            conn.execute("""
            INSERT OR REPLACE INTO assets (
                asset_id, filename, file_path, sha256, size_bytes,
                duration, width, height, fps, video_codec, audio_codec,
                channels, sample_rate, metadata_json, transcript_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                asset["asset_id"],
                asset["filename"],
                str(asset["file_path"]),
                asset["sha256"],
                asset["size_bytes"],
                asset.get("duration", 0.0),
                asset.get("width"),
                asset.get("height"),
                asset.get("fps"),
                asset.get("video_codec"),
                asset.get("audio_codec"),
                asset.get("channels"),
                asset.get("sample_rate"),
                json.dumps(asset.get("metadata", {})),
                json.dumps(asset.get("transcript")) if asset.get("transcript") is not None else None,
            ))
            conn.commit()

    def get_asset(self, asset_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM assets WHERE asset_id = ?", (asset_id,)).fetchone()
            if not row:
                return None
            res = dict(row)
            res["metadata"] = json.loads(res["metadata_json"]) if res["metadata_json"] else {}
            res["transcript"] = json.loads(res["transcript_json"]) if res["transcript_json"] else None
            return res

    def list_assets(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute("SELECT * FROM assets ORDER BY created_at DESC").fetchall()
            results = []
            for r in rows:
                item = dict(r)
                item["metadata"] = json.loads(item["metadata_json"]) if item["metadata_json"] else {}
                item["transcript"] = json.loads(item["transcript_json"]) if item["transcript_json"] else None
                results.append(item)
            return results

    # Session operations
    def save_session(self, session_id: str, asset_id: str, timeline_json: str):
        with self._get_connection() as conn:
            conn.execute("""
            INSERT INTO sessions (session_id, asset_id, timeline_json, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(session_id) DO UPDATE SET
                timeline_json = excluded.timeline_json,
                updated_at = CURRENT_TIMESTAMP
            """, (session_id, asset_id, timeline_json))
            conn.commit()

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,)).fetchone()
            return dict(row) if row else None

    # Operations / History
    def record_operation(self, session_id: str, operation_id: str, operation_type: str,
                         raw_instruction: str, payload: Dict[str, Any],
                         timeline_before_json: str, timeline_after_json: str):
        with self._get_connection() as conn:
            # When a new edit is committed, invalidate any undone operations in redo stack
            conn.execute("DELETE FROM operations WHERE session_id = ? AND is_undone = 1", (session_id,))
            conn.execute("""
            INSERT INTO operations (
                session_id, operation_id, operation_type, raw_instruction,
                payload_json, timeline_before_json, timeline_after_json, is_undone
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """, (
                session_id, operation_id, operation_type, raw_instruction,
                json.dumps(payload), timeline_before_json, timeline_after_json
            ))
            conn.commit()

    def get_last_applied_operation(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("""
            SELECT * FROM operations 
            WHERE session_id = ? AND is_undone = 0 
            ORDER BY id DESC LIMIT 1
            """, (session_id,)).fetchone()
            return dict(row) if row else None

    def get_last_undone_operation(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("""
            SELECT * FROM operations 
            WHERE session_id = ? AND is_undone = 1 
            ORDER BY id ASC LIMIT 1
            """, (session_id,)).fetchone()
            return dict(row) if row else None

    def mark_operation_undone(self, op_id: int):
        with self._get_connection() as conn:
            conn.execute("UPDATE operations SET is_undone = 1 WHERE id = ?", (op_id,))
            conn.commit()

    def mark_operation_redone(self, op_id: int):
        with self._get_connection() as conn:
            conn.execute("UPDATE operations SET is_undone = 0 WHERE id = ?", (op_id,))
            conn.commit()

    def get_operations_history(self, session_id: str) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            rows = conn.execute("""
            SELECT * FROM operations WHERE session_id = ? ORDER BY id ASC
            """, (session_id,)).fetchall()
            return [dict(r) for r in rows]

    # Clarifications
    def save_clarification(self, session_id: str, clarification_id: str, intent_type: str, prompt: str, options: List[Dict[str, Any]]):
        with self._get_connection() as conn:
            conn.execute("""
            INSERT OR REPLACE INTO clarifications (session_id, clarification_id, intent_type, prompt, options_json)
            VALUES (?, ?, ?, ?, ?)
            """, (session_id, clarification_id, intent_type, prompt, json.dumps(options)))
            conn.commit()

    def get_clarification(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM clarifications WHERE session_id = ?", (session_id,)).fetchone()
            if not row:
                return None
            res = dict(row)
            res["options"] = json.loads(res["options_json"]) if res["options_json"] else []
            return res

    def clear_clarification(self, session_id: str):
        with self._get_connection() as conn:
            conn.execute("DELETE FROM clarifications WHERE session_id = ?", (session_id,))
            conn.commit()

    # Render Jobs
    def create_render_job(self, job_id: str, session_id: str, asset_id: str):
        with self._get_connection() as conn:
            conn.execute("""
            INSERT INTO render_jobs (job_id, session_id, asset_id, status, progress)
            VALUES (?, ?, ?, 'QUEUED', 0.0)
            """, (job_id, session_id, asset_id))
            conn.commit()

    def update_render_job(self, job_id: str, status: str, progress: float = 0.0,
                          error_message: Optional[str] = None, output_path: Optional[str] = None,
                          manifest: Optional[Dict[str, Any]] = None):
        with self._get_connection() as conn:
            conn.execute("""
            UPDATE render_jobs SET
                status = ?,
                progress = ?,
                error_message = ?,
                output_path = ?,
                manifest_json = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE job_id = ?
            """, (
                status, progress, error_message,
                output_path,
                json.dumps(manifest) if manifest else None,
                job_id
            ))
            conn.commit()

    def get_render_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM render_jobs WHERE job_id = ?", (job_id,)).fetchone()
            if not row:
                return None
            res = dict(row)
            res["manifest"] = json.loads(res["manifest_json"]) if res["manifest_json"] else None
            return res

storage = SQLiteStorage()
