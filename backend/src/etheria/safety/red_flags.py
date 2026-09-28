"""The triage rule table (spec 4.6), loaded from red_flags.yaml. The matcher
that applies it arrives with the triage node in M4; rules can only raise
the triage level.

A rule fires when any phrase in `any_of` occurs, or when every group in
`all_of` has at least one phrase that occurs."""

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, TypeAdapter, model_validator

RULES_FILE = Path(__file__).with_name("red_flags.yaml")


class RedFlagRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    level: Literal["RED", "YELLOW"]
    category: str
    any_of: list[str] = []
    all_of: list[list[str]] = []
    helpline: Literal["tele_manas"] | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _has_trigger(self) -> "RedFlagRule":
        if not self.any_of and not self.all_of:
            raise ValueError(f"rule {self.id}: needs any_of or all_of")
        if any(not group for group in self.all_of):
            raise ValueError(f"rule {self.id}: empty all_of group")
        return self


def load_rules(path: Path = RULES_FILE) -> list[RedFlagRule]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return TypeAdapter(list[RedFlagRule]).validate_python(data)
