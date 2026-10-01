"""Public commit-effect ledger for PACT-v8."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from .pact_grounding_v8 import commit_attempt_key_v8
from .transaction_actions_v4 import ContractActionV4
from .typed_observation import SemanticSnapshot


def _sha(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode(
            "utf-8"
        )
    ).hexdigest()


@dataclass(frozen=True)
class CommitEffectV8:
    effective: bool
    reason: str
    before_sha256: str
    after_sha256: str
    key_sha256: str
    quarantined: bool


class CommitEffectLedgerV8:
    def __init__(self) -> None:
        self.quarantined_keys: set[tuple[object, ...]] = set()
        self.records: list[dict[str, Any]] = []

    def assess(
        self,
        *,
        before: SemanticSnapshot,
        after: SemanticSnapshot,
        action: ContractActionV4,
        active_transactions: tuple[Any, ...],
        terminal: bool,
    ) -> CommitEffectV8:
        key = commit_attempt_key_v8(
            current=before,
            action=action,
            active_transactions=active_transactions,
        )
        before_fingerprint = before.semantic_fingerprint()
        after_fingerprint = after.semantic_fingerprint()
        changed = before_fingerprint != after_fingerprint
        effective = bool(terminal or changed)
        quarantined = not effective
        if quarantined:
            self.quarantined_keys.add(key)
        record = CommitEffectV8(
            effective=effective,
            reason=(
                "commit terminated the episode or changed public semantic state"
                if effective
                else "nonterminal commit produced zero public semantic effect"
            ),
            before_sha256=_sha(before_fingerprint),
            after_sha256=_sha(after_fingerprint),
            key_sha256=_sha(key),
            quarantined=quarantined,
        )
        self.records.append(
            {
                "effective": record.effective,
                "reason": record.reason,
                "before_sha256": record.before_sha256,
                "after_sha256": record.after_sha256,
                "key_sha256": record.key_sha256,
                "quarantined": record.quarantined,
                "action": {
                    "operation": action.operation,
                    "bid": action.bid,
                    "argument": action.argument,
                    "enable_autocomplete_menu": action.enable_autocomplete_menu,
                },
            }
        )
        return record

    def frozen_quarantine(self) -> frozenset[tuple[object, ...]]:
        return frozenset(self.quarantined_keys)
