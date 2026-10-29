"""Routes a policy question to the policy sub-section(s) that answer it, or reports a policy gap."""

from __future__ import annotations

from dataclasses import dataclass

from shopassist import lexicon as lx
from shopassist.policy import Policy


@dataclass(frozen=True)
class PolicyRoute:
    sections: tuple[str, ...]  # sub-sections to cite, most relevant first
    gap: bool = False  # the policy is silent on this topic -> refuse


def route_policy(text: str, policy: Policy) -> PolicyRoute | None:
    """`text` is the cleaned shopper message. None means 'this is not a policy question after all'."""
    if any(rx.search(text) for rx in lx.POLICY_GAPS):
        return PolicyRoute((), gap=True)
    for rx, sections in lx.POLICY_ROUTES:
        if rx.search(text):
            known = tuple(s for s in sections if policy.get(s))
            if known:
                return PolicyRoute(known)
    return None
