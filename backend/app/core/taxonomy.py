"""
Static taxonomy & evidence-requirement configuration.
This corresponds to the claims.csv / evidence_requirements.csv concept from
the spec, but expressed as importable Python config so the rest of the
system can validate against it without re-parsing CSVs on every request.
"""

OBJECT_PARTS = {
    "car": [
        "front_bumper", "rear_bumper", "door", "hood", "windshield",
        "side_mirror", "headlight", "taillight", "fender", "quarter_panel", "body",
    ],
    "laptop": [
        "screen", "keyboard", "trackpad", "hinge", "lid",
        "corner", "port", "base", "body",
    ],
    "package": [
        "box", "package_corner", "package_side", "seal", "label", "contents",
    ],
}

OBJECT_ISSUES = {
    "car": ["dent", "scratch", "crack", "glass_shatter", "broken_part", "missing_part"],
    "laptop": ["crack", "broken_part", "water_damage", "scratch", "missing_part"],
    "package": ["torn_packaging", "crushed_packaging", "water_damage", "missing_part"],
}

# Required viewing angles per (object, part, issue) — falls back to a
# sensible default per object type if no specific rule is defined.
EVIDENCE_REQUIREMENTS = {
    ("laptop", "screen", "crack"): ["front_view", "closeup_crack_view", "side_angle"],
    ("laptop", "keyboard", "water_damage"): ["top_down_view", "closeup_view", "port_view"],
    ("car", "front_bumper", "dent"): ["front_view", "closeup_view", "side_angle"],
    ("car", "windshield", "glass_shatter"): ["front_view", "closeup_crack_view", "interior_view"],
    ("package", "box", "crushed_packaging"): ["full_box_view", "closeup_view", "label_view"],
}

DEFAULT_REQUIREMENTS = {
    "car": ["front_view", "side_angle", "closeup_view"],
    "laptop": ["front_view", "closeup_view", "side_angle"],
    "package": ["full_box_view", "closeup_view", "label_view"],
}

# Cause -> expected damage pattern mapping used by the Story Consistency Engine.
EXPECTED_DAMAGE_PATTERNS = {
    "fall": {
        "laptop": "corner_or_screen_impact_with_branching_fracture",
        "car": "localized_dent_or_scratch_at_contact_point",
        "package": "crushed_corner",
    },
    "collision": {
        "car": "directional_dent_with_paint_transfer_or_bumper_deformation",
        "laptop": "localized_impact_crack",
        "package": "crushed_side",
    },
    "water_spill": {
        "laptop": "water_damage_no_mechanical_fracture",
        "package": "water_damage_no_mechanical_fracture",
        "car": "water_damage_no_mechanical_fracture",
    },
    "theft_attempt": {
        "car": "broken_window_or_forced_lock_damage",
        "laptop": "missing_part_or_pry_marks",
        "package": "torn_packaging_seal_broken",
    },
    "shipping_mishandling": {
        "package": "crushed_or_torn_packaging",
    },
    "unknown": {
        "laptop": "unspecified",
        "car": "unspecified",
        "package": "unspecified",
    },
}

def get_required_views(claim_object: str, part: str | None, issue: str | None) -> list[str]:
    if part and issue:
        key = (claim_object, part, issue)
        if key in EVIDENCE_REQUIREMENTS:
            return EVIDENCE_REQUIREMENTS[key]
    return DEFAULT_REQUIREMENTS.get(claim_object, ["front_view", "closeup_view"])
