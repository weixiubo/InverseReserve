"""WebArena exact-mutation successor with complete-public commit freshness."""

from __future__ import annotations

from typing import Any

from inversereserve.adapters.webarena.webarena_exact_mutation_agent_v1 import (
    _certificate_record,
    _restoration_record,
)
from inversereserve.adapters.webarena.webarena_exact_mutation_agent_v12 import ExactMutationTransferAgentV12
from inversereserve.adapters.webarena.webarena_exact_mutation_v1 import (
    certify_exact_mutation_commit_v1,
    compile_exact_mutation_goal_v1,
    compile_exact_mutation_inventory_v1,
)
from inversereserve.adapters.webarena.webarena_goal_adapter_v1 import PublicPayloadBindingV1
from inversereserve.controllers.confirmation_agents_v13 import complete_public_commit_metrics_v13
from inversereserve.controllers.pact_controller_v8 import inverse_action_cost_v8
from inversereserve.controllers.pact_controller_v10 import interrupt_repair_action_cost_v10
from inversereserve.controllers.pact_controller_v13 import (
    FailClosedTransactionRuntimeV13,
    bind_complete_public_commit_certificate_v13,
)
from inversereserve.core.recovery_capacity import remaining_after_action as _remaining_capacity_after_proposal


class ExactMutationTransferAgentV13(ExactMutationTransferAgentV12):
    method_id = "full_pact_v13_webarena_exact_mutation_v2"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.runtime = FailClosedTransactionRuntimeV13(self.executor, self.interrupt_repair_reservation)

    def execute_exact_mutation(self, compilation: Any) -> None:
        """Execute the frozen V2 mechanism with a complete-public certificate."""
        before = self.executor.snapshot
        inventory = compile_exact_mutation_inventory_v1(before, self.goal, compilation=compilation)
        bindings = compilation.goal_contract.payload_bindings
        if len(bindings) != 1:
            self.method_failure = "exact target form did not bind one public field"
            return
        binding = bindings[0]
        contract = inventory.contract_by_bid.get(binding.bid)
        if contract is None:
            self.method_failure = "exact target field lacks a typed transaction"
            return
        inverse_reserve = inverse_action_cost_v8(contract)
        commit_action_cost = 1
        interrupt_repair_cost = interrupt_repair_action_cost_v10(contract)
        remaining_after_forward = _remaining_capacity_after_proposal(
            self.budgets["maximum_gui_actions"], len(self.executor.actions)
        )
        required_after_forward = inverse_reserve + commit_action_cost + interrupt_repair_cost
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
            self.method_failure = "inverse, commit, and repair budget reservation stopped mutation"
            return
        opened = self.runtime.transact(before=before, contract=contract, candidate_label=binding.label)
        self.typed_transactions += 1
        if opened.restoration is not None:
            self.restorations.append(_restoration_record(opened.restoration))
        self.audit(
            {
                "type": "exact_mutation_transaction_result_v1",
                "bid": binding.bid,
                "admitted": opened.admitted,
                "reason": opened.reason,
                "interrupt_repairs": opened.interrupt_repairs,
                "halted": opened.halted,
            }
        )
        if not opened.admitted or opened.halted:
            self.method_failure = opened.reason
            return
        self._certify_and_commit_v13(binding)

    def result(self) -> dict[str, Any]:
        result = super().result()
        result["candidate"] = "WebArena-exact-mutation-agent-v13-episode"
        result["metrics"].update(complete_public_commit_metrics_v13(self))
        return result

    def _certify_and_commit_v13(self, binding: PublicPayloadBindingV1) -> None:
        """Revalidate and commit the admitted mutation."""
        current = self.executor.snapshot
        fresh = compile_exact_mutation_goal_v1(self.goal, current)
        self.final_compilation = fresh
        if not fresh.allowed:
            self.method_failure = "exact mutation disappeared after typed forward"
            return
        fresh_inventory = compile_exact_mutation_inventory_v1(current, self.goal, compilation=fresh)
        fresh_bindings = fresh.goal_contract.payload_bindings
        if len(fresh_bindings) != 1 or fresh_bindings[0].bid != binding.bid:
            self.method_failure = "exact mutation binding changed after typed forward"
            return
        submit = next(
            (row for row in fresh_inventory.candidates if row.bid == fresh_bindings[0].submit_bid), None
        )
        if submit is None:
            self.method_failure = "bound same-form action disappeared before commit"
            return
        certificate = certify_exact_mutation_commit_v1(
            current=current,
            compilation=fresh,
            candidate=submit,
            inventory=fresh_inventory.candidates,
            active_transactions=tuple(self.runtime.active),
            resolved_semantic_bids=tuple(sorted(self.resolved_exact_transaction_bids)),
            quarantined_commit_keys=self.effect_ledger.frozen_quarantine(),
        )
        certificate = bind_complete_public_commit_certificate_v13(current, certificate)
        self.audit(
            {
                "type": "exact_mutation_commit_certificate_v13",
                "bid": submit.bid,
                "certificate": _certificate_record(certificate),
                "fingerprint_scope": "all_retained_semantic_snapshot_fields",
            }
        )
        if not certificate.allowed:
            self.method_failure = certificate.reason
            return
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
                "type": "exact_mutation_commit_effect_v1",
                "bid": submit.bid,
                "effective": effect.effective,
                "reason": effect.reason,
                "quarantined": effect.quarantined,
                "key_sha256": effect.key_sha256,
            }
        )
        if committed.result.terminal:
            self.wrong_terminal_commits += 1
            self.method_failure = "exact mutation commit terminated before evaluator"
            return
        if not effect.effective:
            self.method_failure = effect.reason
            return
        self.resolved_exact_transaction_bids.add(binding.bid)
        self.method_commit_effective = True
