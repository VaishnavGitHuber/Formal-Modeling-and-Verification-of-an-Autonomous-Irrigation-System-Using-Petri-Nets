"""
Entry point for the Autonomous Irrigation System Petri Net tool.

Usage::

    python main.py

This script:
  1. Builds the Petri Net model of the autonomous irrigation system.
  2. Runs the formal verification suite (reachability, boundedness,
     safeness, liveness, deadlock-freeness).
  3. Runs a simulation for each of the four sensor-reading scenarios.
  4. Exports the model as a PNML file for PIPE 4.3.0 / WoPeD 3.8.0.
"""

from __future__ import annotations

import os
import sys

from src.irrigation_model import build_irrigation_net
from src.pnml_export import export_pnml
from src.simulation import SCENARIOS, simulate_scenario
from src.verification import verify


def main() -> None:
    print("=" * 60)
    print("  Autonomous Irrigation System – Petri Net Analysis")
    print("=" * 60)

    # ------------------------------------------------------------------
    # 1. Build model
    # ------------------------------------------------------------------
    print("\n[1/4] Building Petri Net model …")
    net = build_irrigation_net()
    print(f"      {net}")
    print(f"      Places      : {', '.join(net.places)}")
    print(f"      Transitions : {', '.join(net.transitions)}")

    # ------------------------------------------------------------------
    # 2. Formal verification
    # ------------------------------------------------------------------
    print("\n[2/4] Running formal verification …")
    result = verify(net)
    print(result.summary())

    # ------------------------------------------------------------------
    # 3. Simulation
    # ------------------------------------------------------------------
    print("\n[3/4] Simulating all four sensing scenarios …")
    for scenario in sorted(SCENARIOS):
        trace = simulate_scenario(net, scenario, verbose=True)
        print(f"      → {len(trace)} transitions fired for scenario '{scenario}'")

    # ------------------------------------------------------------------
    # 4. PNML export
    # ------------------------------------------------------------------
    print("\n[4/4] Exporting PNML model …")
    pnml_str = export_pnml(net)
    models_dir = os.path.join(os.path.dirname(__file__), "models")
    os.makedirs(models_dir, exist_ok=True)
    pnml_path = os.path.join(models_dir, "irrigation_system.pnml")
    with open(pnml_path, "w", encoding="utf-8") as fh:
        fh.write(pnml_str)
    print(f"      Saved: {pnml_path}")
    print("\nDone.")


if __name__ == "__main__":
    main()
