"""SQLite 的底层连接设置。

领域模型不会导入这个模块。后续将由仓储函数负责在 SQLite 数据行与
Pydantic 模型之间进行转换。
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path

from job_agent.domain.models import (
    Capability,
    CapabilityLevel,
    Evidence,
    EvidenceStatus,
    Profile,
)

def connect(database_path: Path) -> sqlite3.Connection:
    """连接 SQLite，并启用按列名取值和外键约束。"""

    database_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_schema(connection: sqlite3.Connection) -> None:
    """创建保存用户档案的表。"""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS profiles (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            target_roles TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS capabilities (
            id TEXT PRIMARY KEY,
            profile_id TEXT NOT NULL,
            name TEXT NOT NULL,
            level TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (profile_id) REFERENCES profiles(id)
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS evidence (
            id TEXT PRIMARY KEY,
            capability_id TEXT NOT NULL,
            source_type TEXT NOT NULL,
            source_ref TEXT,
            summary TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (capability_id) REFERENCES capabilities(id)
        )
        """
    )
    connection.commit()


def save_profile(
    connection: sqlite3.Connection,
    profile: Profile,
) -> None:
    """把一份用户档案保存到 profiles 表。"""

    connection.execute(
        """
        INSERT INTO profiles (
            id,
            name,
            target_roles,
            created_at,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            profile.id,
            profile.name,
            json.dumps(profile.target_roles, ensure_ascii=False),
            profile.created_at.isoformat(),
            profile.updated_at.isoformat(),
        ),
    )
    connection.commit()


def load_profile(
    connection: sqlite3.Connection,
    profile_id: str,
) -> Profile | None:
    """根据 ID 从 profiles 表读取一份用户档案。"""

    row = connection.execute(
        """
        SELECT id, name, target_roles, created_at, updated_at
        FROM profiles
        WHERE id = ?
        """,
        (profile_id,),
    ).fetchone()

    if row is None:
        return None

    return Profile(
        id=row["id"],
        name=row["name"],
        target_roles=json.loads(row["target_roles"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def save_capability(
    connection: sqlite3.Connection,
    capability: Capability,
) -> None:
    """把一项能力保存到 capabilities 表。"""

    connection.execute(
        """
        INSERT INTO capabilities (
            id,
            profile_id,
            name,
            level,
            updated_at
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            capability.id,
            capability.profile_id,
            capability.name,
            capability.level.value,
            capability.updated_at.isoformat(),
        ),
    )
    connection.commit()


def load_capability(
    connection: sqlite3.Connection,
    capability_id: str,
) -> Capability | None:
    """根据 ID 从 capabilities 表读取一项能力。"""

    row = connection.execute(
        """
        SELECT id, profile_id, name, level, updated_at
        FROM capabilities
        WHERE id = ?
        """,
        (capability_id,),
    ).fetchone()

    if row is None:
        return None

    return Capability(
        id=row["id"],
        profile_id=row["profile_id"],
        name=row["name"],
        level=CapabilityLevel(row["level"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def list_capabilities_by_profile(
    connection: sqlite3.Connection,
    profile_id: str,
) -> list[Capability]:
    """读取一份用户档案下的全部能力。"""

    rows = connection.execute(
        """
        SELECT id, profile_id, name, level, updated_at
        FROM capabilities
        WHERE profile_id = ?
        ORDER BY updated_at, id
        """,
        (profile_id,),
    ).fetchall()

    return [
        Capability(
            id=row["id"],
            profile_id=row["profile_id"],
            name=row["name"],
            level=CapabilityLevel(row["level"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
        for row in rows
    ]


def save_evidence(
    connection: sqlite3.Connection,
    evidence: Evidence,
) -> None:
    """把一条证据保存到 evidence 表。"""

    connection.execute(
        """
        INSERT INTO evidence (
            id,
            capability_id,
            source_type,
            source_ref,
            summary,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            evidence.id,
            evidence.capability_id,
            evidence.source_type,
            evidence.source_ref,
            evidence.summary,
            evidence.status.value,
            evidence.created_at.isoformat(),
        ),
    )
    connection.commit()


def load_evidence(
    connection: sqlite3.Connection,
    evidence_id: str,
) -> Evidence | None:
    """根据 ID 从 evidence 表读取一条证据。"""

    row = connection.execute(
        """
        SELECT
            id,
            capability_id,
            source_type,
            source_ref,
            summary,
            status,
            created_at
        FROM evidence
        WHERE id = ?
        """,
        (evidence_id,),
    ).fetchone()

    if row is None:
        return None

    return Evidence(
        id=row["id"],
        capability_id=row["capability_id"],
        source_type=row["source_type"],
        source_ref=row["source_ref"],
        summary=row["summary"],
        status=EvidenceStatus(row["status"]),
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def list_evidence_by_capability(
    connection: sqlite3.Connection,
    capability_id: str,
) -> list[Evidence]:
    """读取一项能力下的全部证据。"""

    rows = connection.execute(
        """
        SELECT
            id,
            capability_id,
            source_type,
            source_ref,
            summary,
            status,
            created_at
        FROM evidence
        WHERE capability_id = ?
        ORDER BY created_at, id
        """,
        (capability_id,),
    ).fetchall()

    return [
        Evidence(
            id=row["id"],
            capability_id=row["capability_id"],
            source_type=row["source_type"],
            source_ref=row["source_ref"],
            summary=row["summary"],
            status=EvidenceStatus(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )
        for row in rows
    ]


def list_evidence_by_profile(
    connection: sqlite3.Connection,
    profile_id: str,
) -> list[Evidence]:
    """读取一份用户档案下全部能力对应的证据。"""

    all_evidence: list[Evidence] = []

    for capability in list_capabilities_by_profile(connection, profile_id):
        evidence = list_evidence_by_capability(connection, capability.id)
        all_evidence.extend(evidence)

    return all_evidence
