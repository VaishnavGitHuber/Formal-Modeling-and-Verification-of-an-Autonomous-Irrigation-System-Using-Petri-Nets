"""
Unit tests for src/petri_net.py.

Tests cover:
  - Place and transition creation
  - Enabling conditions
  - Firing rule (correct token movement, immutability of input marking)
  - Error handling (unknown transitions, not-enabled firing, negative tokens)
  - Reachability graph construction
  - Marking-to-tuple serialisation
"""

import pytest

from src.petri_net import PetriNet


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def simple_net() -> PetriNet:
    """A minimal two-place, one-transition net for basic tests."""
    net = PetriNet("Simple")
    net.add_place("p1", initial_tokens=1, label="Place 1")
    net.add_place("p2", initial_tokens=0, label="Place 2")
    net.add_transition("t1", inputs={"p1": 1}, outputs={"p2": 1}, label="Move")
    return net


def cycle_net() -> PetriNet:
    """A two-place cycle (p1 → t1 → p2 → t2 → p1)."""
    net = PetriNet("Cycle")
    net.add_place("p1", initial_tokens=1)
    net.add_place("p2", initial_tokens=0)
    net.add_transition("t1", inputs={"p1": 1}, outputs={"p2": 1})
    net.add_transition("t2", inputs={"p2": 1}, outputs={"p1": 1})
    return net


# ---------------------------------------------------------------------------
# Place creation
# ---------------------------------------------------------------------------

class TestAddPlace:
    def test_basic(self):
        net = PetriNet()
        net.add_place("p1", initial_tokens=3, label="My Place")
        assert "p1" in net.places
        assert net.initial_marking()["p1"] == 3
        assert net.place_label("p1") == "My Place"

    def test_default_label(self):
        net = PetriNet()
        net.add_place("alpha")
        assert net.place_label("alpha") == "alpha"

    def test_zero_tokens_allowed(self):
        net = PetriNet()
        net.add_place("p", initial_tokens=0)
        assert net.initial_marking()["p"] == 0

    def test_negative_tokens_rejected(self):
        net = PetriNet()
        with pytest.raises(ValueError, match="≥ 0"):
            net.add_place("bad", initial_tokens=-1)

    def test_method_chaining(self):
        net = PetriNet()
        result = net.add_place("p1")
        assert result is net


# ---------------------------------------------------------------------------
# Transition creation
# ---------------------------------------------------------------------------

class TestAddTransition:
    def test_basic(self):
        net = simple_net()
        assert "t1" in net.transitions
        assert net.transition_label("t1") == "Move"

    def test_unknown_place_rejected(self):
        net = PetriNet()
        net.add_place("p1")
        with pytest.raises(ValueError, match="does not exist"):
            net.add_transition("t1", inputs={"p_missing": 1}, outputs={"p1": 1})

    def test_method_chaining(self):
        net = PetriNet()
        net.add_place("p1")
        net.add_place("p2")
        result = net.add_transition("t1", inputs={"p1": 1}, outputs={"p2": 1})
        assert result is net


# ---------------------------------------------------------------------------
# Enabling
# ---------------------------------------------------------------------------

class TestIsEnabled:
    def test_enabled_when_sufficient_tokens(self):
        net = simple_net()
        m = {"p1": 1, "p2": 0}
        assert net.is_enabled("t1", m) is True

    def test_not_enabled_when_no_tokens(self):
        net = simple_net()
        m = {"p1": 0, "p2": 0}
        assert net.is_enabled("t1", m) is False

    def test_not_enabled_when_insufficient_tokens(self):
        net = PetriNet()
        net.add_place("p1", initial_tokens=1)
        net.add_place("p2")
        net.add_transition("t1", inputs={"p1": 2}, outputs={"p2": 1})
        m = {"p1": 1, "p2": 0}
        assert net.is_enabled("t1", m) is False

    def test_enabled_with_arc_weight(self):
        net = PetriNet()
        net.add_place("p1", initial_tokens=2)
        net.add_place("p2")
        net.add_transition("t1", inputs={"p1": 2}, outputs={"p2": 1})
        m = {"p1": 2, "p2": 0}
        assert net.is_enabled("t1", m) is True

    def test_unknown_transition_raises(self):
        net = simple_net()
        with pytest.raises(ValueError, match="Unknown transition"):
            net.is_enabled("t_nonexistent", {"p1": 1})


# ---------------------------------------------------------------------------
# Firing
# ---------------------------------------------------------------------------

class TestFire:
    def test_fire_basic(self):
        net = simple_net()
        m0 = {"p1": 1, "p2": 0}
        m1 = net.fire("t1", m0)
        assert m1["p1"] == 0
        assert m1["p2"] == 1

    def test_fire_does_not_mutate_input(self):
        net = simple_net()
        m0 = {"p1": 1, "p2": 0}
        original = dict(m0)
        net.fire("t1", m0)
        assert m0 == original

    def test_fire_not_enabled_raises(self):
        net = simple_net()
        m = {"p1": 0, "p2": 0}
        with pytest.raises(ValueError, match="not enabled"):
            net.fire("t1", m)

    def test_fire_with_weight_2(self):
        net = PetriNet()
        net.add_place("p1", initial_tokens=3)
        net.add_place("p2")
        net.add_transition("t1", inputs={"p1": 2}, outputs={"p2": 1})
        m1 = net.fire("t1", {"p1": 3, "p2": 0})
        assert m1["p1"] == 1
        assert m1["p2"] == 1

    def test_cycle(self):
        net = cycle_net()
        m0 = net.initial_marking()  # {p1: 1, p2: 0}
        m1 = net.fire("t1", m0)
        assert m1["p1"] == 0
        assert m1["p2"] == 1
        m2 = net.fire("t2", m1)
        assert m2["p1"] == 1
        assert m2["p2"] == 0


# ---------------------------------------------------------------------------
# Enabled transitions list
# ---------------------------------------------------------------------------

class TestEnabledTransitions:
    def test_initial_state(self):
        net = simple_net()
        enabled = net.enabled_transitions(net.initial_marking())
        assert enabled == ["t1"]

    def test_empty_when_no_tokens(self):
        net = simple_net()
        assert net.enabled_transitions({"p1": 0, "p2": 0}) == []

    def test_conflict_both_enabled(self):
        """Both t1 and t2 consume from p1; both should appear as enabled."""
        net = PetriNet()
        net.add_place("p1", initial_tokens=1)
        net.add_place("p2")
        net.add_place("p3")
        net.add_transition("t1", inputs={"p1": 1}, outputs={"p2": 1})
        net.add_transition("t2", inputs={"p1": 1}, outputs={"p3": 1})
        enabled = sorted(net.enabled_transitions({"p1": 1, "p2": 0, "p3": 0}))
        assert enabled == ["t1", "t2"]


# ---------------------------------------------------------------------------
# Reachability graph
# ---------------------------------------------------------------------------

class TestReachabilityGraph:
    def test_simple_two_states(self):
        net = simple_net()
        states, edges = net.reachability_graph()
        # Should have exactly 2 states: {p1:1} and {p2:1}
        assert len(states) == 2

    def test_cycle_three_states(self):
        """The cycle net has 2 distinct states reachable from {p1:1}."""
        net = cycle_net()
        states, edges = net.reachability_graph()
        assert len(states) == 2

    def test_edges_correct(self):
        net = simple_net()
        states, edges = net.reachability_graph()
        init_key = PetriNet._marking_key(net.initial_marking())
        # There must be exactly one outgoing edge from the initial state
        assert len(edges[init_key]) == 1
        trans_id, _ = edges[init_key][0]
        assert trans_id == "t1"

    def test_max_states_guard(self):
        """An unbounded net should raise when max_states is exceeded."""
        # p1 → t_gen → p1 + p2  accumulates tokens indefinitely
        net = PetriNet()
        net.add_place("p1", initial_tokens=1)
        net.add_place("p2")
        net.add_transition("t_gen", inputs={"p1": 1}, outputs={"p1": 2, "p2": 1})
        with pytest.raises(RuntimeError, match="exceeded"):
            net.reachability_graph(max_states=5)


# ---------------------------------------------------------------------------
# Marking key
# ---------------------------------------------------------------------------

class TestMarkingKey:
    def test_empty_marking(self):
        key = PetriNet._marking_key({"p1": 0, "p2": 0})
        assert key == ()

    def test_non_zero_only(self):
        key = PetriNet._marking_key({"p1": 1, "p2": 0, "p3": 2})
        assert set(key) == {("p1", 1), ("p3", 2)}

    def test_sorted_order(self):
        k1 = PetriNet._marking_key({"b": 1, "a": 1})
        k2 = PetriNet._marking_key({"a": 1, "b": 1})
        assert k1 == k2


# ---------------------------------------------------------------------------
# Repr
# ---------------------------------------------------------------------------

def test_repr():
    net = simple_net()
    r = repr(net)
    assert "Simple" in r
    assert "places=2" in r
    assert "transitions=1" in r
