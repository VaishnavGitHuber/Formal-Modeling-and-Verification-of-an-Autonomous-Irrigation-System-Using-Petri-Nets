"""
Petri Net model of an Autonomous Irrigation System.

System overview
---------------
The system autonomously monitors soil moisture and nutrient levels and
performs irrigation and/or fertilization without human intervention.

Workflow phases (matching the paper's description):
  1. Sensing   – soil moisture and nutrient levels are read by sensors
  2. Decision  – sensor data is analysed; four outcomes are possible:
                   (a) moisture LOW  + nutrient LOW  → irrigate + fertilise
                   (b) moisture LOW  + nutrient OK   → irrigate only
                   (c) moisture OK   + nutrient LOW  → fertilise only
                   (d) moisture OK   + nutrient OK   → no actuation needed
  3. Actuation – irrigation valve and/or fertiliser pump are activated
  4. Logging   – actuation results are written to the data store
  5. Notification – an alert/summary is sent to the operator

Petri Net structure
-------------------
Places (states):
  idle           – system is idle, waiting for the next sensing cycle
  sensing        – sensor readings are being taken
  moist_low      – moisture sensor reports soil is DRY
  moist_ok       – moisture sensor reports soil is ADEQUATE
  nutr_low       – nutrient sensor reports nutrient level is LOW
  nutr_ok        – nutrient sensor reports nutrient level is ADEQUATE
  irrigating     – irrigation valve is open, water is being delivered
  fertilising    – fertiliser pump is active
  irr_complete   – irrigation actuation has finished (or was not required)
  fert_complete  – fertilisation actuation has finished (or was not required)
  actuations_done – both actuation paths have completed/been skipped
  logging        – system is writing data to the log
  notifying      – notification is being sent to the operator
  cycle_done     – full sensing-actuation-logging-notification cycle is done

Transitions (events):
  t_start_sensing          – system wakes from idle and starts sensing
  t_sense_dry_poor         – sensing complete: moisture LOW, nutrient LOW
  t_sense_dry_rich         – sensing complete: moisture LOW, nutrient OK
  t_sense_moist_poor       – sensing complete: moisture OK, nutrient LOW
  t_sense_moist_rich       – sensing complete: moisture OK, nutrient OK
  t_start_irrigation       – open irrigation valve (moisture low path)
  t_irrigation_complete    – irrigation delivered successfully
  t_skip_irrigation        – moisture is adequate; skip irrigation
  t_start_fertilisation    – activate fertiliser pump (nutrient low path)
  t_fertilisation_complete – fertiliser delivered successfully
  t_skip_fertilisation     – nutrient level adequate; skip fertilisation
  t_sync_actuations        – both actuation branches have joined; proceed
  t_start_logging          – begin writing the cycle log entry
  t_log_complete           – log entry written successfully
  t_notify                 – send operator notification
  t_reset                  – cycle finished; return to idle for next cycle

Key properties (verified in src/verification.py):
  * Reachability  – all expected system states are reachable
  * 1-Safeness    – each place holds ≤ 1 token in every reachable marking
  * Boundedness   – the net is 1-safe (bound = 1)
  * Liveness      – no transition permanently loses the ability to fire
  * Deadlock-free – no reachable marking has zero enabled transitions
"""

from __future__ import annotations

from src.petri_net import PetriNet


def build_irrigation_net() -> PetriNet:
    """
    Construct and return the Petri Net model of the autonomous irrigation
    system.

    Returns:
        A fully configured :class:`~src.petri_net.PetriNet` instance.
    """
    net = PetriNet(name="Autonomous Irrigation System")

    # ------------------------------------------------------------------
    # Places
    # ------------------------------------------------------------------
    net.add_place("idle",            initial_tokens=1, label="Idle")
    net.add_place("sensing",         initial_tokens=0, label="Sensing")
    net.add_place("moist_low",       initial_tokens=0, label="Moisture Low")
    net.add_place("moist_ok",        initial_tokens=0, label="Moisture OK")
    net.add_place("nutr_low",        initial_tokens=0, label="Nutrient Low")
    net.add_place("nutr_ok",         initial_tokens=0, label="Nutrient OK")
    net.add_place("irrigating",      initial_tokens=0, label="Irrigating")
    net.add_place("fertilising",     initial_tokens=0, label="Fertilising")
    net.add_place("irr_complete",    initial_tokens=0, label="Irrigation Complete")
    net.add_place("fert_complete",   initial_tokens=0, label="Fertilisation Complete")
    net.add_place("actuations_done", initial_tokens=0, label="Actuations Done")
    net.add_place("logging",         initial_tokens=0, label="Logging")
    net.add_place("notifying",       initial_tokens=0, label="Notifying")
    net.add_place("cycle_done",      initial_tokens=0, label="Cycle Done")

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------

    # Phase 1 – Sensing
    net.add_transition(
        "t_start_sensing",
        inputs={"idle": 1},
        outputs={"sensing": 1},
        label="Start Sensing",
    )

    # Phase 2 – Decision (four non-deterministic outcomes modelling all
    # possible sensor reading combinations)
    net.add_transition(
        "t_sense_dry_poor",
        inputs={"sensing": 1},
        outputs={"moist_low": 1, "nutr_low": 1},
        label="Sense: Dry + Low Nutrient",
    )
    net.add_transition(
        "t_sense_dry_rich",
        inputs={"sensing": 1},
        outputs={"moist_low": 1, "nutr_ok": 1},
        label="Sense: Dry + Adequate Nutrient",
    )
    net.add_transition(
        "t_sense_moist_poor",
        inputs={"sensing": 1},
        outputs={"moist_ok": 1, "nutr_low": 1},
        label="Sense: Moist + Low Nutrient",
    )
    net.add_transition(
        "t_sense_moist_rich",
        inputs={"sensing": 1},
        outputs={"moist_ok": 1, "nutr_ok": 1},
        label="Sense: Moist + Adequate Nutrient",
    )

    # Phase 3a – Irrigation branch
    net.add_transition(
        "t_start_irrigation",
        inputs={"moist_low": 1},
        outputs={"irrigating": 1},
        label="Start Irrigation",
    )
    net.add_transition(
        "t_irrigation_complete",
        inputs={"irrigating": 1},
        outputs={"irr_complete": 1},
        label="Irrigation Complete",
    )
    net.add_transition(
        "t_skip_irrigation",
        inputs={"moist_ok": 1},
        outputs={"irr_complete": 1},
        label="Skip Irrigation (Moisture OK)",
    )

    # Phase 3b – Fertilisation branch
    net.add_transition(
        "t_start_fertilisation",
        inputs={"nutr_low": 1},
        outputs={"fertilising": 1},
        label="Start Fertilisation",
    )
    net.add_transition(
        "t_fertilisation_complete",
        inputs={"fertilising": 1},
        outputs={"fert_complete": 1},
        label="Fertilisation Complete",
    )
    net.add_transition(
        "t_skip_fertilisation",
        inputs={"nutr_ok": 1},
        outputs={"fert_complete": 1},
        label="Skip Fertilisation (Nutrient OK)",
    )

    # Phase 3c – Synchronisation join (AND-join for the two actuation branches)
    net.add_transition(
        "t_sync_actuations",
        inputs={"irr_complete": 1, "fert_complete": 1},
        outputs={"actuations_done": 1},
        label="Sync: Actuations Done",
    )

    # Phase 4 – Logging
    net.add_transition(
        "t_start_logging",
        inputs={"actuations_done": 1},
        outputs={"logging": 1},
        label="Start Logging",
    )
    net.add_transition(
        "t_log_complete",
        inputs={"logging": 1},
        outputs={"notifying": 1},
        label="Log Complete",
    )

    # Phase 5 – Notification
    net.add_transition(
        "t_notify",
        inputs={"notifying": 1},
        outputs={"cycle_done": 1},
        label="Send Notification",
    )

    # Reset – start the next monitoring cycle
    net.add_transition(
        "t_reset",
        inputs={"cycle_done": 1},
        outputs={"idle": 1},
        label="Reset (Next Cycle)",
    )

    return net


# Convenience: ordered list of places in logical workflow order for display
PLACE_ORDER = [
    "idle",
    "sensing",
    "moist_low",
    "moist_ok",
    "nutr_low",
    "nutr_ok",
    "irrigating",
    "fertilising",
    "irr_complete",
    "fert_complete",
    "actuations_done",
    "logging",
    "notifying",
    "cycle_done",
]
