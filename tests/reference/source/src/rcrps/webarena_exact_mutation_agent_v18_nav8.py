"""PACT-v18 WebArena agent with joint URL semantics and viewport editors."""

from __future__ import annotations

from .recovery_capacity import remaining_after_action as _remaining_capacity_after_proposal

from typing import Any

from .pact_controller_v8 import inverse_action_cost_v8
from .pact_controller_v10 import interrupt_repair_action_cost_v10
from .pact_controller_v13 import bind_complete_public_commit_certificate_v13
from .webarena_exact_mutation_agent_v1 import (
    _certificate_record,
    _restoration_record,
)
from .webarena_exact_mutation_agent_v16_nav6 import (
    ExactMutationTransferAgentV16Nav6,
)
from .webarena_exact_mutation_v6 import (
    certify_exact_mutation_commit_v6,
    compile_exact_mutation_goal_v6,
    compile_exact_mutation_inventory_v6,
)


class ExactMutationTransferAgentV18Nav8(
    ExactMutationTransferAgentV16Nav6
):
    """Add only joint public URL semantics to the frozen V17 policy."""

    method_id = "full_pact_v18_webarena_exact_mutation_nav8"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.typed_url_normalizations = 0
        self.joint_url_semantic_normalizations = 0
        self.viewport_editor_surface_bindings = 0
        self.viewport_save_canonicalizations = 0
        self.token_back_neutralization_bindings = 0

    def _viewport(self) -> tuple[int, int]:
        height, width = self.executor.observation["screenshot"].shape[:2]
        return int(width), int(height)

    def execute_exact_mutation(self, compilation: Any) -> None:
        before = self.executor.snapshot
        width, height = self._viewport()
        inventory = compile_exact_mutation_inventory_v6(
            before,
            self.goal,
            compilation=compilation,
            viewport_width=width,
            viewport_height=height,
        )
        bindings = compilation.goal_contract.payload_bindings
        if len(bindings) != 1:
            self.method_failure = (
                "exact target surface did not bind one public field"
            )
            return
        binding = bindings[0]
        contract = inventory.contract_by_bid.get(binding.bid)
        if contract is None:
            self.method_failure = "exact target field lacks a typed transaction"
            return
        inverse_reserve = inverse_action_cost_v8(contract)
        commit_action_cost = 1
        interrupt_repair_cost = interrupt_repair_action_cost_v10(contract)
        remaining_after_forward = _remaining_capacity_after_proposal(self.budgets["maximum_gui_actions"], len(self.executor.actions))
        required_after_forward = (
            inverse_reserve + commit_action_cost + interrupt_repair_cost
        )
        allowed = remaining_after_forward >= required_after_forward
        self.inverse_reservation_audits += 1
        self.audit(
            {
                "type": "inverse_budget_reservation",
                "bid": binding.bid,
                "inverse_action_cost": inverse_reserve,
                "commit_action_cost": commit_action_cost,
                "interrupt_repair_action_cost": interrupt_repair_cost,
                "required_after_forward": required_after_forward,
                "remaining_after_forward": remaining_after_forward,
                "allowed": allowed,
                "reservation_version": "PACT-v10-recovery-plus-commit",
            }
        )
        if not allowed:
            self.inverse_reservation_stops += 1
            self.method_failure = (
                "inverse, commit, and repair budget reservation stopped mutation"
            )
            return
        opened = self.runtime.transact(
            before=before,
            contract=contract,
            candidate_label=binding.label,
        )
        self.typed_transactions += 1
        if opened.restoration is not None:
            self.restorations.append(_restoration_record(opened.restoration))
        self.audit(
            {
                "type": "exact_mutation_transaction_result_v6",
                "bid": binding.bid,
                "surface": compilation.surface.record(),
                "projection": compilation.projection.record(),
                "scoped_binding": (
                    None
                    if compilation.scoped_binding is None
                    else compilation.scoped_binding.record()
                ),
                "typed_value_normalization": (
                    None
                    if compilation.value_normalization is None
                    else compilation.value_normalization.record()
                ),
                "joint_url_semantic_normalization": (
                    None
                    if compilation.semantic_url_normalization is None
                    else compilation.semantic_url_normalization.record()
                ),
                "viewport_surface_binding": (
                    None
                    if compilation.viewport_surface is None
                    else compilation.viewport_surface.record()
                ),
                "admitted": opened.admitted,
                "reason": opened.reason,
                "interrupt_repairs": opened.interrupt_repairs,
                "halted": opened.halted,
            }
        )
        if not opened.admitted or opened.halted:
            self.method_failure = opened.reason
            return

        current = self.executor.snapshot
        width, height = self._viewport()
        fresh = compile_exact_mutation_goal_v6(
            self.goal,
            current,
            viewport_width=width,
            viewport_height=height,
        )
        self.final_compilation = fresh
        if not fresh.allowed:
            self.method_failure = "exact mutation disappeared after typed forward"
            return
        fresh_inventory = compile_exact_mutation_inventory_v6(
            current,
            self.goal,
            compilation=fresh,
            viewport_width=width,
            viewport_height=height,
        )
        fresh_bindings = fresh.goal_contract.payload_bindings
        if (
            len(fresh_bindings) != 1
            or fresh_bindings[0].bid != binding.bid
            or fresh_bindings[0].value != binding.value
        ):
            self.method_failure = (
                "exact mutation binding changed after typed forward"
            )
            return
        submit = next(
            (
                row
                for row in fresh_inventory.candidates
                if row.bid == fresh_bindings[0].submit_bid
            ),
            None,
        )
        if submit is None:
            self.method_failure = (
                "bound exact-mutation action disappeared before commit"
            )
            return
        certificate = certify_exact_mutation_commit_v6(
            current=current,
            compilation=fresh,
            candidate=submit,
            inventory=fresh_inventory.candidates,
            active_transactions=tuple(self.runtime.active),
            resolved_semantic_bids=tuple(
                sorted(self.resolved_exact_transaction_bids)
            ),
            quarantined_commit_keys=self.effect_ledger.frozen_quarantine(),
        )
        certificate = bind_complete_public_commit_certificate_v13(
            current,
            certificate,
        )
        self.audit(
            {
                "type": "exact_mutation_commit_certificate_v18_surface_v6",
                "bid": submit.bid,
                "certificate": _certificate_record(certificate),
                "fingerprint_scope": (
                    "all_retained_semantic_snapshot_fields"
                ),
            }
        )
        if not certificate.allowed:
            self.method_failure = certificate.reason
            return
        active_before = tuple(self.runtime.active)
        committed = self.runtime.commit(
            current=current,
            action=submit.action,
            certificate=certificate,
        )
        self.certified_commits += 1
        if not committed.executed or committed.halted or committed.result is None:
            self.method_failure = committed.reason
            return
        effect = self.effect_ledger.assess(
            before=current,
            after=committed.result.snapshot,
            action=submit.action,
            active_transactions=active_before,
            terminal=committed.result.terminal,
        )
        self.audit(
            {
                "type": "exact_mutation_commit_effect_v6",
                "bid": submit.bid,
                "effective": effect.effective,
                "reason": effect.reason,
                "quarantined": effect.quarantined,
                "key_sha256": effect.key_sha256,
            }
        )
        if committed.result.terminal:
            self.wrong_terminal_commits += 1
            self.method_failure = (
                "exact mutation commit terminated before evaluator"
            )
            return
        if not effect.effective:
            self.method_failure = effect.reason
            return
        self.resolved_exact_transaction_bids.add(binding.bid)
        self.method_commit_effective = True

    def run_policy(self) -> None:
        while not self.method_commit_effective and self.within_budget():
            width, height = self._viewport()
            compilation = compile_exact_mutation_goal_v6(
                self.goal,
                self.executor.snapshot,
                viewport_width=width,
                viewport_height=height,
            )
            self.final_compilation = compilation
            if compilation.allowed:
                self.target_form_reached = True
                self.scoped_field_bindings += int(
                    compilation.scoped_binding is not None
                    and compilation.scoped_binding.winning_bid is not None
                )
                self.typed_url_normalizations += int(
                    compilation.value_normalization is not None
                    and compilation.value_normalization.applied
                )
                self.joint_url_semantic_normalizations += int(
                    compilation.semantic_url_normalization is not None
                    and compilation.semantic_url_normalization.applied
                )
                self.viewport_editor_surface_bindings += int(
                    compilation.viewport_surface is not None
                )
                self.viewport_save_canonicalizations += int(
                    compilation.viewport_surface is not None
                    and len(
                        compilation.viewport_surface.commit_representation_bids
                    )
                    > 1
                )
                self.token_back_neutralization_bindings += len(
                    compilation.projection.token_back_neutralization_bids
                )
                self.execute_exact_mutation(compilation)
                break
            self.navigate_once()
            if self.method_failure is not None:
                break
        if not self.method_commit_effective and self.method_failure is None:
            self.method_failure = (
                "method stopped before an effective exact commit"
            )
        self._cleanup_failed_transaction()

    def result(self) -> dict[str, Any]:
        result = super().result()
        result["candidate"] = (
            "WebArena-exact-mutation-agent-v18-nav8-episode"
        )
        result["navigation_version"] = "public_navigation_v6"
        result["exact_mutation_version"] = (
            "joint_url_semantics_and_frozen_v5_surfaces_v6"
        )
        result["metrics"].update(
            {
                "typed_url_normalizations": self.typed_url_normalizations,
                "joint_url_semantic_normalizations": (
                    self.joint_url_semantic_normalizations
                ),
                "viewport_editor_surface_bindings": (
                    self.viewport_editor_surface_bindings
                ),
                "viewport_save_canonicalizations": (
                    self.viewport_save_canonicalizations
                ),
                "token_back_neutralization_bindings": (
                    self.token_back_neutralization_bindings
                ),
            }
        )
        return result
