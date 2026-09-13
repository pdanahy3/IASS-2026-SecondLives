"""Generate a 2D Warren truss centreline model and write it as JSON.

Parallel chords, alternating diagonals, no verticals. The bottom chord is
divided into equal panels; top chord nodes sit above the panel midpoints, so
the top chord is one panel shorter than the bottom and the end diagonals run
from the supports up to the first and last top nodes.

Geometry lies in the XZ plane (y = 0) so it reads as an elevation in Rhino.
Units are millimetres, matching the donor inventory models.

    python tools/build_truss.py
"""

import json
import math
import os

FT = 304.8

SPAN = 20000.0
DEPTH = 2000.0
PANELS = 8

OUT_DIR = os.path.join(
    r"c:\Users\pdanahy3\Downloads\IASS-2026-Workshop_SecondLives", "rhino")
OUT_NAME = "SecondLives_truss_warren_20m"


def build(span=SPAN, depth=DEPTH, panels=PANELS):
    panel = span / panels

    nodes = []
    for i in range(panels + 1):
        nodes.append({
            "id": "B{0}".format(i),
            "chord": "bottom",
            "x": round(i * panel, 4),
            "y": 0.0,
            "z": 0.0,
        })
    for i in range(panels):
        nodes.append({
            "id": "T{0}".format(i),
            "chord": "top",
            "x": round(panel / 2.0 + i * panel, 4),
            "y": 0.0,
            "z": round(depth, 4),
        })

    by_id = dict((n["id"], n) for n in nodes)

    # Pin one support and roller the other so the model is statically determinate.
    by_id["B0"]["support"] = "pin"
    by_id["B{0}".format(panels)]["support"] = "roller"

    def length(a, b):
        na, nb = by_id[a], by_id[b]
        return math.sqrt((nb["x"] - na["x"]) ** 2 + (nb["z"] - na["z"]) ** 2)

    members = []

    def add(role, a, b):
        members.append({
            "id": "{0}{1}".format({"bottom_chord": "BC",
                                   "top_chord": "TC",
                                   "diagonal": "D"}[role], len(
                [m for m in members if m["role"] == role]) + 1),
            "role": role,
            "start": a,
            "end": b,
            "length_mm": round(length(a, b), 4),
            "length_ft": round(length(a, b) / FT, 4),
        })

    for i in range(panels):
        add("bottom_chord", "B{0}".format(i), "B{0}".format(i + 1))
    for i in range(panels - 1):
        add("top_chord", "T{0}".format(i), "T{0}".format(i + 1))
    for i in range(panels):
        add("diagonal", "B{0}".format(i), "T{0}".format(i))
        add("diagonal", "T{0}".format(i), "B{0}".format(i + 1))

    roles = {}
    for m in members:
        entry = roles.setdefault(m["role"], {"count": 0, "total_mm": 0.0, "unit_mm": m["length_mm"]})
        entry["count"] += 1
        entry["total_mm"] = round(entry["total_mm"] + m["length_mm"], 4)

    return {
        "model": "warren_truss_2d",
        "description": "2D Warren truss centrelines, parallel chords, no verticals",
        "units": "mm",
        "plane": "XZ",
        "parameters": {
            "span_mm": span,
            "depth_mm": depth,
            "panels": panels,
            "panel_length_mm": round(panel, 4),
            "span_to_depth": round(span / depth, 3),
        },
        "nodes": nodes,
        "members": members,
        "summary": {
            "node_count": len(nodes),
            "member_count": len(members),
            "by_role": roles,
            "total_length_mm": round(sum(m["length_mm"] for m in members), 4),
            "total_length_ft": round(sum(m["length_ft"] for m in members), 4),
            "distinct_lengths_mm": sorted(set(m["length_mm"] for m in members)),
        },
    }


def main():
    model = build()
    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)
    path = os.path.join(OUT_DIR, OUT_NAME + ".json")
    handle = open(path, "w")
    try:
        json.dump(model, handle, indent=2)
        handle.write("\n")
    finally:
        handle.close()

    s = model["summary"]
    print("wrote {0}".format(path))
    print("nodes={0} members={1}".format(s["node_count"], s["member_count"]))
    for role in sorted(s["by_role"]):
        info = s["by_role"][role]
        print("  {0:14s} count={1:3d} unit={2:10.3f} mm  total={3:10.1f} mm".format(
            role, info["count"], info["unit_mm"], info["total_mm"]))
    print("total length = {0:.1f} mm ({1:.2f} ft)".format(
        s["total_length_mm"], s["total_length_ft"]))
    print("distinct member lengths (mm): {0}".format(s["distinct_lengths_mm"]))
    return model


if __name__ == "__main__":
    main()
