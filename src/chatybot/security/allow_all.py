"""
Allow-All Policy Engine (engine = "allow")
Runs tools without policy checks, the way chatybot behaved before v0.9.0.

Unlike the --no-security CLI flag, this is a persistent setting in
security.toml, it still goes through the SecurityManager (banner, audit
logging, usable as a chain stage), and by default it keeps the security
self-protection floor so the agent cannot rewrite security.toml or read the
chatybot secrets file. Set `protect_security_config = false` under [allow] to
turn that off too.
"""

from __future__ import annotations

from chatybot.security import self_protect
from chatybot.security.base import BasePolicyEngine
from chatybot.security.models import PolicyDecision, PolicyRequest, Verdict


class AllowAllPolicyEngine(BasePolicyEngine):
    """Allows every tool call, except (by default) access to security configuration."""

    def __init__(self, protect_security_config: bool = True, debug: bool = False):
        self.protect_security_config = protect_security_config
        self.debug = debug

    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        if self.protect_security_config:
            blocked = self_protect.check(request)
            if blocked is not None:
                if self.debug:
                    print(f"[Security Debug] [ALLOW ENGINE] [SPECIAL DENY] {blocked.reason}")
                return blocked
        if self.debug:
            print(f"[Security Debug] [ALLOW ENGINE] Permitted '{request.tool}' without policy checks.")
        return PolicyDecision(verdict=Verdict.ALLOW, reason="Allow engine: no policy checks (pre-0.9.0 behavior).")

    def evaluate_output(self, request: PolicyRequest) -> PolicyDecision:
        if self.protect_security_config:
            blocked = self_protect.check(request)
            if blocked is not None:
                if self.debug:
                    print(f"[Security Debug] [ALLOW ENGINE] [OUTPUT SPECIAL DENY] {blocked.reason}")
                return blocked
        return PolicyDecision(verdict=Verdict.ALLOW, reason="Allow engine: output permitted.")

    def get_banner(self) -> str:
        suffix = "security config protected" if self.protect_security_config else "NO self-protection"
        return f"Allow-All (no policy checks; {suffix})"
