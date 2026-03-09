"""
Simulation engine for the Autonomous Irrigation System Petri Net.

Supports two modes:
  * Automatic – a scenario name selects which sensing transition to fire
    so that the caller can deterministically exercise all four sensor
    outcome paths.
  * Interactive – enabled transitions are printed and the user (or a test
    harness) supplies the transition to fire at each step.

Example usage::

    from src.irrigation_model import build_irrigation_net
    from src.simulation import simulate_scenario

    net = build_irrigation_net()
    trace = simulate_scenario(net, scenario="dry_poor", verbose=True)
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple

from src.petri_net import PetriNet

# Four deterministic sensing scenarios (names map to transition IDs)
SCENARIOS: Dict[str, str] = {
    "dry_poor":   "t_sense_dry_poor",    # moisture LOW, nutrient LOW
    "dry_rich":   "t_sense_dry_rich",    # moisture LOW, nutrient OK
    "moist_poor": "t_sense_moist_poor",  # moisture OK,  nutrient LOW
    "moist_rich": "t_sense_moist_rich",  # moisture OK,  nutrient OK
}

# Number of steps after which the simulation is forcibly stopped (safety guard)
_MAX_STEPS = 200


def simulate_scenario(
    net: PetriNet,
    scenario: str,
    verbose: bool = False,
) -> List[Tuple[str, Dict[str, int]]]:
    """
    Run a complete one-cycle simulation for the given sensing *scenario*.

    The simulation fires ``t_start_sensing`` deterministically, then fires
    the sensing transition selected by *scenario*, and from that point
    fires enabled transitions greedily (alphabetical order) until either no
    transitions remain enabled or the cycle resets to the *idle* place.

    Args:
        net:      The Petri Net (returned by ``build_irrigation_net()``).
        scenario: One of ``"dry_poor"``, ``"dry_rich"``,
                  ``"moist_poor"``, or ``"moist_rich"``.
        verbose:  If True, print each step to stdout.

    Returns:
        A list of ``(transition_id, resulting_marking)`` tuples representing
        the firing trace, starting **after** the initial marking.

    Raises:
        KeyError: If *scenario* is not recognised.
    """
    if scenario not in SCENARIOS:
        raise KeyError(
            f"Unknown scenario {scenario!r}. "
            f"Valid options: {list(SCENARIOS)}"
        )

    sensing_transition = SCENARIOS[scenario]
    marking = net.initial_marking()
    trace: List[Tuple[str, Dict[str, int]]] = []

    def _step(trans_id: str) -> None:
        nonlocal marking
        marking = net.fire(trans_id, marking)
        trace.append((trans_id, dict(marking)))
        if verbose:
            active = {p: c for p, c in marking.items() if c > 0}
            label = net.transition_label(trans_id)
            print(f"  Fired: [{trans_id}] {label}")
            print(f"  Marking: {active}")

    if verbose:
        print(f"\n{'=' * 60}")
        print(f"  SIMULATION  –  Scenario: {scenario!r}")
        print(f"{'=' * 60}")
        print(f"  Initial marking: {{idle: 1}}")

    # Step 1 – start sensing (deterministic)
    _step("t_start_sensing")

    # Step 2 – fire the scenario-specific sensing transition
    _step(sensing_transition)

    # Step 3 – fire remaining transitions greedily until idle regained
    for _ in range(_MAX_STEPS):
        enabled = net.enabled_transitions(marking)
        if not enabled:
            break
        # Fire non-sensing transitions first (sorted for determinism)
        non_sensing = [
            t for t in sorted(enabled)
            if not t.startswith("t_sense_")
        ]
        if non_sensing:
            _step(non_sensing[0])
        elif enabled:
            _step(sorted(enabled)[0])
        # Stop once we are back at idle
        if marking.get("idle", 0) == 1:
            break

    if verbose:
        print(f"  Simulation complete. {len(trace)} transitions fired.")

    return trace


def simulate_random(
    net: PetriNet,
    num_cycles: int = 5,
    seed: Optional[int] = None,
    verbose: bool = False,
) -> List[Tuple[str, Dict[str, int]]]:
    """
    Run *num_cycles* full cycles using random transition selection.

    This exercises all non-deterministic paths over multiple cycles.

    Args:
        net:        The Petri Net.
        num_cycles: How many idle → idle cycles to complete.
        seed:       Optional random seed for reproducibility.
        verbose:    If True, print each step to stdout.

    Returns:
        Full firing trace as a list of ``(transition_id, marking)`` tuples.
    """
    rng = random.Random(seed)
    marking = net.initial_marking()
    trace: List[Tuple[str, Dict[str, int]]] = []
    cycles_completed = 0

    if verbose:
        print(f"\n{'=' * 60}")
        print(f"  RANDOM SIMULATION  –  {num_cycles} cycle(s), seed={seed}")
        print(f"{'=' * 60}")

    for _ in range(_MAX_STEPS * num_cycles):
        enabled = net.enabled_transitions(marking)
        if not enabled:
            break
        trans_id = rng.choice(sorted(enabled))
        marking = net.fire(trans_id, marking)
        trace.append((trans_id, dict(marking)))
        if verbose:
            active = {p: c for p, c in marking.items() if c > 0}
            print(f"  Fired: [{trans_id}] → {active}")
        if trans_id == "t_reset":
            cycles_completed += 1
            if cycles_completed >= num_cycles:
                break

    if verbose:
        print(
            f"  Done. {len(trace)} transitions fired across "
            f"{cycles_completed} cycle(s)."
        )

    return trace
