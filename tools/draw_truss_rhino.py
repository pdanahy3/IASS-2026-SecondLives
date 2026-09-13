"""Draw the truss JSON model in Rhino as centreline curves.

Run inside Rhino (RhinoScript Python):

    exec(compile(open(PATH).read(), PATH, "exec"), g)
    g["main"]()

Reads the JSON written by tools/build_truss.py and adds one line per member.
Lines only, no solids: layered and coloured by role, named by member id, with
the source data attached as user text.
"""

import json

import rhinoscriptsyntax as rs

JSON_PATH = (r"c:\Users\pdanahy3\Downloads\IASS-2026-Workshop_SecondLives"
             r"\rhino\SecondLives_truss_warren_20m.json")

ROLE_LAYERS = {
    "bottom_chord": ("BOTTOM_CHORD", (48, 96, 200)),
    "top_chord": ("TOP_CHORD", (196, 48, 48)),
    "diagonal": ("DIAGONALS", (56, 152, 88)),
}


def main(json_path=JSON_PATH):
    handle = open(json_path, "r")
    try:
        model = json.load(handle)
    finally:
        handle.close()

    root = "TRUSS_WARREN_{0:.0f}M".format(model["parameters"]["span_mm"] / 1000.0)
    rs.AddLayer(root)

    nodes = dict((n["id"], n) for n in model["nodes"])

    rs.EnableRedraw(False)
    group = "TRUSS"
    rs.AddGroup(group)
    made = []

    for role in ("bottom_chord", "top_chord", "diagonal"):
        name, color = ROLE_LAYERS[role]
        layer = rs.AddLayer(name, color, parent=root)
        rs.CurrentLayer(layer)
        for member in model["members"]:
            if member["role"] != role:
                continue
            a = nodes[member["start"]]
            b = nodes[member["end"]]
            line_id = rs.AddLine((a["x"], a["y"], a["z"]), (b["x"], b["y"], b["z"]))
            rs.ObjectName(line_id, member["id"])
            rs.SetUserText(line_id, "member_id", member["id"])
            rs.SetUserText(line_id, "role", role)
            rs.SetUserText(line_id, "start_node", member["start"])
            rs.SetUserText(line_id, "end_node", member["end"])
            rs.SetUserText(line_id, "length_mm", "{0:.4f}".format(member["length_mm"]))
            rs.SetUserText(line_id, "length_ft", "{0:.4f}".format(member["length_ft"]))
            made.append(line_id)

    rs.AddObjectsToGroup(made, group)
    rs.CurrentLayer(root)
    rs.EnableRedraw(True)

    return {
        "lines": len(made),
        "expected": model["summary"]["member_count"],
        "root_layer": root,
    }
