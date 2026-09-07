"""Low-level SQLite setup.

The domain models do not import this module. Later, repository functions will
translate between SQLite rows and Pydantic models.
"""

import sqlite3
from pathlib import Path


def connect(database_path: Path) -> sqlite3.Connection:
    """Open SQLite with named-column rows and foreign keys enabled."""

    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection

