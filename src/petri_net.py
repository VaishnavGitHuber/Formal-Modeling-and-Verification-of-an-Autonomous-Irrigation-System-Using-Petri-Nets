"""
Core Place/Transition Petri Net implementation.

A Petri Net is a mathematical modeling language consisting of:
  - Places   – represent conditions or states (drawn as circles)
  - Transitions – represent events or actions (drawn as rectangles/bars)
  - Arcs     – directed edges connecting places to transitions (input arcs)
               and transitions to places (output arcs), each with a weight
  - Tokens   – indicate the current state; their distribution across places
               is called a *marking*

Firing rule
-----------
A transition t is *enabled* in marking M if every input place p has at least
arc_weight(p, t) tokens.  Firing t produces a new marking M' by:
  - Subtracting arc_weight(p, t) tokens from each input place p
  - Adding arc_weight(t, p) tokens to each output place p
"""

from __future__ import annotations

from collections import deque
from typing import Dict, Iterable, List, Optional, Tuple


class PetriNet:
    """A Place/Transition Petri Net with support for formal verification."""

    def __init__(self, name: str = "PetriNet") -> None:
        """
        Initialise an empty Petri Net.

        Args:
            name: Human-readable label for the net.
        """
        self.name: str = name
        # place_id -> initial token count
        self._places: Dict[str, int] = {}
        # place_id -> display label
        self._place_labels: Dict[str, str] = {}
        # trans_id -> {"inputs": {place_id: weight}, "outputs": {place_id: weight}, "label": str}
        self._transitions: Dict[str, Dict] = {}

    # ------------------------------------------------------------------
    # Building the net
    # ------------------------------------------------------------------

    def add_place(
        self,
        place_id: str,
        initial_tokens: int = 0,
        label: Optional[str] = None,
    ) -> "PetriNet":
        """
        Add a place to the net.

        Args:
            place_id:       Unique identifier.
            initial_tokens: Number of tokens in the initial marking (≥ 0).
            label:          Human-readable name; defaults to *place_id*.

        Returns:
            self  (enables method chaining)
        """
        if initial_tokens < 0:
            raise ValueError(
                f"Initial token count must be ≥ 0, got {initial_tokens!r}"
            )
        self._places[place_id] = initial_tokens
        self._place_labels[place_id] = label if label is not None else place_id
        return self

    def add_transition(
        self,
        trans_id: str,
        inputs: Dict[str, int],
        outputs: Dict[str, int],
        label: Optional[str] = None,
    ) -> "PetriNet":
        """
        Add a transition to the net.

        Args:
            trans_id: Unique identifier.
            inputs:   Mapping from input place IDs to arc weights (≥ 1).
            outputs:  Mapping from output place IDs to arc weights (≥ 1).
            label:    Human-readable name; defaults to *trans_id*.

        Returns:
            self  (enables method chaining)

        Raises:
            ValueError: If any referenced place has not yet been added.
        """
        for pid in list(inputs) + list(outputs):
            if pid not in self._places:
                raise ValueError(
                    f"Place '{pid}' referenced in transition '{trans_id}' "
                    "does not exist. Add all places before adding transitions."
                )
        self._transitions[trans_id] = {
            "inputs": dict(inputs),
            "outputs": dict(outputs),
            "label": label if label is not None else trans_id,
        }
        return self

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def places(self) -> List[str]:
        """Return sorted list of place IDs."""
        return sorted(self._places)

    @property
    def transitions(self) -> List[str]:
        """Return sorted list of transition IDs."""
        return sorted(self._transitions)

    def place_label(self, place_id: str) -> str:
        """Return the display label for a place."""
        return self._place_labels[place_id]

    def transition_label(self, trans_id: str) -> str:
        """Return the display label for a transition."""
        return self._transitions[trans_id]["label"]

    def transition_inputs(self, trans_id: str) -> Dict[str, int]:
        """Return {place_id: arc_weight} for the input arcs of *trans_id*."""
        return dict(self._transitions[trans_id]["inputs"])

    def transition_outputs(self, trans_id: str) -> Dict[str, int]:
        """Return {place_id: arc_weight} for the output arcs of *trans_id*."""
        return dict(self._transitions[trans_id]["outputs"])

    # ------------------------------------------------------------------
    # Marking operations
    # ------------------------------------------------------------------

    def initial_marking(self) -> Dict[str, int]:
        """Return a copy of the initial marking."""
        return dict(self._places)

    def is_enabled(self, trans_id: str, marking: Dict[str, int]) -> bool:
        """
        Return True if *trans_id* is enabled in *marking*.

        A transition is enabled when every input place holds at least as many
        tokens as the corresponding arc weight.
        """
        if trans_id not in self._transitions:
            raise ValueError(f"Unknown transition '{trans_id}'")
        for place_id, weight in self._transitions[trans_id]["inputs"].items():
            if marking.get(place_id, 0) < weight:
                return False
        return True

    def fire(
        self, trans_id: str, marking: Dict[str, int]
    ) -> Dict[str, int]:
        """
        Fire *trans_id* in *marking* and return the resulting marking.

        The original *marking* dict is **not** modified.

        Raises:
            ValueError: If the transition is not enabled.
        """
        if not self.is_enabled(trans_id, marking):
            raise ValueError(
                f"Transition '{trans_id}' is not enabled in marking {marking}"
            )
        new_marking: Dict[str, int] = dict(marking)
        for place_id, weight in self._transitions[trans_id]["inputs"].items():
            new_marking[place_id] -= weight
        for place_id, weight in self._transitions[trans_id]["outputs"].items():
            new_marking[place_id] = new_marking.get(place_id, 0) + weight
        return new_marking

    def enabled_transitions(self, marking: Dict[str, int]) -> List[str]:
        """Return all transition IDs that are enabled in *marking*."""
        return [t for t in self._transitions if self.is_enabled(t, marking)]

    # ------------------------------------------------------------------
    # Reachability graph
    # ------------------------------------------------------------------

    def reachability_graph(
        self, max_states: int = 100_000
    ) -> Tuple[Dict[Tuple, Dict[str, int]], Dict[Tuple, List[Tuple[str, Tuple]]]]:
        """
        Build the reachability graph by BFS from the initial marking.

        Returns:
            states:  dict mapping marking_key → marking dict
            edges:   dict mapping marking_key → list of (transition_id, successor_key)

        A *marking_key* is the canonical (sorted) tuple of (place_id, tokens)
        pairs for places with > 0 tokens.

        Args:
            max_states: Safety limit to guard against unbounded nets.
        """
        initial = self.initial_marking()
        init_key = self._marking_key(initial)

        states: Dict[Tuple, Dict[str, int]] = {init_key: initial}
        edges: Dict[Tuple, List[Tuple[str, Tuple]]] = {init_key: []}
        queue: deque = deque([init_key])

        while queue:
            if len(states) >= max_states:
                raise RuntimeError(
                    f"Reachability graph exceeded {max_states} states – "
                    "the net may be unbounded."
                )
            cur_key = queue.popleft()
            cur_marking = states[cur_key]
            for trans_id in self.enabled_transitions(cur_marking):
                next_marking = self.fire(trans_id, cur_marking)
                next_key = self._marking_key(next_marking)
                if next_key not in states:
                    states[next_key] = next_marking
                    edges[next_key] = []
                    queue.append(next_key)
                edges[cur_key].append((trans_id, next_key))

        return states, edges

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _marking_key(marking: Dict[str, int]) -> Tuple:
        """Return a hashable representation of *marking*."""
        return tuple(sorted((p, c) for p, c in marking.items() if c > 0))

    def __repr__(self) -> str:
        return (
            f"PetriNet(name={self.name!r}, "
            f"places={len(self._places)}, "
            f"transitions={len(self._transitions)})"
        )
