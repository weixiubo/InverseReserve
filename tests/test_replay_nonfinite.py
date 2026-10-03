import pytest

from inversereserve.replay import ReplayEnvironment, builtin_record


@pytest.mark.parametrize("reward", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_replay_reward_fails_before_execution(reward):
    record = builtin_record()
    record["steps"][0]["reward"] = reward
    with pytest.raises(ValueError, match="action/reward"):
        ReplayEnvironment(record)
