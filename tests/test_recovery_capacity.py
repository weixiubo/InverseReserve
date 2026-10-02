from types import SimpleNamespace

import pytest

from inversereserve.controllers.pact_controller_v8 import inverse_action_cost_v8 as compatible_cost
from inversereserve.core.commit_ledger import CommitEffectLedgerV8 as CanonicalLedger
from inversereserve.core.effect_ledger_v8 import CommitEffectLedgerV8
from inversereserve.core.recovery_capacity import inverse_action_cost_v8, remaining_after_action


@pytest.mark.parametrize("maximum,used,expected", [(0, 0, -1), (2, 2, -1), (3, 2, 0), (4, 2, 1), (40, 7, 32)])
def test_capacity_does_not_clamp_or_forget_proposed_action(maximum, used, expected):
    assert remaining_after_action(maximum, used) == expected


def test_dynamic_inverse_is_one_action_and_static_inverse_counts_every_step():
    assert (
        inverse_action_cost_v8(
            SimpleNamespace(dynamic_inverse_class_token="class", inverse_actions=(1, 2, 3))
        )
        == 1
    )
    assert (
        inverse_action_cost_v8(SimpleNamespace(dynamic_inverse_class_token=None, inverse_actions=(1, 2, 3)))
        == 3
    )
    assert inverse_action_cost_v8(SimpleNamespace(dynamic_inverse_class_token=None, inverse_actions=())) == 0


def test_old_imports_refer_to_the_same_implementations():
    assert compatible_cost is inverse_action_cost_v8
    assert CanonicalLedger is CommitEffectLedgerV8
