"""Store policy loading: policy.md split into citable sub-sections ("1.1", "6.2", ...)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_SUB_RE = re.compile(r"^###\s+(\d+\.\d+)\s+(.+?)\s*$", re.MULTILINE)
_SECTION_RE = re.compile(r"^##\s+\d+\.", re.MULTILINE)


class PolicyError(Exception):
    """Raised when policy.md is missing or has no numbered sub-sections."""


@dataclass(frozen=True)
class PolicySection:
    section_id: str  # "1.2"
    title: str  # "Free returns, no restocking fee"
    text: str  # plain text of the sub-section (markdown emphasis removed)


@dataclass
class Policy:
    sections: dict[str, PolicySection]

    def get(self, section_id: str) -> PolicySection | None:
        return self.sections.get(section_id)


def parse_policy(markdown: str) -> Policy:
    """Each `### N.M Title` heading starts a sub-section that runs to the next heading."""
    matches = list(_SUB_RE.finditer(markdown))
    sections: dict[str, PolicySection] = {}
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        body = markdown[m.end() : end]
        next_top = _SECTION_RE.search(body)
        if next_top:
            body = body[: next_top.start()]
        text = " ".join(body.replace("**", "").replace("`", "").split())
        sections[m.group(1)] = PolicySection(m.group(1), m.group(2).strip(), text)
    if not sections:
        raise PolicyError("policy.md has no '### N.M Title' sub-sections.")
    return Policy(sections)


def load_policy(path: Path) -> Policy:
    if not path.is_file():
        raise PolicyError(f"Policy not found at {path}. Copy the pack's data/ files into FULL_CODE/data/.")
    return parse_policy(path.read_text(encoding="utf-8"))
