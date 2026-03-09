"""
Integration tests for the Autonomous Irrigation System Petri Net.

These tests validate that the complete Petri Net model satisfies the formal
properties stated in the paper:

  * Reachability   – all expected system states are reachable
  * 1-Safeness     – each place holds ≤ 1 token in every reachable marking
  * Boundedness    – net is bounded (finite reachability graph)
  * Liveness       – all transitions can fire (L0-live); all four sensing
                     transitions are L0-live; most are L1-live
  * Deadlock-free  – no reachable marking has zero enabled transitions

Simulation tests confirm that each of the four sensor-reading scenarios
completes a full cycle and exercises the expected transitions.
"""

import pytest

from src.irrigation_model import PLACE_ORDER, build_irrigation_net
from src.simulation import SCENARIOS, simulate_random, simulate_scenario
from src.verification import check_reachability, verify


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def net():
    return build_irrigation_net()


@pytest.fixture(scope="module")
def verification_result(net):
    return verify(net)


# ---------------------------------------------------------------------------
# Model structure
# ---------------------------------------------------------------------------

class TestModelStructure:
    def test_place_count(self, net):
        assert len(net.places) == 14

    def test_transition_count(self, net):
        assert len(net.transitions) == 16

    def test_all_expected_places_present(self, net):
        for p in PLACE_ORDER:
            assert p in net.places, f"Expected place '{p}' not found"

    def test_initial_marking_has_one_idle_token(self, net):
        m0 = net.initial_marking()
        assert m0["idle"] == 1
        assert sum(m0.values()) == 1

    def test_all_expected_transitions_present(self, net):
        expected = {
            "t_start_sensing",
            "t_sense_dry_poor",
            "t_sense_dry_rich",
            "t_sense_moist_poor",
            "t_sense_moist_rich",
            "t_start_irrigation",
            "t_irrigation_complete",
            "t_skip_irrigation",
            "t_start_fertilisation",
            "t_fertilisation_complete",
            "t_skip_fertilisation",
            "t_sync_actuations",
            "t_start_logging",
            "t_log_complete",
            "t_notify",
            "t_reset",
        }
        assert set(net.transitions) == expected


# ---------------------------------------------------------------------------
# Reachability
# ---------------------------------------------------------------------------

class TestReachability:
    def test_all_places_are_reachable(self, net):
        """Every place in the model should hold a token in some reachable state."""
        for place in PLACE_ORDER:
            assert check_reachability(net, {place: 1}), \
                f"Place '{place}' is never marked in any reachable state"

    def test_idle_reachable_from_initial(self, net):
        assert check_reachability(net, {"idle": 1})

    def test_cycle_done_reachable(self, net):
        assert check_reachability(net, {"cycle_done": 1})

    def test_both_actuation_paths_reachable(self, net):
        assert check_reachability(net, {"irrigating": 1})
        assert check_reachability(net, {"fertilising": 1})

    def test_skip_paths_reachable(self, net):
        """Skip transitions must also be exercised on some path."""
        # irr_complete is reached either via irrigation or via skip
        assert check_reachability(net, {"irr_complete": 1})
        assert check_reachability(net, {"fert_complete": 1})


# ---------------------------------------------------------------------------
# Safeness (1-boundedness)
# ---------------------------------------------------------------------------

class TestSafeness:
    def test_net_is_safe(self, verification_result):
        assert verification_result.is_safe is True, (
            "The irrigation net is expected to be 1-safe (each place ≤ 1 token)"
        )

    def test_every_place_bound_is_1(self, verification_result):
        for place, bound in verification_result.place_bounds.items():
            assert bound <= 1, \
                f"Place '{place}' has bound {bound} > 1 (not 1-safe)"


# ---------------------------------------------------------------------------
# Boundedness
# ---------------------------------------------------------------------------

class TestBoundedness:
    def test_net_is_bounded(self, verification_result):
        assert verification_result.is_bounded is True

    def test_bound_is_1(self, verification_result):
        assert verification_result.bound == 1


# ---------------------------------------------------------------------------
# Liveness
# ---------------------------------------------------------------------------

class TestLiveness:
    def test_all_transitions_are_l0_live(self, verification_result):
        """Every transition must fire at least once in some execution."""
        assert verification_result.not_l0_live_transitions == [], (
            f"Dead transitions found: {verification_result.not_l0_live_transitions}"
        )

    def test_all_sensing_transitions_l0_live(self, verification_result):
        for t in [
            "t_sense_dry_poor",
            "t_sense_dry_rich",
            "t_sense_moist_poor",
            "t_sense_moist_rich",
        ]:
            assert t in verification_result.l0_live_transitions, \
                f"Sensing transition '{t}' is not L0-live"

    def test_sequential_transitions_are_l1_live(self, verification_result):
        """Transitions outside the non-deterministic sensing choice must be L1-live."""
        sequential = [
            "t_start_sensing",
            "t_start_logging",
            "t_log_complete",
            "t_notify",
            "t_reset",
        ]
        for t in sequential:
            assert t in verification_result.l1_live_transitions, \
                f"Sequential transition '{t}' should be L1-live"

    def test_all_transitions_are_l1_live(self, verification_result):
        """Because the system is cyclic (every path returns to *sensing*),
        all four sensing transitions are reachable from every state, making
        the net fully L1-live – a stronger property than expected."""
        assert verification_result.is_l1_live is True, (
            f"Not-L1-live transitions: {verification_result.not_l1_live_transitions}"
        )


# ---------------------------------------------------------------------------
# Deadlock-freeness
# ---------------------------------------------------------------------------

class TestDeadlockFreeness:
    def test_no_deadlocks(self, verification_result):
        assert verification_result.is_deadlock_free is True, (
            f"Deadlocks found: {verification_result.deadlock_markings}"
        )


# ---------------------------------------------------------------------------
# Simulation – scenario coverage
# ---------------------------------------------------------------------------

class TestSimulationScenarios:
    @pytest.mark.parametrize("scenario", list(SCENARIOS))
    def test_scenario_returns_to_idle(self, net, scenario):
        """Every scenario must end with idle = 1 (full cycle completed)."""
        trace = simulate_scenario(net, scenario)
        final_marking = trace[-1][1]
        assert final_marking.get("idle", 0) == 1, \
            f"Scenario '{scenario}' did not return to idle. Final: {final_marking}"

    @pytest.mark.parametrize("scenario", list(SCENARIOS))
    def test_scenario_fires_sensing_transition(self, net, scenario):
        transition_ids = [t for t, _ in simulate_scenario(net, scenario)]
        assert SCENARIOS[scenario] in transition_ids

    def test_dry_poor_fires_both_actuation_transitions(self, net):
        """When both sensors are low, irrigation AND fertilisation happen."""
        trace = simulate_scenario(net, "dry_poor")
        fired = {t for t, _ in trace}
        assert "t_start_irrigation" in fired
        assert "t_start_fertilisation" in fired

    def test_dry_rich_fires_only_irrigation(self, net):
        """When moisture is low but nutrient is OK, only irrigation happens."""
        trace = simulate_scenario(net, "dry_rich")
        fired = {t for t, _ in trace}
        assert "t_start_irrigation" in fired
        assert "t_skip_fertilisation" in fired
        assert "t_start_fertilisation" not in fired

    def test_moist_poor_fires_only_fertilisation(self, net):
        """When moisture is OK but nutrient is low, only fertilisation happens."""
        trace = simulate_scenario(net, "moist_poor")
        fired = {t for t, _ in trace}
        assert "t_start_fertilisation" in fired
        assert "t_skip_irrigation" in fired
        assert "t_start_irrigation" not in fired

    def test_moist_rich_fires_no_actuation(self, net):
        """When both sensors show adequate levels, no actuation occurs."""
        trace = simulate_scenario(net, "moist_rich")
        fired = {t for t, _ in trace}
        assert "t_start_irrigation" not in fired
        assert "t_start_fertilisation" not in fired
        assert "t_skip_irrigation" in fired
        assert "t_skip_fertilisation" in fired

    @pytest.mark.parametrize("scenario", list(SCENARIOS))
    def test_scenario_fires_logging_and_notify(self, net, scenario):
        trace = simulate_scenario(net, scenario)
        fired = {t for t, _ in trace}
        assert "t_start_logging" in fired
        assert "t_log_complete" in fired
        assert "t_notify" in fired

    def test_unknown_scenario_raises(self, net):
        with pytest.raises(KeyError):
            simulate_scenario(net, "bad_scenario")


# ---------------------------------------------------------------------------
# Simulation – random multi-cycle
# ---------------------------------------------------------------------------

class TestSimulationRandom:
    def test_random_simulation_completes_cycles(self, net):
        trace = simulate_random(net, num_cycles=4, seed=42)
        resets = sum(1 for t, _ in trace if t == "t_reset")
        assert resets == 4

    def test_random_all_scenarios_hit(self, net):
        """Over many cycles, all four sensing transitions should fire."""
        trace = simulate_random(net, num_cycles=50, seed=0)
        fired = {t for t, _ in trace}
        for scenario_trans in SCENARIOS.values():
            assert scenario_trans in fired, \
                f"Sensing transition '{scenario_trans}' never fired in 50 cycles"
