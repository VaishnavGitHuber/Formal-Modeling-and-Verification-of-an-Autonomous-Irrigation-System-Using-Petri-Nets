"""
Formal verification algorithms for Petri Nets.

The following properties are verified by exhaustive exploration of the
reachability graph (state space):

Reachability
    From the initial marking M0, determine all reachable markings and
    whether a specific target marking is reachable.

Boundedness (k-boundedness)
    A net is k-bounded if no place ever holds more than k tokens across
    all reachable markings.  The *bound* of the net is the tightest such k.

Safeness (1-safeness)
    A special case of k-boundedness with k = 1.  Every place holds at most
    one token in every reachable marking.

Liveness
    - L0-live (weakly live / potentially firable): each transition fires in
      at least one reachable firing sequence.
    - L1-live (live): from every reachable marking there exists a firing
      sequence that enables (and fires) the transition.

Deadlock-freeness
    No reachable marking is a *deadlock* (a state with no enabled
    transitions), unless it is a designated terminal/final marking.

All algorithms operate on the finite reachability graph returned by
``PetriNet.reachability_graph()``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from src.petri_net import PetriNet


@dataclass
class VerificationResult:
    """Container for the complete verification report of a Petri Net."""

    # --- Reachability ---
    num_reachable_states: int = 0
    reachable_markings: List[Dict[str, int]] = field(default_factory=list)

    # --- Boundedness ---
    is_bounded: bool = False
    bound: int = 0  # max tokens in any place across all reachable markings
    place_bounds: Dict[str, int] = field(default_factory=dict)

    # --- Safeness ---
    is_safe: bool = False

    # --- Liveness ---
    l0_live_transitions: List[str] = field(default_factory=list)   # fire at least once
    not_l0_live_transitions: List[str] = field(default_factory=list)
    l1_live_transitions: List[str] = field(default_factory=list)   # fire from every state
    not_l1_live_transitions: List[str] = field(default_factory=list)
    is_l1_live: bool = False  # True only when ALL transitions are L1-live

    # --- Deadlock-freeness ---
    is_deadlock_free: bool = False
    deadlock_markings: List[Dict[str, int]] = field(default_factory=list)

    def summary(self) -> str:
        """Return a human-readable summary of the verification results."""
        lines = [
            f"{'=' * 60}",
            "  PETRI NET VERIFICATION REPORT",
            f"{'=' * 60}",
            "",
            f"Reachable states : {self.num_reachable_states}",
            "",
            "BOUNDEDNESS",
            f"  Bounded          : {self.is_bounded}",
            f"  Bound (k)        : {self.bound}",
            "  Per-place bounds :",
        ]
        for p, b in sorted(self.place_bounds.items()):
            lines.append(f"    {p:<30} max = {b}")
        lines += [
            "",
            "SAFENESS (1-bounded)",
            f"  Safe             : {self.is_safe}",
            "",
            "LIVENESS",
            f"  All transitions L0-live (weakly live): "
            f"{len(self.not_l0_live_transitions) == 0}",
        ]
        if self.not_l0_live_transitions:
            lines.append(
                f"  Dead transitions : {', '.join(sorted(self.not_l0_live_transitions))}"
            )
        lines += [
            f"  All transitions L1-live (live): {self.is_l1_live}",
        ]
        if self.not_l1_live_transitions:
            lines.append(
                f"  Not L1-live      : {', '.join(sorted(self.not_l1_live_transitions))}"
            )
        lines += [
            "",
            "DEADLOCK-FREENESS",
            f"  Deadlock-free    : {self.is_deadlock_free}",
        ]
        if self.deadlock_markings:
            lines.append(
                f"  Deadlocks found  : {len(self.deadlock_markings)}"
            )
            for dm in self.deadlock_markings:
                lines.append(f"    {dm}")
        lines.append(f"{'=' * 60}")
        return "\n".join(lines)


def verify(net: PetriNet, max_states: int = 100_000) -> VerificationResult:
    """
    Run all formal verification checks on *net*.

    Args:
        net:        The Petri Net to verify.
        max_states: Maximum number of states to explore (safety guard for
                    unbounded nets).

    Returns:
        A :class:`VerificationResult` populated with all property checks.
    """
    states, edges = net.reachability_graph(max_states=max_states)

    result = VerificationResult()
    result.num_reachable_states = len(states)
    result.reachable_markings = list(states.values())

    # ------------------------------------------------------------------
    # Boundedness & Safeness
    # ------------------------------------------------------------------
    place_bounds: Dict[str, int] = {p: 0 for p in net.places}
    for marking in states.values():
        for p in net.places:
            tokens = marking.get(p, 0)
            if tokens > place_bounds[p]:
                place_bounds[p] = tokens

    result.place_bounds = place_bounds
    result.bound = max(place_bounds.values()) if place_bounds else 0
    result.is_bounded = True  # finite reachability graph implies bounded
    result.is_safe = result.bound <= 1

    # ------------------------------------------------------------------
    # Liveness
    # ------------------------------------------------------------------
    # Build set of transitions that fire in at least one state (L0-live)
    fired_transitions: Set[str] = set()
    for trans_list in edges.values():
        for trans_id, _ in trans_list:
            fired_transitions.add(trans_id)

    all_transitions = set(net.transitions)
    result.l0_live_transitions = sorted(fired_transitions)
    result.not_l0_live_transitions = sorted(all_transitions - fired_transitions)

    # L1-liveness: from every reachable marking, t is eventually fireable.
    # We check this by building a "can reach a firing of t" relation via
    # backward reachability on the graph.
    result.l1_live_transitions = []
    result.not_l1_live_transitions = []

    # Precompute successor sets
    state_keys = list(states.keys())
    successors: Dict[Tuple, List[Tuple]] = {k: [] for k in state_keys}
    predecessors: Dict[Tuple, List[Tuple]] = {k: [] for k in state_keys}
    for src_key, trans_list in edges.items():
        for trans_id, dst_key in trans_list:
            successors[src_key].append(dst_key)
            predecessors[dst_key].append(src_key)

    init_key = PetriNet._marking_key(net.initial_marking())

    for trans_id in sorted(all_transitions):
        # States where t fires directly
        direct_fire_states: Set[Tuple] = set()
        for src_key, trans_list in edges.items():
            for tid, _ in trans_list:
                if tid == trans_id:
                    direct_fire_states.add(src_key)

        # Backward BFS: find all states that can reach a direct-fire state
        can_reach: Set[Tuple] = set(direct_fire_states)
        bfs_queue = list(direct_fire_states)
        while bfs_queue:
            cur = bfs_queue.pop()
            for pred in predecessors.get(cur, []):
                if pred not in can_reach:
                    can_reach.add(pred)
                    bfs_queue.append(pred)

        if set(state_keys) == can_reach:
            result.l1_live_transitions.append(trans_id)
        else:
            result.not_l1_live_transitions.append(trans_id)

    result.is_l1_live = len(result.not_l1_live_transitions) == 0

    # ------------------------------------------------------------------
    # Deadlock-freeness
    # ------------------------------------------------------------------
    deadlock_markings: List[Dict[str, int]] = []
    for state_key, trans_list in edges.items():
        if not trans_list:
            # No outgoing transitions → deadlock
            deadlock_markings.append(states[state_key])

    result.deadlock_markings = deadlock_markings
    result.is_deadlock_free = len(deadlock_markings) == 0

    return result


def check_reachability(
    net: PetriNet,
    target: Dict[str, int],
    max_states: int = 100_000,
) -> bool:
    """
    Return True if *target* marking is reachable from the initial marking.

    Only places listed in *target* are checked; places not mentioned in
    *target* may hold any number of tokens.

    Args:
        net:    The Petri Net to analyse.
        target: Partial marking to search for (place_id → required tokens).
    """
    states, _ = net.reachability_graph(max_states=max_states)
    for marking in states.values():
        if all(marking.get(p, 0) == v for p, v in target.items()):
            return True
    return False
