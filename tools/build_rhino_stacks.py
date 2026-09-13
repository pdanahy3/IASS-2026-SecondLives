"""Build a Rhino model of salvaged steel members laid out as sorted stacks.

Run inside Rhino (RhinoScript Python). One dataset per Rhino document:

    exec(compile(open(PATH).read(), PATH, "exec"), g)
    g["main"]("A")

Members are modelled at their reusable length only, so members with
reusable_length_ft == 0 carry no solid and appear as a tag-only entry in the
REJECTED branch. Profiles are correct outer silhouettes, extruded as low-poly
meshes: rectangular HSS as a box, round HSS as a 12-sided cylinder, W-shapes as
the true I outline built from three boxes.

Document units are millimetres; source data is feet and inches.
"""

import math

import rhinoscriptsyntax as rs

DATA_DIR = r"c:\Users\pdanahy3\Downloads\IASS-2026-Workshop_SecondLives\wokshop-day\wokshop-day\data"

DATASETS = {
    "A": {"csv": "harmonized_source_A_gsr_reno_hss.csv", "root": "A_gsr_reno"},
    "B": {"csv": "harmonized_source_B_cambridge_pavilion.csv", "root": "B_cambridge_pavilion"},
}

FT = 304.8
IN = 25.4

GAP = 40.0          # clear spacing between members inside a bundle
BAY_GAP = 1500.0    # clear spacing between stacks
DOT_OFFSET = 200.0  # tag stand-off past the end of a member
REJECT_DX = -1800.0  # tag column offset, upstream of the bay start
LABEL_DX = -2900.0
REJECT_DZ = 160.0
REJECT_DY = 320.0
REJECT_PER_COL = 14
MAX_COLS = 12       # widest a bundle gets before it starts a new row

# Bays are packed into rows so the yard stays roughly square instead of
# stretching into a single 200 m ribbon.
TARGET_ROW_Y = 60000.0
AISLE = 5000.0
ROW_TAIL = 2500.0   # room past the longest member for its tags

# AISC dimensions in inches: depth, flange width, flange thickness, web thickness
W_SHAPES = {
    "W6X12": (6.03, 4.00, 0.280, 0.230),
    "W8X31": (8.00, 8.00, 0.435, 0.285),
    "W8X40": (8.25, 8.07, 0.560, 0.360),
    "W14X159": (14.98, 15.565, 1.190, 0.745),
}

TYPE_TOKENS = ("CABLE", "COL", "BEM", "IPB", "BRC", "GIR", "JST", "TRS", "PLT", "ELM")

TYPE_COLORS = {
    "COL": (196, 48, 48),
    "BEM": (48, 96, 200),
    "IPB": (56, 152, 88),
    "BRC": (224, 136, 32),
    "ELM": (140, 140, 148),
    "CABLE": (216, 200, 64),
    "OTHER": (168, 72, 176),
}

REJECT_COLOR = (96, 96, 96)
LABEL_COLOR = (24, 24, 24)


# ---------------------------------------------------------------- data loading

def _to_float(text):
    text = (text or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def load_rows(csv_name):
    path = DATA_DIR + "\\" + csv_name
    handle = open(path, "r")
    try:
        raw = handle.read()
    finally:
        handle.close()
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    if raw and raw[0] == u"\ufeff":
        raw = raw[1:]
    lines = [ln for ln in raw.split("\n") if ln.strip()]
    header = [h.strip() for h in lines[0].split(",")]
    rows = []
    for line in lines[1:]:
        cells = line.split(",")
        row = {}
        for idx, key in enumerate(header):
            row[key] = cells[idx].strip() if idx < len(cells) else ""
        rows.append(row)
    return rows


def member_type(element_id):
    parts = [p for p in element_id.replace("-", "_").split("_") if p]
    for token in TYPE_TOKENS:
        if token in parts:
            return token
    return "OTHER"


# ------------------------------------------------------------ section geometry

def _frac(text):
    text = text.strip()
    if "/" in text:
        num, den = text.split("/")
        return float(num) / float(den)
    return float(text)


def section_profile(section):
    """Return (kind, width_y_mm, height_z_mm, extra) for a section designation."""
    name = section.strip()
    upper = name.upper()

    if upper.startswith("HSS"):
        body = upper[3:]
        parts = body.split("X")
        numeric = []
        for part in parts:
            try:
                numeric.append(_frac(part))
            except (ValueError, ZeroDivisionError):
                return None
        if len(numeric) == 3:
            depth, width = numeric[0], numeric[1]
            return ("box", width * IN, depth * IN, None)
        if len(numeric) == 2:
            outer = numeric[0]
            return ("cyl", outer * IN, outer * IN, None)
        return None

    if upper in W_SHAPES:
        depth, flange_w, flange_t, web_t = W_SHAPES[upper]
        return ("wshape", flange_w * IN, depth * IN, (flange_t * IN, web_t * IN))

    return None


# --------------------------------------------------------------- mesh builders

def _add_box(verts, faces, x0, x1, ya, yb, za, zb):
    i = len(verts)
    verts.extend([
        (x0, ya, za), (x0, yb, za), (x0, yb, zb), (x0, ya, zb),
        (x1, ya, za), (x1, yb, za), (x1, yb, zb), (x1, ya, zb),
    ])
    faces.extend([
        (i + 0, i + 1, i + 2, i + 3),
        (i + 7, i + 6, i + 5, i + 4),
        (i + 0, i + 4, i + 5, i + 1),
        (i + 3, i + 2, i + 6, i + 7),
        (i + 0, i + 3, i + 7, i + 4),
        (i + 1, i + 5, i + 6, i + 2),
    ])


def _add_cylinder(verts, faces, x0, x1, yc, zc, radius, sides=12):
    base = len(verts)
    for end in (x0, x1):
        for k in range(sides):
            ang = 2.0 * math.pi * k / sides
            verts.append((end, yc + radius * math.cos(ang), zc + radius * math.sin(ang)))
    c0 = len(verts)
    verts.append((x0, yc, zc))
    c1 = len(verts)
    verts.append((x1, yc, zc))
    for k in range(sides):
        nxt = (k + 1) % sides
        faces.append((base + k, base + sides + k, base + sides + nxt, base + nxt))
        faces.append((base + nxt, base + k, c0, c0))
        faces.append((base + sides + k, base + sides + nxt, c1, c1))


def build_mesh(kind, extra, x0, length, width, height, yc, zc):
    """Mesh for one member, extruded along +X from x0, centred on (yc, zc)."""
    verts = []
    faces = []
    x1 = x0 + length
    if kind == "box":
        _add_box(verts, faces, x0, x1,
                 yc - width / 2.0, yc + width / 2.0,
                 zc - height / 2.0, zc + height / 2.0)
    elif kind == "cyl":
        _add_cylinder(verts, faces, x0, x1, yc, zc, width / 2.0)
    elif kind == "wshape":
        flange_t, web_t = extra
        ya, yb = yc - width / 2.0, yc + width / 2.0
        zbot, ztop = zc - height / 2.0, zc + height / 2.0
        _add_box(verts, faces, x0, x1, ya, yb, zbot, zbot + flange_t)
        _add_box(verts, faces, x0, x1, ya, yb, ztop - flange_t, ztop)
        _add_box(verts, faces, x0, x1,
                 yc - web_t / 2.0, yc + web_t / 2.0,
                 zbot + flange_t, ztop - flange_t)
    else:
        return None, None
    return verts, faces


# ------------------------------------------------------------------ formatting

def _safe(text):
    out = text
    for bad in ("/", ":", "*", "?", "\"", "<", ">", "|"):
        out = out.replace(bad, "-")
    return out.replace(" ", "")


def tag_text(row, reusable_ft, total_ft, mass, pct, carbon):
    lines = [row["element_id"], row["section_or_species"]]
    if total_ft is None:
        lines.append("reuse {0:.2f} ft (total n/a)".format(reusable_ft))
    else:
        lines.append("reuse {0:.2f} of {1:.2f} ft".format(reusable_ft, total_ft))
    lines.append("mass {0:.1f} kg".format(mass) if mass is not None else "mass n/a")
    lines.append("reusable {0:.1f}%".format(pct * 100.0) if pct is not None else "reusable n/a")
    lines.append("saved {0:.1f} kgCO2e".format(carbon) if carbon is not None else "saved n/a")
    return "\n".join(lines)


# ------------------------------------------------------------------- the build

def plan_stacks(rows):
    """Group members into stacks and pack the bays into rows of bays."""
    stacks = {}
    for row in rows:
        key = (member_type(row["element_id"]), row["section_or_species"])
        stacks.setdefault(key, []).append(row)

    plan = []
    unparsed = []
    for key in sorted(stacks.keys()):
        mtype, section = key
        members = stacks[key]
        profile = section_profile(section)

        reusable = []
        rejected = []
        for row in members:
            length_ft = _to_float(row["reusable_length_ft"]) or 0.0
            if length_ft > 0.0 and profile is not None:
                reusable.append((length_ft, row))
            else:
                rejected.append(row)
                if length_ft > 0.0 and profile is None:
                    unparsed.append(row["element_id"])
        reusable.sort(key=lambda item: -item[0])

        cols = 1
        step_y = 0.0
        step_z = 0.0
        bundle_width = 0.0
        bundle_height = 0.0
        max_length = 0.0
        if reusable:
            kind, width, height, extra = profile
            cols = min(MAX_COLS, int(math.ceil(math.sqrt(len(reusable)))))
            step_y = width + GAP
            step_z = height + GAP
            shelves = int(math.ceil(float(len(reusable)) / cols))
            bundle_width = cols * step_y
            bundle_height = shelves * step_z
            max_length = reusable[0][0] * FT

        reject_cols = 0
        if rejected:
            reject_cols = (len(rejected) - 1) // REJECT_PER_COL + 1

        plan.append({
            "mtype": mtype,
            "section": section,
            "members": members,
            "profile": profile,
            "reusable": reusable,
            "rejected": rejected,
            "cols": cols,
            "step_y": step_y,
            "step_z": step_z,
            "bundle_height": bundle_height,
            "bay_width": max(bundle_width, reject_cols * REJECT_DY, 600.0),
            "max_length": max_length,
        })

    row_x = 0.0
    y = 0.0
    row_depth = 0.0
    for entry in plan:
        if y > 0.0 and y + entry["bay_width"] > TARGET_ROW_Y:
            row_x += row_depth + AISLE
            y = 0.0
            row_depth = 0.0
        entry["x0"] = row_x
        entry["y0"] = y
        y += entry["bay_width"] + BAY_GAP
        row_depth = max(row_depth, entry["max_length"] + DOT_OFFSET + ROW_TAIL)

    return plan, unparsed


def main(dataset, write_user_text=True):
    spec = DATASETS[dataset]
    rows = load_rows(spec["csv"])

    root = spec["root"]
    rs.AddLayer(root)
    reuse_parent = rs.AddLayer("REUSABLE", parent=root)
    reject_parent = rs.AddLayer("REJECTED", parent=root)
    tag_parent = rs.AddLayer("TAGS", parent=root)
    label_layer = rs.AddLayer("LABELS", LABEL_COLOR, parent=root)

    plan, skipped = plan_stacks(rows)

    rs.EnableRedraw(False)
    made_solid = 0
    made_tag = 0

    for entry in plan:
        mtype = entry["mtype"]
        section = entry["section"]
        members = entry["members"]
        reusable = entry["reusable"]
        rejected = entry["rejected"]
        bay_x = entry["x0"]
        bay_y = entry["y0"]

        stack_name = "{0}__{1}".format(mtype, _safe(section))
        color = TYPE_COLORS.get(mtype, TYPE_COLORS["OTHER"])
        stack_group = "STACK__" + stack_name
        rs.AddGroup(stack_group)
        stack_ids = []

        if reusable:
            kind, width, height, extra = entry["profile"]
            layer = rs.AddLayer(stack_name, color, parent=reuse_parent)
            tag_layer = rs.AddLayer(stack_name, color, parent=tag_parent)
            rs.CurrentLayer(layer)
            cols = entry["cols"]
            step_y = entry["step_y"]
            step_z = entry["step_z"]

            for idx, (length_ft, row) in enumerate(reusable):
                col = idx % cols
                shelf = idx // cols
                yc = bay_y + col * step_y + width / 2.0
                zc = shelf * step_z + height / 2.0
                length = length_ft * FT

                verts, faces = build_mesh(kind, extra, bay_x, length, width, height, yc, zc)
                mesh_id = rs.AddMesh(verts, faces)
                if mesh_id is None:
                    skipped.append(row["element_id"])
                    continue
                rs.ObjectName(mesh_id, row["element_id"])

                mass = _to_float(row["mass_kg"])
                pct = _to_float(row["percent_reusable"])
                carbon = _to_float(row["embodied_carbon_savings_kgco2e"])
                total_ft = _to_float(row["length_ft"])

                dot_id = rs.AddTextDot(
                    tag_text(row, length_ft, total_ft, mass, pct, carbon),
                    (bay_x + length + DOT_OFFSET, yc, zc))
                rs.TextDotHeight(dot_id, 11)
                rs.ObjectLayer(dot_id, tag_layer)

                if write_user_text:
                    rs.SetUserText(mesh_id, "element_id", row["element_id"])
                    rs.SetUserText(mesh_id, "source", row["source"])
                    rs.SetUserText(mesh_id, "section", row["section_or_species"])
                    rs.SetUserText(mesh_id, "member_type", mtype)
                    rs.SetUserText(mesh_id, "reusable_length_ft", "{0:.3f}".format(length_ft))
                    if total_ft is not None:
                        rs.SetUserText(mesh_id, "length_ft", "{0:.3f}".format(total_ft))
                    if mass is not None:
                        rs.SetUserText(mesh_id, "mass_kg", "{0:.3f}".format(mass))
                    if pct is not None:
                        rs.SetUserText(mesh_id, "percent_reusable", "{0:.3f}".format(pct))
                    if carbon is not None:
                        rs.SetUserText(mesh_id, "embodied_carbon_savings_kgco2e",
                                       "{0:.3f}".format(carbon))

                member_group = "MBR__" + row["element_id"]
                rs.AddGroup(member_group)
                rs.AddObjectsToGroup([mesh_id, dot_id], member_group)
                stack_ids.extend([mesh_id, dot_id])
                made_solid += 1
                made_tag += 1

        if rejected:
            layer = rs.AddLayer(stack_name, REJECT_COLOR, parent=reject_parent)
            rs.CurrentLayer(layer)
            for idx, row in enumerate(rejected):
                col = idx // REJECT_PER_COL
                slot = idx % REJECT_PER_COL
                yc = bay_y + col * REJECT_DY
                zc = slot * REJECT_DZ
                total_ft = _to_float(row["length_ft"])
                mass = _to_float(row["mass_kg"])
                text = "{0}\n{1}\nNOT REUSABLE".format(
                    row["element_id"], row["section_or_species"])
                if total_ft is not None:
                    text += "\ntotal {0:.2f} ft".format(total_ft)
                if mass is not None:
                    text += "\nmass {0:.1f} kg".format(mass)
                dot_id = rs.AddTextDot(text, (bay_x + REJECT_DX, yc, zc))
                rs.TextDotHeight(dot_id, 10)
                member_group = "MBR__" + row["element_id"]
                rs.AddGroup(member_group)
                rs.AddObjectsToGroup([dot_id], member_group)
                stack_ids.append(dot_id)
                made_tag += 1

        if stack_ids:
            rs.AddObjectsToGroup(stack_ids, stack_group)

        rs.CurrentLayer(label_layer)
        total_reuse = float(sum(item[0] for item in reusable))
        total_mass = float(sum(_to_float(r["mass_kg"]) or 0.0 for r in members))
        total_carbon = float(sum(_to_float(r["embodied_carbon_savings_kgco2e"]) or 0.0 for r in members))
        label = "{0}  |  {1}\n{2} members ({3} reusable)\n{4:.1f} reusable ft\n{5:.0f} kg  |  {6:.0f} kgCO2e".format(
            mtype, section, len(members), len(reusable), total_reuse, total_mass, total_carbon)
        label_id = rs.AddTextDot(
            label, (bay_x + LABEL_DX, bay_y, entry["bundle_height"] + 500.0))
        rs.TextDotHeight(label_id, 20)

    rs.CurrentLayer(root)
    rs.EnableRedraw(True)

    return {
        "dataset": dataset,
        "rows": len(rows),
        "stacks": len(plan),
        "solids": made_solid,
        "tags": made_tag,
        "skipped_no_profile": skipped,
        "bay_rows": len(set(e["x0"] for e in plan)),
        "extent_x_mm": max(e["x0"] + e["max_length"] for e in plan),
        "extent_y_mm": max(e["y0"] + e["bay_width"] for e in plan),
    }
