"""
PNML (Petri Net Markup Language) export for PIPE 4.3.0 and WoPeD 3.8.0.

The generated XML follows the ISO/IEC 15909-2 standard PNML format for
Place/Transition nets, which is accepted by both PIPE 4.3.0 and WoPeD 3.8.0.

Usage::

    from src.irrigation_model import build_irrigation_net
    from src.pnml_export import export_pnml

    net = build_irrigation_net()
    pnml_str = export_pnml(net)
    with open("models/irrigation_system.pnml", "w") as f:
        f.write(pnml_str)
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from typing import Dict, Optional, Tuple

from src.petri_net import PetriNet


# ------------------------------------------------------------------
# Layout: (x, y) coordinates for each place/transition in the model.
# These positions produce a readable left-to-right, top-to-bottom layout
# when the PNML is opened in PIPE 4.3.0 or WoPeD 3.8.0.
# ------------------------------------------------------------------

_PLACE_POSITIONS: Dict[str, Tuple[float, float]] = {
    "idle":            (80,  350),
    "sensing":         (220, 350),
    "moist_low":       (400, 200),
    "moist_ok":        (400, 500),
    "nutr_low":        (580, 200),
    "nutr_ok":         (580, 500),
    "irrigating":      (760, 150),
    "fertilising":     (760, 550),
    "irr_complete":    (940, 150),
    "fert_complete":   (940, 550),
    "actuations_done": (1120, 350),
    "logging":         (1300, 350),
    "notifying":       (1480, 350),
    "cycle_done":      (1660, 350),
}

_TRANSITION_POSITIONS: Dict[str, Tuple[float, float]] = {
    "t_start_sensing":         (150, 350),
    "t_sense_dry_poor":        (310, 110),
    "t_sense_dry_rich":        (310, 270),
    "t_sense_moist_poor":      (310, 430),
    "t_sense_moist_rich":      (310, 590),
    "t_start_irrigation":      (580, 150),
    "t_irrigation_complete":   (850, 150),
    "t_skip_irrigation":       (580, 500),   # moist_ok → irr_complete
    "t_start_fertilisation":   (670, 550),
    "t_fertilisation_complete":(850, 550),
    "t_skip_fertilisation":    (670, 200),   # nutr_ok → fert_complete
    "t_sync_actuations":       (1030, 350),
    "t_start_logging":         (1210, 350),
    "t_log_complete":          (1390, 350),
    "t_notify":                (1570, 350),
    "t_reset":                 (1740, 350),
}


def export_pnml(
    net: PetriNet,
    place_positions: Optional[Dict[str, Tuple[float, float]]] = None,
    transition_positions: Optional[Dict[str, Tuple[float, float]]] = None,
) -> str:
    """
    Serialise *net* to a PNML string (ISO/IEC 15909-2 PT-net grammar).

    Args:
        net:                  The Petri Net to export.
        place_positions:      Optional dict overriding default (x, y)
                              positions for places.
        transition_positions: Optional dict overriding default (x, y)
                              positions for transitions.

    Returns:
        A UTF-8 PNML XML string.
    """
    p_pos = dict(_PLACE_POSITIONS)
    if place_positions:
        p_pos.update(place_positions)
    t_pos = dict(_TRANSITION_POSITIONS)
    if transition_positions:
        t_pos.update(transition_positions)

    # Root element
    root = ET.Element(
        "pnml",
        xmlns="http://www.pnml.org/version-2009/grammar/pnml",
    )
    net_elem = ET.SubElement(
        root,
        "net",
        id="Net-IrrigationSystem",
        type="http://www.pnml.org/version-2009/grammar/ptnet",
    )
    name_elem = ET.SubElement(net_elem, "name")
    ET.SubElement(name_elem, "text").text = net.name

    page = ET.SubElement(net_elem, "page", id="page0")

    # ------------------------------------------------------------------
    # Places
    # ------------------------------------------------------------------
    for place_id in sorted(net._places):
        initial = net._places[place_id]
        label = net._place_labels[place_id]
        x, y = p_pos.get(place_id, (0.0, 0.0))

        p_elem = ET.SubElement(page, "place", id=place_id)

        p_name = ET.SubElement(p_elem, "name")
        ET.SubElement(p_name, "text").text = label
        p_name_g = ET.SubElement(p_name, "graphics")
        ET.SubElement(p_name_g, "offset", x="0.0", y="-20.0")

        if initial > 0:
            im = ET.SubElement(p_elem, "initialMarking")
            ET.SubElement(im, "text").text = str(initial)

        p_graphics = ET.SubElement(p_elem, "graphics")
        ET.SubElement(p_graphics, "position", x=str(x), y=str(y))

    # ------------------------------------------------------------------
    # Transitions
    # ------------------------------------------------------------------
    for trans_id in sorted(net._transitions):
        label = net._transitions[trans_id]["label"]
        x, y = t_pos.get(trans_id, (0.0, 0.0))

        t_elem = ET.SubElement(page, "transition", id=trans_id)

        t_name = ET.SubElement(t_elem, "name")
        ET.SubElement(t_name, "text").text = label
        t_name_g = ET.SubElement(t_name, "graphics")
        ET.SubElement(t_name_g, "offset", x="0.0", y="-20.0")

        t_graphics = ET.SubElement(t_elem, "graphics")
        ET.SubElement(t_graphics, "position", x=str(x), y=str(y))

    # ------------------------------------------------------------------
    # Arcs
    # ------------------------------------------------------------------
    arc_counter = 0
    for trans_id, tdata in sorted(net._transitions.items()):
        # Input arcs  (place → transition)
        for place_id, weight in sorted(tdata["inputs"].items()):
            arc_counter += 1
            arc_id = f"arc{arc_counter}"
            arc = ET.SubElement(
                page, "arc",
                id=arc_id, source=place_id, target=trans_id,
            )
            insc = ET.SubElement(arc, "inscription")
            ET.SubElement(insc, "text").text = str(weight)
            ET.SubElement(arc, "graphics")

        # Output arcs (transition → place)
        for place_id, weight in sorted(tdata["outputs"].items()):
            arc_counter += 1
            arc_id = f"arc{arc_counter}"
            arc = ET.SubElement(
                page, "arc",
                id=arc_id, source=trans_id, target=place_id,
            )
            insc = ET.SubElement(arc, "inscription")
            ET.SubElement(insc, "text").text = str(weight)
            ET.SubElement(arc, "graphics")

    # ------------------------------------------------------------------
    # Serialise
    # ------------------------------------------------------------------
    _indent(root)
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")

    import io
    buf = io.BytesIO()
    tree.write(buf, encoding="utf-8", xml_declaration=True)
    return buf.getvalue().decode("utf-8")


def _indent(elem: ET.Element, level: int = 0) -> None:
    """Add pretty-print indentation (fallback for Python < 3.9)."""
    indent = "\n" + "  " * level
    if len(elem):
        if not elem.text or not elem.text.strip():
            elem.text = indent + "  "
        if not elem.tail or not elem.tail.strip():
            elem.tail = indent
        for child in elem:
            _indent(child, level + 1)
        if not child.tail or not child.tail.strip():  # noqa: F821
            child.tail = indent
    else:
        if level and (not elem.tail or not elem.tail.strip()):
            elem.tail = indent
