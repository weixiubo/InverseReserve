"""Exact-mutation transfer agent with feedback isolation and PACT-v10."""

from __future__ import annotations

from typing import Any

from .pact_controller_v8 import inverse_action_cost_v8
from .pact_controller_v10 import (
    FailClosedTransactionRuntimeV10,
    InterruptRepairReservationV10,
    interrupt_repair_action_cost_v10,
)
from .typed_contracts_v4 import TransactionContractV4
from .webarena_exact_mutation_agent_v1 import (
    ExactMutationTransferAgentV1,
    PlannerGenerateV1,
    _certificate_record,
    _restoration_record,
)
from .webarena_exact_mutation_v1 import (
    certify_exact_mutation_commit_v1,
    compile_exact_mutation_goal_v1,
    compile_exact_mutation_inventory_v1,
)
from .webarena_executor_v2 import WebArenaConfirmationExecutorV2


class ExactMutationTransferAgentV2(ExactMutationTransferAgentV1):
    """Use reward-isolated execution and preserve recovery plus commit reserve."""

    method_id = "full_pact_v10_webarena_exact_mutation_v2"

    def __init__(
        self,
        *,
        environment: Any,
        observation: dict[str, Any],
        budgets: dict[str, Any],
        planner_generate: PlannerGenerateV1,
    ) -> None:
        super().__init__(
            environment=environment,
            observation=observation,
            budgets=budgets,
            planner_generate=planner_generate,
        )
        self.executor = WebArenaConfirmationExecutorV2(
            environment,
            observation,
            maximum_gui_actions=int(budgets["maximum_gui_actions"]),
        )
        self.interrupt_repair_reservation_audits = 0
        self.interrupt_repair_reservation_fallbacks = 0
        self.runtime = FailClosedTransactionRuntimeV10(
            self.executor,
            self.interrupt_repair_reservation,
        )

    def interrupt_repair_reservation(
        self, contract: TransactionContractV4
    ) -> InterruptRepairReservationV10:
        registered_inverse_reserve = sum(
            inverse_action_cost_v8(transaction.contract)
            for transaction in self.runtime.active
        ) + inverse_action_cost_v8(contract)
        reservation = InterruptRepairReservationV10(
            remaining_gui_actions=(
                int(self.budgets["maximum_gui_actions"])
                - len(self.executor.actions)
            ),
            repair_pair_actions=interrupt_repair_action_cost_v10(contract),
            registered_inverse_reserve=registered_inverse_reserve,
        )
        self.interrupt_repair_reservation_audits += 1
        self.interrupt_repair_reservation_fallbacks += int(not reservation.allowed)
        self.audit(
            {
                "type": "interrupt_repair_reservation_v10",
                "remaining_gui_actions": reservation.remaining_gui_actions,
                "repair_pair_actions": reservation.repair_pair_actions,
                "registered_inverse_reserve": (
                    reservation.registered_inverse_reserve
                ),
                "allowed": reservation.allowed,
            }
        )
        return reservation

    def execute_exact_mutation(self, compilation: Any) -> None:
        """Reserve inverse, commit, and worst-case repair before forwarding."""

        before = self.executor.snapshot
        inventory = compile_exact_mutation_inventory_v1(
            before,
            self.goal,
            compilation=compilation,
        )
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
        remaining_after_forward = (
            int(self.budgets["maximum_gui_actions"])
            - len(self.executor.actions)
            - 1
        )
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
        current = self.executor.snapshot
        fresh = compile_exact_mutation_goal_v1(self.goal, current)
        self.final_compilation = fresh
        if not fresh.allowed:
            self.method_failure = "exact mutation disappeared after typed forward"
            return
        fresh_inventory = compile_exact_mutation_inventory_v1(
            current,
            self.goal,
            compilation=fresh,
        )
        fresh_bindings = fresh.goal_contract.payload_bindings
        if len(fresh_bindings) != 1 or fresh_bindings[0].bid != binding.bid:
            self.method_failure = "exact mutation binding changed after typed forward"
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
            self.method_failure = "bound same-form action disappeared before commit"
            return
        certificate = certify_exact_mutation_commit_v1(
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
        self.audit(
            {
                "type": "exact_mutation_commit_certificate_v1",
                "bid": submit.bid,
                "certificate": _certificate_record(certificate),
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

    def result(self) -> dict[str, Any]:
        result = super().result()
        inverse_fallbacks = sum(
            event.get("type") == "compensator_grounding"
            and event.get("policy") == "inverse"
            for event in self.runtime.events
        )
        result["candidate"] = "WebArena-exact-mutation-agent-v2-episode"
        result["metrics"].update(
            {
                "interrupt_repair_reservation_audits": (
                    self.interrupt_repair_reservation_audits
                ),
                "interrupt_repair_reservation_fallbacks": (
                    self.interrupt_repair_reservation_fallbacks
                ),
                "interrupt_repair_inverse_fallbacks": inverse_fallbacks,
            }
        )
        return result
