"""
Unit tests for src/verification.py.

Covers:
  - Verification on a known-safe cycle net
  - Verification on a known-deadlocking net
  - Boundedness/safeness checks
  - Liveness (L0 and L1) detection
  - check_reachability helper
"""

import pytest

from src.petri_net import PetriNet
from src.verification import VerificationResult, check_reachability, verify


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def cycle_net() -> PetriNet:
    """A minimal cycle: p1 → t1 → p2 → t2 → p1.  Deadlock-free, 1-safe."""
    net = PetriNet("Cycle")
    net.add_place("p1", initial_tokens=1)
    net.add_place("p2", initial_tokens=0)
    net.add_transition("t1", inputs={"p1": 1}, outputs={"p2": 1})
    net.add_transition("t2", inputs={"p2": 1}, outputs={"p1": 1})
    return net


def deadlock_net() -> PetriNet:
    """p1 → t1 → p2  (no way back from p2 → deadlock)."""
    net = PetriNet("Deadlock")
    net.add_place("p1", initial_tokens=1)
    net.add_place("p2", initial_tokens=0)
    net.add_transition("t1", inputs={"p1": 1}, outputs={"p2": 1})
    return net


def unbounded_net() -> PetriNet:
    """t_gen: {} → p1 continuously generates tokens (unbounded)."""
    net = PetriNet("Unbounded")
    net.add_place("p1", initial_tokens=1)
    net.add_place("p2", initial_tokens=0)
    net.add_transition(
        "t_gen", inputs={"p1": 1}, outputs={"p1": 2, "p2": 1}
    )
    return net


def multi_token_net() -> PetriNet:
    """p1 starts with 2 tokens; t1 fires twice.  Bound = 2."""
    net = PetriNet("MultiToken")
    net.add_place("p1", initial_tokens=2)
    net.add_place("p2", initial_tokens=0)
    net.add_transition("t1", inputs={"p1": 1}, outputs={"p2": 1})
    return net


# ---------------------------------------------------------------------------
# Reachable states
# ---------------------------------------------------------------------------

class TestReachableStates:
    def test_cycle_has_two_states(self):
        result = verify(cycle_net())
        assert result.num_reachable_states == 2

    def test_deadlock_has_two_states(self):
        result = verify(deadlock_net())
        assert result.num_reachable_states == 2


# ---------------------------------------------------------------------------
# Boundedness & Safeness
# ---------------------------------------------------------------------------

class TestBoundedness:
    def test_cycle_is_bounded(self):
        result = verify(cycle_net())
        assert result.is_bounded is True

    def test_cycle_bound_is_1(self):
        result = verify(cycle_net())
        assert result.bound == 1

    def test_cycle_is_safe(self):
        result = verify(cycle_net())
        assert result.is_safe is True

    def test_multi_token_not_safe(self):
        result = verify(multi_token_net())
        assert result.is_safe is False

    def test_multi_token_bound_is_2(self):
        result = verify(multi_token_net())
        assert result.bound == 2

    def test_place_bounds_populated(self):
        result = verify(multi_token_net())
        assert result.place_bounds["p1"] == 2
        assert result.place_bounds["p2"] == 2

    def test_unbounded_raises(self):
        with pytest.raises(RuntimeError, match="exceeded"):
            verify(unbounded_net(), max_states=10)


# ---------------------------------------------------------------------------
# Deadlock-freeness
# ---------------------------------------------------------------------------

class TestDeadlockFreeness:
    def test_cycle_is_deadlock_free(self):
        result = verify(cycle_net())
        assert result.is_deadlock_free is True
        assert result.deadlock_markings == []

    def test_deadlock_net_has_deadlock(self):
        result = verify(deadlock_net())
        assert result.is_deadlock_free is False
        assert len(result.deadlock_markings) == 1
        # The deadlock state has p2 = 1
        assert result.deadlock_markings[0].get("p2", 0) == 1


# ---------------------------------------------------------------------------
# Liveness
# ---------------------------------------------------------------------------

class TestLiveness:
    def test_cycle_all_l0_live(self):
        result = verify(cycle_net())
        assert sorted(result.l0_live_transitions) == ["t1", "t2"]
        assert result.not_l0_live_transitions == []

    def test_cycle_all_l1_live(self):
        result = verify(cycle_net())
        assert result.is_l1_live is True
        assert result.not_l1_live_transitions == []

    def test_deadlock_net_t1_is_l0_live(self):
        """t1 fires once, so it is L0-live but not L1-live."""
        result = verify(deadlock_net())
        assert "t1" in result.l0_live_transitions

    def test_deadlock_net_t1_not_l1_live(self):
        """From the deadlock state, t1 can never fire again."""
        result = verify(deadlock_net())
        assert "t1" in result.not_l1_live_transitions
        assert result.is_l1_live is False

    def test_dead_transition_not_l0_live(self):
        """A transition that can never fire is not L0-live."""
        net = PetriNet("DeadTrans")
        net.add_place("p1", initial_tokens=1)
        net.add_place("p2", initial_tokens=0)
        net.add_place("p3", initial_tokens=0)
        # t1 consumes p1 → p2, t2 consumes p3 (never has tokens)
        net.add_transition("t1", inputs={"p1": 1}, outputs={"p2": 1})
        net.add_transition("t2", inputs={"p3": 1}, outputs={"p2": 1})
        result = verify(net)
        assert "t2" in result.not_l0_live_transitions
        assert "t1" in result.l0_live_transitions


# ---------------------------------------------------------------------------
# check_reachability
# ---------------------------------------------------------------------------

class TestCheckReachability:
    def test_reachable_state(self):
        assert check_reachability(cycle_net(), {"p2": 1}) is True

    def test_unreachable_state(self):
        """p1 and p2 both holding 1 token is never reachable in cycle_net."""
        assert check_reachability(cycle_net(), {"p1": 1, "p2": 1}) is False

    def test_initial_marking_reachable(self):
        assert check_reachability(cycle_net(), {"p1": 1}) is True

    def test_partial_marking(self):
        """Partial marking: only check that p2 has 1 token (ignore p1)."""
        assert check_reachability(deadlock_net(), {"p2": 1}) is True


# ---------------------------------------------------------------------------
# VerificationResult.summary()
# ---------------------------------------------------------------------------

class TestVerificationResultSummary:
    def test_summary_contains_key_fields(self):
        result = verify(cycle_net())
        s = result.summary()
        assert "Reachable states" in s
        assert "BOUNDEDNESS" in s
        assert "SAFENESS" in s
        assert "LIVENESS" in s
        assert "DEADLOCK-FREENESS" in s

    def test_summary_shows_safe_true(self):
        result = verify(cycle_net())
        assert "Safe             : True" in result.summary()

    def test_summary_shows_deadlock_free_true(self):
        result = verify(cycle_net())
        assert "Deadlock-free    : True" in result.summary()

    def test_summary_shows_deadlock_free_false(self):
        result = verify(deadlock_net())
        assert "Deadlock-free    : False" in result.summary()
