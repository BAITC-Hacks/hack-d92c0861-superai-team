"""Deterministic building blocks for the Career Quest recommendation engine."""

from .data_loader import DataLoader, Dataset, DatasetPaths
from .skill_gap import SkillGap, calculate_skill_gaps
from .target_resolver import (
    CareerTarget,
    TargetResolution,
    find_role_profile,
    resolve_target,
)

__all__ = [
    "CareerTarget",
    "DataLoader",
    "Dataset",
    "DatasetPaths",
    "SkillGap",
    "TargetResolution",
    "calculate_skill_gaps",
    "find_role_profile",
    "resolve_target",
]
