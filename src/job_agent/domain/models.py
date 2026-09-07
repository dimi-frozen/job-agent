"""Core domain models.

Day 1 exercise: implement the enums and Pydantic models described in
``docs/day-01.md``. Keep this module independent from SQLite and LangGraph.
"""

from enum import StrEnum

from pydantic import BaseModel


class CapabilityLevel(StrEnum):
    """How strongly the available evidence supports a capability."""

    # TODO: add the four agreed values.
    pass


class EvidenceStatus(StrEnum):
    """Where a piece of evidence is in the validation lifecycle."""

    # TODO: add the four agreed values.
    pass


class Profile(BaseModel):
    """The user's stable identity and target roles."""

    # TODO: implement the fields from docs/day-01.md.
    pass


class Capability(BaseModel):
    """The current level of one capability for one profile."""

    # TODO: implement the fields from docs/day-01.md.
    pass


class Evidence(BaseModel):
    """A source-backed statement that may support a capability."""

    # TODO: implement the fields from docs/day-01.md.
    pass

