# Formal Modeling and Verification of an Autonomous Irrigation System Using Petri Nets

## Abstract

Automated irrigation systems are critical for efficient water and nutrient
management in modern agriculture. However, most existing approaches rely on
heuristic methods without formal verification, leaving the system prone to
deadlocks or inconsistent operation. This project addresses this research gap by
presenting a formal modeling and verification of an autonomous irrigation system
using Petri Nets. The system autonomously monitors soil moisture and nutrient
levels to perform irrigation and fertilization without human intervention. The
workflow—including sensing, decision-making, actuation, logging, and
notification—is modeled and simulated using both Python and PNML files loadable
in PIPE 4.3.0 and WoPeD 3.8.0. Verification of reachability, boundedness,
liveness, safeness, and deadlock-freeness confirms reliable system operation,
highlighting the relevance of Petri Net-based modeling for robust, scalable
autonomous irrigation systems.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Petri Net Model](#petri-net-model)
3. [Verification Results](#verification-results)
4. [Project Structure](#project-structure)
5. [Getting Started](#getting-started)
6. [Running Simulations](#running-simulations)
7. [Running Verification](#running-verification)
8. [PNML Export (PIPE / WoPeD)](#pnml-export-pipe--woped)
9. [Running Tests](#running-tests)

---

## System Overview

The autonomous irrigation system performs the following cyclic workflow
without human intervention:

```
Idle ──► Sensing ──► Decision ──► Actuation ──► Logging ──► Notification ──► Idle
```

| Phase          | Description                                                          |
|----------------|----------------------------------------------------------------------|
| **Sensing**    | Soil moisture and nutrient levels are read simultaneously            |
| **Decision**   | Sensor data is analysed; four outcomes determine what to do next     |
| **Actuation**  | Irrigation valve and/or fertiliser pump are activated as required    |
| **Logging**    | The cycle outcome is written to the data store                       |
| **Notification** | An alert/summary is sent to the operator                           |

---

## Petri Net Model

### Places (14)

| Place ID          | Label                    | Role                                              |
|-------------------|--------------------------|---------------------------------------------------|
| `idle`            | Idle                     | System waiting for next cycle (initial: 1 token)  |
| `sensing`         | Sensing                  | Sensor readings in progress                       |
| `moist_low`       | Moisture Low             | Soil moisture below irrigation threshold          |
| `moist_ok`        | Moisture OK              | Soil moisture is adequate                         |
| `nutr_low`        | Nutrient Low             | Nutrient level below fertilisation threshold      |
| `nutr_ok`         | Nutrient OK              | Nutrient level is adequate                        |
| `irrigating`      | Irrigating               | Irrigation valve open, water flowing              |
| `fertilising`     | Fertilising              | Fertiliser pump active                            |
| `irr_complete`    | Irrigation Complete      | Irrigation branch finished (or skipped)           |
| `fert_complete`   | Fertilisation Complete   | Fertilisation branch finished (or skipped)        |
| `actuations_done` | Actuations Done          | Both actuation branches synchronised              |
| `logging`         | Logging                  | Writing cycle data to log                         |
| `notifying`       | Notifying                | Sending operator notification                     |
| `cycle_done`      | Cycle Done               | Full cycle completed; ready to reset              |

### Transitions (16)

| Transition ID              | Event                              |
|----------------------------|------------------------------------|
| `t_start_sensing`          | Wake from idle, begin sensing      |
| `t_sense_dry_poor`         | Moisture LOW + Nutrient LOW        |
| `t_sense_dry_rich`         | Moisture LOW + Nutrient OK         |
| `t_sense_moist_poor`       | Moisture OK  + Nutrient LOW        |
| `t_sense_moist_rich`       | Moisture OK  + Nutrient OK         |
| `t_start_irrigation`       | Open irrigation valve              |
| `t_irrigation_complete`    | Irrigation delivered               |
| `t_skip_irrigation`        | Moisture adequate – skip           |
| `t_start_fertilisation`    | Activate fertiliser pump           |
| `t_fertilisation_complete` | Fertiliser delivered               |
| `t_skip_fertilisation`     | Nutrient adequate – skip           |
| `t_sync_actuations`        | AND-join: both branches done       |
| `t_start_logging`          | Begin writing log entry            |
| `t_log_complete`           | Log written                        |
| `t_notify`                 | Send notification                  |
| `t_reset`                  | Reset; return to idle              |

### Decision Logic

The four sensing transitions model non-deterministic sensor readings and
route tokens into the two parallel actuation branches:

```
t_sense_dry_poor   → moist_low  + nutr_low   (irrigate AND fertilise)
t_sense_dry_rich   → moist_low  + nutr_ok    (irrigate only)
t_sense_moist_poor → moist_ok   + nutr_low   (fertilise only)
t_sense_moist_rich → moist_ok   + nutr_ok    (no actuation needed)
```

The `t_skip_irrigation` and `t_skip_fertilisation` transitions produce a
virtual completion token so the AND-join (`t_sync_actuations`) always fires
regardless of which decision path was taken.

---

## Verification Results

All formal properties were verified by exhaustive BFS exploration of the
reachability graph (22 reachable states).

| Property            | Result | Details                                             |
|---------------------|--------|-----------------------------------------------------|
| **Reachability**    | ✅ Pass | All 14 places are reachable; all 4 sensor outcomes are exercisable |
| **Boundedness**     | ✅ Pass | Net is bounded (finite reachability graph)          |
| **Safeness (1-bounded)** | ✅ Pass | Every place holds ≤ 1 token in every reachable marking |
| **Liveness (L0)**   | ✅ Pass | All 16 transitions fire in at least one execution   |
| **Liveness (L1)**   | ✅ Pass | All 16 transitions are fully live (fire from every reachable state) |
| **Deadlock-freeness** | ✅ Pass | No reachable marking has zero enabled transitions   |

---

## Project Structure

```
.
├── src/
│   ├── petri_net.py        # Core Petri Net data structure
│   ├── verification.py     # Reachability graph + property verification
│   ├── irrigation_model.py # Irrigation system Petri Net model
│   ├── simulation.py       # Scenario and random simulation runner
│   └── pnml_export.py      # PNML export (PIPE 4.3.0 / WoPeD 3.8.0)
├── tests/
│   ├── test_petri_net.py           # Unit tests – core Petri Net
│   ├── test_verification.py        # Unit tests – verification algorithms
│   └── test_irrigation_model.py    # Integration tests – irrigation model
├── models/
│   └── irrigation_system.pnml  # PNML file (auto-generated by main.py)
├── main.py           # Entry point: build → verify → simulate → export
├── requirements.txt
└── README.md
```

---

## Getting Started

**Requirements:** Python 3.9+

```bash
# Install dependencies (pytest only)
pip install -r requirements.txt

# Run the full analysis (verification + simulation + PNML export)
python main.py
```

---

## Running Simulations

```python
from src.irrigation_model import build_irrigation_net
from src.simulation import simulate_scenario, simulate_random

net = build_irrigation_net()

# Deterministic scenario: moisture low, nutrient low (both actuators fire)
trace = simulate_scenario(net, scenario="dry_poor", verbose=True)

# Random multi-cycle simulation (5 cycles, reproducible seed)
trace = simulate_random(net, num_cycles=5, seed=42, verbose=True)
```

Available scenarios: `"dry_poor"`, `"dry_rich"`, `"moist_poor"`, `"moist_rich"`.

---

## Running Verification

```python
from src.irrigation_model import build_irrigation_net
from src.verification import verify, check_reachability

net = build_irrigation_net()

# Full verification suite
result = verify(net)
print(result.summary())

# Check whether a specific state is reachable
print(check_reachability(net, {"irrigating": 1}))   # True
print(check_reachability(net, {"idle": 1, "sensing": 1}))  # False
```

---

## PNML Export (PIPE / WoPeD)

```bash
# Regenerate the PNML file
python main.py
# → models/irrigation_system.pnml
```

Open `models/irrigation_system.pnml` in **PIPE 4.3.0** or **WoPeD 3.8.0** to
view the graphical Petri Net diagram and run the built-in analysis tools.

---

## Running Tests

```bash
pytest tests/ -v
```

The test suite comprises **91 tests** covering:
- Core Petri Net operations (place/transition creation, enabling, firing)
- Verification algorithms (boundedness, safeness, liveness, deadlock detection)
- Irrigation model properties (all formal properties verified)
- Simulation scenarios (all four sensor-reading paths exercised)
