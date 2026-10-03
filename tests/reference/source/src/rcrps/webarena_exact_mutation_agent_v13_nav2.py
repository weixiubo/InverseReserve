"""PACT-v13 exact-mutation agent with the development-informed v2 navigator."""

from __future__ import annotations

import hashlib
from typing import Any

from .webarena_exact_mutation_agent_v13 import ExactMutationTransferAgentV13
from .webarena_public_navigation_v2 import (
    check_public_navigation_effect_v2,
    compile_public_navigation_v2,
    navigation_messages_v2,
    resolve_public_navigation_v2,
)


class ExactMutationTransferAgentV13Nav2(ExactMutationTransferAgentV13):
    """Change only public navigation; retain the frozen PACT-v13 mutation path."""

    method_id = "full_pact_v13_webarena_exact_mutation_nav2"

    def navigate_once(self) -> None:
        before = self.executor.snapshot
        before_url = str(self.executor.observation.get("url", ""))
        inventory = compile_public_navigation_v2(
            before,
            current_url=before_url,
            goal=self.goal,
            quarantined_attempt_keys=self.quarantined_navigation_keys,
            maximum_candidates=int(self.budgets["maximum_navigation_candidates"]),
        )
        step: dict[str, Any] = {
            "type": "public_navigation_decision_v2",
            "inventory": inventory.record(),
            "model": None,
            "resolution": None,
        }
        if not inventory.candidates:
            self.method_failure = "public navigation exposed no safe current candidate"
            self.audit(step)
            return
        messages = navigation_messages_v2(
            goal=self.goal,
            current_url=before_url,
            inventory=inventory,
            navigation_history=self.navigation_history,
        )
        model = self.call_model(messages)
        if model is None:
            self.audit(step)
            return
        step["model"] = model
        try:
            decision = resolve_public_navigation_v2(
                inventory,
                model_output=model["raw_output"],
            )
        except Exception as error:
            self.parse_failures += 1
            self.method_failure = (
                f"navigation planner parse failed: {type(error).__name__}: {error}"
            )
            self.audit(step)
            return
        step["resolution"] = decision.record()
        self.audit(step)
        if not decision.allowed or decision.candidate is None:
            self.method_failure = "public base navigator abstained"
            return
        candidate = decision.candidate
        outcome = self.executor(candidate.action, "navigation")
        after_url = str(self.executor.observation.get("url", ""))
        effect = check_public_navigation_effect_v2(
            before=before,
            after=outcome.snapshot,
            before_url=before_url,
            after_url=after_url,
            candidate=candidate,
        )
        record = {
            **effect.record(),
            "bid": candidate.bid,
            "label": candidate.label,
            "kind": candidate.kind,
            "before_url_sha256": hashlib.sha256(
                before_url.encode("utf-8")
            ).hexdigest(),
            "after_url_sha256": hashlib.sha256(
                after_url.encode("utf-8")
            ).hexdigest(),
        }
        self.navigation_effects.append(record)
        self.navigation_history.append(
            {
                "bid": candidate.bid,
                "label": candidate.label,
                "kind": candidate.kind,
                "effective": effect.effective,
                "url_changed": effect.url_changed,
            }
        )
        if not effect.effective:
            self.quarantined_navigation_keys.add(effect.attempt_key)
        if outcome.action_error:
            self.method_failure = (
                f"public navigation action reported an error: {outcome.action_error}"
            )
        elif outcome.terminal:
            self.method_failure = "public navigation terminated before exact mutation"

    def result(self) -> dict[str, Any]:
        result = super().result()
        result["candidate"] = "WebArena-exact-mutation-agent-v13-nav2-episode"
        result["navigation_version"] = "public_navigation_v2"
        return result
