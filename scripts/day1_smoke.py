"""用于检查第一阶段领域模型是否符合约定的可执行脚本。"""

import sqlite3
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import ValidationError

from job_agent.domain.models import (
    Capability,
    CapabilityLevel,
    Evidence,
    EvidenceStatus,
    Profile,
)
from job_agent.storage.sqlite import (
    connect,
    initialize_schema,
    load_capability,
    load_evidence,
    load_profile,
    save_capability,
    save_evidence,
    save_profile,
)


EXPECTED_ENUMS = {
    CapabilityLevel: {"aware", "assisted", "independent", "project_verified"},
    EvidenceStatus: {"candidate", "confirmed", "verified", "rejected"},
}

EXPECTED_FIELDS = {
    Profile: {"id", "name", "target_roles", "created_at", "updated_at"},
    Capability: {"id", "profile_id", "name", "level", "updated_at"},
    Evidence: {
        "id",
        "capability_id",
        "source_type",
        "source_ref",
        "summary",
        "status",
        "created_at",
    },
}


def check_contract() -> None:
    for enum_type, expected_values in EXPECTED_ENUMS.items():
        actual_values = {item.value for item in enum_type}
        assert actual_values == expected_values, (
            f"{enum_type.__name__} values: expected {expected_values}, "
            f"got {actual_values}"
        )

    for model_type, expected_fields in EXPECTED_FIELDS.items():
        actual_fields = set(model_type.model_fields)
        assert actual_fields == expected_fields, (
            f"{model_type.__name__} fields: expected {expected_fields}, "
            f"got {actual_fields}"
        )

def check_non_empty_strings() -> None:
    invalid_cases = [
        lambda: Profile(name=""),
        lambda: Capability(profile_id="p1", name=""),
        lambda: Evidence(
            capability_id="c1",
            source_type="code",
            summary="",
        ),
    ]

    for create_model in invalid_cases:
        try:
            create_model()
        except ValidationError:
            continue

        raise AssertionError("空字符串应该触发 ValidationError")


def check_sqlite_round_trip() -> None:
    """使用临时数据库检查保存、读取和外键约束。"""

    with TemporaryDirectory() as temporary_directory:
        database_path = Path(temporary_directory) / "day1.db"
        connection = connect(database_path)

        try:
            initialize_schema(connection)

            profile = Profile(
                name="张先生",
                target_roles=["AI 应用开发"],
            )
            capability = Capability(
                profile_id=profile.id,
                name="RAG",
                level=CapabilityLevel.INDEPENDENT,
            )
            evidence = Evidence(
                capability_id=capability.id,
                source_type="run_result",
                summary="Day 1 数据库验收通过",
                status=EvidenceStatus.VERIFIED,
            )

            save_profile(connection, profile)
            save_capability(connection, capability)
            save_evidence(connection, evidence)

            assert load_profile(connection, profile.id) == profile
            assert load_capability(connection, capability.id) == capability
            assert load_evidence(connection, evidence.id) == evidence

            invalid_capability = Capability(
                profile_id="missing-profile",
                name="无效能力",
            )

            try:
                save_capability(connection, invalid_capability)
            except sqlite3.IntegrityError:
                connection.rollback()
            else:
                raise AssertionError("不存在的 Profile ID 应该触发外键错误")
        finally:
            connection.close()

if __name__ == "__main__":
    check_contract()
    check_non_empty_strings()
    check_sqlite_round_trip()
    print("Day 1 domain contract passed.")
