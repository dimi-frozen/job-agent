"""Executable contract for the first domain-model exercise."""

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


if __name__ == "__main__":
    check_contract()
    print("Day 1 domain contract passed.")

