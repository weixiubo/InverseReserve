"""WebArena development agent for public multi-field InverseReserve stacks."""

from __future__ import annotations

from typing import Any

from inversereserve.adapters.webarena.webarena_exact_mutation_agent_v1 import (
    _certificate_record,
    _restoration_record,
)
from inversereserve.adapters.webarena.webarena_exact_mutation_agent_v15_nav5 import (
    ExactMutationTransferAgentV15Nav5,
)
from inversereserve.adapters.webarena.webarena_exact_mutation_agent_v18_nav8 import (
    ExactMutationTransferAgentV18Nav8,
)
from inversereserve.adapters.webarena.webarena_multifield_v1 import (
    MultiFieldCompilationV1,
    certify_multifield_commit_v1,
    compile_multifield_goal_v1,
    compile_multifield_inventory_v1,
)
from inversereserve.controllers.pact_controller_v8 import inverse_action_cost_v8
from inversereserve.controllers.pact_controller_v10 import interrupt_repair_action_cost_v10
from inversereserve.controllers.pact_controller_v13 import bind_complete_public_commit_certificate_v13
from inversereserve.core.recovery_capacity import remaining_after_action as _remaining_capacity_after_proposal


class MultiFieldInverseReserveAgentV1(ExactMutationTransferAgentV18Nav8):
    """Execute one public form as a stack of typed field transactions."""

    method_id = "inversereserve_webarena_multifield_v1"
    reserve_scope = "stack_wide"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.maximum_live_obligation_depth = 0
        self.multifield_forms_compiled = 0
        self.multifield_forwards = 0
        self.multifield_commit_reservations = 0
        self.minimum_stack_wide_slack: int | None = None
        self.initial_binding_identity: tuple[tuple[str, str], ...] = ()

    def _deterministic_navigation_decision(self, *, inventory: Any, recovery_detected: bool) -> Any:
        return ExactMutationTransferAgentV15Nav5._deterministic_navigation_decision(
            self, inventory=inventory, recovery_detected=recovery_detected
        )

    @staticmethod
    def _binding_identity(compilation: MultiFieldCompilationV1) -> tuple[tuple[str, str], ...]:
        return tuple(
            ((binding.binding_kind, binding.bid) for binding in compilation.goal_contract.payload_bindings)
        )

    def _record_slack(self, slack: int) -> None:
        if self.minimum_stack_wide_slack is None:
            self.minimum_stack_wide_slack = slack
        else:
            self.minimum_stack_wide_slack = min(self.minimum_stack_wide_slack, slack)

    def _fresh_compilation(self) -> MultiFieldCompilationV1 | None:
        fresh = compile_multifield_goal_v1(self.goal, self.executor.snapshot)
        self.final_compilation = fresh
        if not fresh.allowed:
            self.method_failure = "multi-field public form disappeared during execution"
            return None
        if self._binding_identity(fresh) != self.initial_binding_identity:
            self.method_failure = "multi-field public binding identity changed after a forward"
            return None
        return fresh

    def _reserve_forward(self, *, binding: Any, contract: Any) -> bool:
        active_reserve = sum(
            (inverse_action_cost_v8(transaction.contract) for transaction in self.runtime.active)
        )
        proposal_reserve = inverse_action_cost_v8(contract)
        commit_reserve = 1
        repair_reserve = interrupt_repair_action_cost_v10(contract)
        stack_wide_required = active_reserve + proposal_reserve + commit_reserve + repair_reserve
        remaining_after_forward = _remaining_capacity_after_proposal(
            self.budgets["maximum_gui_actions"], len(self.executor.actions)
        )
        slack = remaining_after_forward - stack_wide_required
        self._record_slack(slack)
        allowed = slack >= 0
        self.inverse_reservation_audits += 1
        self.audit(
            {
                "type": "webarena_multifield_stack_reservation_v1",
                "reservation_rule": self.reserve_scope,
                "bid": binding.bid,
                "binding_kind": binding.binding_kind,
                "active_inverse_cost": active_reserve,
                "proposal_inverse_cost": proposal_reserve,
                "commit_action_cost": commit_reserve,
                "interrupt_repair_action_cost": repair_reserve,
                "stack_wide_required_after_forward": stack_wide_required,
                "remaining_after_forward": remaining_after_forward,
                "stack_wide_slack": slack,
                "allowed": allowed,
            }
        )
        if not allowed:
            self.inverse_reservation_stops += 1
            self.method_failure = "complete multi-field inverse stack and commit no longer fit"
        return allowed

    def _execute_field(self, binding_kind: str) -> bool:
        fresh = self._fresh_compilation()
        if fresh is None:
            return False
        binding = next(
            (row for row in fresh.goal_contract.payload_bindings if row.binding_kind == binding_kind), None
        )
        if binding is None:
            self.method_failure = "declared multi-field binding disappeared"
            return False
        inventory = compile_multifield_inventory_v1(self.executor.snapshot, self.goal, compilation=fresh)
        contract = inventory.contract_by_bid.get(binding.bid)
        if contract is None:
            self.method_failure = "multi-field target lacks a typed transaction"
            return False
        if not self._reserve_forward(binding=binding, contract=contract):
            return False
        opened = self.runtime.transact(
            before=self.executor.snapshot, contract=contract, candidate_label=binding.label
        )
        self.typed_transactions += 1
        self.multifield_forwards += 1
        if opened.restoration is not None:
            self.restorations.append(_restoration_record(opened.restoration))
        self.maximum_live_obligation_depth = max(self.maximum_live_obligation_depth, len(self.runtime.active))
        self.audit(
            {
                "type": "webarena_multifield_transaction_result_v1",
                "bid": binding.bid,
                "binding_kind": binding.binding_kind,
                "admitted": opened.admitted,
                "reason": opened.reason,
                "interrupt_repairs": opened.interrupt_repairs,
                "halted": opened.halted,
                "live_obligation_depth": len(self.runtime.active),
            }
        )
        if not opened.admitted or opened.halted:
            self.method_failure = opened.reason
            return False
        return True

    def _commit_multifield(self) -> None:
        fresh = self._fresh_compilation()
        if fresh is None:
            return
        inventory = compile_multifield_inventory_v1(self.executor.snapshot, self.goal, compilation=fresh)
        submit_bids = {binding.submit_bid for binding in fresh.goal_contract.payload_bindings}
        if len(submit_bids) != 1:
            self.method_failure = "multi-field form lost its unique commit"
            return
        submit_bid = next(iter(submit_bids))
        submit = next((row for row in inventory.candidates if row.bid == submit_bid), None)
        if submit is None:
            self.method_failure = "bound multi-field commit disappeared"
            return
        active_reserve = sum(
            (inverse_action_cost_v8(transaction.contract) for transaction in self.runtime.active)
        )
        remaining_after_commit = _remaining_capacity_after_proposal(
            self.budgets["maximum_gui_actions"], len(self.executor.actions)
        )
        slack = remaining_after_commit - active_reserve
        self._record_slack(slack)
        allowed = slack >= 0
        self.multifield_commit_reservations += 1
        self.audit(
            {
                "type": "webarena_multifield_commit_reservation_v1",
                "active_inverse_cost": active_reserve,
                "remaining_after_commit": remaining_after_commit,
                "stack_wide_slack": slack,
                "allowed": allowed,
            }
        )
        if not allowed:
            self.inverse_reservation_stops += 1
            self.method_failure = "multi-field terminal action would consume active inverse reserve"
            return
        return self._execute_multifield_commit(fresh, inventory, submit)

    def execute_multifield(self, compilation: MultiFieldCompilationV1) -> None:
        self.multifield_forms_compiled += 1
        self.initial_binding_identity = self._binding_identity(compilation)
        for binding_kind, _bid in self.initial_binding_identity:
            if not self._execute_field(binding_kind):
                return
        self._commit_multifield()

    def run_policy(self) -> None:
        while not self.method_commit_effective and self.within_budget():
            compilation = compile_multifield_goal_v1(self.goal, self.executor.snapshot)
            self.final_compilation = compilation
            if compilation.allowed:
                self.target_form_reached = True
                self.execute_multifield(compilation)
                break
            self.navigate_once()
            if self.method_failure is not None:
                break
        if not self.method_commit_effective and self.method_failure is None:
            self.method_failure = "method stopped before an effective multi-field commit"
        self._cleanup_failed_transaction()

    def result(self) -> dict[str, Any]:
        result = super().result()
        result["candidate"] = "WebArena-multifield-InverseReserve-v1-episode"
        result["exact_mutation_version"] = "public_multifield_stack_v1"
        result["metrics"].update(
            {
                "multifield_forms_compiled": self.multifield_forms_compiled,
                "multifield_forwards": self.multifield_forwards,
                "maximum_live_obligation_depth": self.maximum_live_obligation_depth,
                "multifield_commit_reservations": self.multifield_commit_reservations,
                "minimum_stack_wide_slack": self.minimum_stack_wide_slack,
            }
        )
        return result

    def _execute_multifield_commit(self, fresh: MultiFieldCompilationV1, inventory: Any, submit: Any) -> None:
        certificate = certify_multifield_commit_v1(
            current=self.executor.snapshot,
            compilation=fresh,
            candidate=submit,
            inventory=inventory.candidates,
            active_transactions=tuple(self.runtime.active),
            quarantined_commit_keys=self.effect_ledger.frozen_quarantine(),
        )
        certificate = bind_complete_public_commit_certificate_v13(self.executor.snapshot, certificate)
        self.audit(
            {
                "type": "webarena_multifield_commit_certificate_v1",
                "bid": submit.bid,
                "certificate": _certificate_record(certificate),
            }
        )
        if not certificate.allowed:
            self.method_failure = certificate.reason
            return
        current = self.executor.snapshot
        active_before = tuple(self.runtime.active)
        committed = self.runtime.commit(current=current, action=submit.action, certificate=certificate)
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
                "type": "webarena_multifield_commit_effect_v1",
                "bid": submit.bid,
                "effective": effect.effective,
                "reason": effect.reason,
                "quarantined": effect.quarantined,
                "key_sha256": effect.key_sha256,
            }
        )
        if committed.result.terminal:
            self.wrong_terminal_commits += 1
            self.method_failure = "multi-field commit terminated before official evaluation"
            return
        if not effect.effective:
            self.method_failure = effect.reason
            return
        self.resolved_exact_transaction_bids.update(
            (binding.bid for binding in fresh.goal_contract.payload_bindings)
        )
        self.runtime.consume_active_after_effective_commit("effective freshly certified multi-field commit")
        self.method_commit_effective = True


__all__ = ["MultiFieldInverseReserveAgentV1"]
