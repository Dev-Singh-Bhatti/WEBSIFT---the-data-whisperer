import os
import re
import sqlite3
from typing import Optional

import pandas as pd

from src.config import DATABASE_URL


def _normalize_name(name: str) -> str:
    """Convert arbitrary names to safe SQLite identifiers."""
    normalized = re.sub(r"[^0-9a-zA-Z_]+", "_", str(name).strip())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    if not normalized:
        normalized = "default_table"
    if normalized[0].isdigit():
        normalized = f"t_{normalized}"
    return normalized


def _resolve_sqlite_path(database_url: Optional[str]) -> str:
    """Resolve sqlite path from DATABASE_URL-style input."""
    url = (database_url or DATABASE_URL or "sqlite:///./app.db").strip()
    if url.startswith("sqlite:///"):
        path = url[len("sqlite:///"):]
    elif url.startswith("sqlite://"):
        path = url[len("sqlite://"):]
    else:
        # Allow direct file path as fallback
        path = url

    if path.startswith("./"):
        path = path[2:]

    if not os.path.isabs(path):
        path = os.path.join(os.getcwd(), path)

    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    return path


class SQLiteDatabaseWrapper:
    """SQLite wrapper with a Mongo-like API used by the app."""

    SUMMARY_TABLE = "review_summaries"
    PLATFORM_ALL_KEY = "__all__"

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.SUMMARY_TABLE} (
                    product_name TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (product_name, platform)
                )
                """
            )
            conn.commit()

    def bulk_insert(self, df: pd.DataFrame, collection_name: str) -> None:
        if df is None or df.empty:
            return
        table = _normalize_name(collection_name)
        data = df.copy()
        with self._connect() as conn:
            data.to_sql(table, conn, if_exists="append", index=False)

    def find(self, collection_name: str, query=None):
        table = _normalize_name(collection_name)
        with self._connect() as conn:
            table_exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            if not table_exists:
                return None

            sql = f'SELECT * FROM "{table}"'
            params = []
            if query and isinstance(query, dict):
                filters = []
                for key, value in query.items():
                    filters.append(f'"{key}" = ?')
                    params.append(value)
                if filters:
                    sql += " WHERE " + " AND ".join(filters)

            df = pd.read_sql_query(sql, conn, params=params)
            return None if df.empty else df

    def list_collection_names(self):
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type='table'
                  AND name NOT LIKE 'sqlite_%'
                  AND name <> ?
                ORDER BY name
                """,
                (self.SUMMARY_TABLE,),
            ).fetchall()
        return [row["name"] for row in rows]

    def upsert_summary(self, product_name: str, platform: Optional[str], summary: str) -> None:
        platform_key = platform if platform else self.PLATFORM_ALL_KEY
        with self._connect() as conn:
            conn.execute(
                f"""
                INSERT INTO {self.SUMMARY_TABLE}
                (product_name, platform, summary, created_at, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(product_name, platform) DO UPDATE SET
                    summary = excluded.summary,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (product_name, platform_key, summary),
            )
            conn.commit()

    def get_summary(self, product_name: str, platform: Optional[str]) -> Optional[str]:
        platform_key = platform if platform else self.PLATFORM_ALL_KEY
        with self._connect() as conn:
            row = conn.execute(
                f"""
                SELECT summary
                FROM {self.SUMMARY_TABLE}
                WHERE product_name = ? AND platform = ?
                LIMIT 1
                """,
                (product_name, platform_key),
            ).fetchone()
        if row is None:
            return None
        return row["summary"]


def mongo_operation(client_url=None, database_name=None):
    """
    Backward-compatible factory used by existing code paths.
    Returns a SQLite wrapper for local prototype storage.
    """
    db_path = _resolve_sqlite_path(client_url or DATABASE_URL)
    return SQLiteDatabaseWrapper(db_path)

