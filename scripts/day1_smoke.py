"""用于检查第一阶段领域模型是否符合约定的可执行脚本。"""

from job_agent.domain.models import (
    Capability,
    CapabilityLevel,
    Evidence,
    EvidenceStatus,
    Profile,
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

if __name__ == "__main__":
    check_contract()
    check_non_empty_strings()
    print("Day 1 domain contract passed.")
