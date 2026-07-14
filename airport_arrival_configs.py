"""Reviewed airport geometry and routing metadata for Arrival Mode.

Only airports with verified terminal or checkpoint-area geometry belong here.
All other tracked airports continue to use the feed-derived airport-overview
configuration built in ``app.py``.
"""

USGS_IMAGERY_URL = (
    "https://basemap.nationalmap.gov/arcgis/rest/services/"
    "USGSImageryOnly/MapServer/tile/{z}/{y}/{x}"
)
USGS_IMAGERY_ATTRIBUTION = "Imagery: USDA / USGS The National Map"


AIRPORT_DECISION_MAPS = {
    "LAS": {
        "decision_mode": "terminal_gate",
        "has_published_hours": True,
        "map": {
            "center": [36.0862, -115.1426],
            "bounds": [[36.0775, -115.1595], [36.0955, -115.1260]],
            "overview_zoom": 14,
            "detail_zoom": 16,
            "location_accuracy": "airport_overview",
            "tile_url": USGS_IMAGERY_URL,
            "tile_attribution": USGS_IMAGERY_ATTRIBUTION,
        },
        "source": {
            "label": "Official LAS security page",
            "url": "https://www.harryreidairport.com/security-at-las",
            "verified_on": "2026-07-10",
        },
        "terminals": [
            {
                "id": "t1",
                "marker_code": "T1",
                "label": "Terminal 1",
                "summary": "A, B, C, and some D-gate routing",
                "anchor": [36.0853711, -115.1480354],
                "location_accuracy": "terminal_curb_anchor",
                "checkpoints": [
                    {
                        "id": "las-t1-ab",
                        "label": "A/B Gates",
                        "aliases": ["T1 - A/B Gates", "Terminal 1 - A/B Gates"],
                        "primary_for": ["A", "B"],
                        "alternate_for": [],
                        "hours": "3:15 a.m.-1 a.m.",
                        "note": "Primary Terminal 1 checkpoint for A and B gates.",
                    },
                    {
                        "id": "las-t1-c",
                        "label": "C Gates",
                        "aliases": ["T1 - C Gates", "Terminal 1 - C Gates"],
                        "primary_for": ["C"],
                        "alternate_for": [],
                        "hours": "3:05 a.m.-10 p.m.",
                        "note": "Southwest-focused checkpoint for C gates.",
                    },
                    {
                        "id": "las-t1-cd",
                        "label": "C/D Gates",
                        "aliases": ["T1 - C/D Gates", "Terminal 1 - C/D Gates"],
                        "primary_for": ["D"],
                        "alternate_for": ["C"],
                        "hours": "Open 24 hours",
                        "note": "Terminal 1 option for D gates and an alternative for C gates.",
                    },
                ],
            },
            {
                "id": "t3",
                "marker_code": "T3",
                "label": "Terminal 3",
                "summary": "D and E gates, with a limited-hours Innovation option",
                "anchor": [36.0868828, -115.1371475],
                "location_accuracy": "terminal_curb_anchor",
                "checkpoints": [
                    {
                        "id": "las-t3-de",
                        "label": "Level 2 / D & E Gates",
                        "aliases": ["T3 - D/E Gates", "Terminal 3 - D/E Gates"],
                        "primary_for": ["D", "E"],
                        "alternate_for": [],
                        "hours": "3:30 a.m.-1:30 a.m.",
                        "note": "Main Terminal 3 checkpoint for D and E gates.",
                    },
                    {
                        "id": "las-t3-innovation",
                        "label": "Level Zero Innovation",
                        "aliases": [],
                        "primary_for": [],
                        "alternate_for": ["D", "E"],
                        "hours": "5 a.m.-1:30 p.m.",
                        "note": "Published checkpoint; the current LAS feed has no separate live reading.",
                        "published_only": True,
                    },
                ],
            },
        ],
    },
    "DCA": {
        "decision_mode": "terminal_checkpoint",
        "has_published_hours": False,
        "routing_note": (
            "Terminal 1 serves A gates. Terminal 2 North and South serve the "
            "B, C, D, and E gate areas. Confirm the terminal on your boarding pass."
        ),
        "map": {
            "center": [38.85175, -77.0431],
            "bounds": [[38.8468, -77.0476], [38.8563, -77.0385]],
            "overview_zoom": 15,
            "detail_zoom": 17,
            "location_accuracy": "checkpoint_area_overview",
            "tile_url": USGS_IMAGERY_URL,
            "tile_attribution": USGS_IMAGERY_ATTRIBUTION,
        },
        "source": {
            "label": "Official DCA security information",
            "url": "https://www.flyreagan.com/travel-information/security-information",
            "verified_on": "2026-07-13",
        },
        "terminals": [
            {
                "id": "t1",
                "marker_code": "T1",
                "label": "Terminal 1",
                "summary": "A gates",
                "anchor": [38.8481601, -77.0426800],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "dca-t1",
                        "label": "Terminal 1 (A Gates)",
                        "aliases": ["Terminal 1 (A Gates)"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Terminal 1 checkpoint for the A-gate area.",
                    }
                ],
            },
            {
                "id": "t2-south",
                "marker_code": "T2S",
                "label": "Terminal 2 South",
                "summary": "B, C, D, and E gates",
                "anchor": [38.8522994, -77.0427533],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "dca-t2-south",
                        "label": "Terminal 2 South",
                        "aliases": ["Terminal 2 South (B, C, D, E Gates)"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "South checkpoint serving Terminal 2 gate areas.",
                    }
                ],
            },
            {
                "id": "t2-north",
                "marker_code": "T2N",
                "label": "Terminal 2 North",
                "summary": "B, C, D, and E gates",
                "anchor": [38.8549527, -77.0438429],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "dca-t2-north",
                        "label": "Terminal 2 North",
                        "aliases": ["Terminal 2 North (B, C, D, E Gates)"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "North checkpoint serving Terminal 2 gate areas.",
                    }
                ],
            },
        ],
    },
    "SFO": {
        "decision_mode": "terminal_checkpoint",
        "has_published_hours": False,
        "all_checkpoints_reach_all_gates": True,
        "routing_note": (
            "SFO states that every gate is accessible from every security "
            "checkpoint. Terminal selection groups nearby checkpoints; it does "
            "not limit which checkpoint you may use."
        ),
        "map": {
            "center": [37.6160, -122.3868],
            "bounds": [[37.6108, -122.3942], [37.6213, -122.3795]],
            "overview_zoom": 14.75,
            "detail_zoom": 16.25,
            "location_accuracy": "terminal_building_overview",
            "tile_url": USGS_IMAGERY_URL,
            "tile_attribution": USGS_IMAGERY_ATTRIBUTION,
        },
        "source": {
            "label": "Official SFO check-in and security guide",
            "url": "https://www.flysfo.com/passengers/flight-info/check-in-security",
            "verified_on": "2026-07-13",
        },
        "terminals": [
            {
                "id": "intl-a",
                "marker_code": "INTL A",
                "marker_label": "International A",
                "marker_offset": [-10, 18],
                "label": "International Terminal A",
                "summary": "Checkpoint A",
                "anchor": [37.6130996, -122.3890632],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [
                    {
                        "id": "sfo-checkpoint-a",
                        "label": "Checkpoint A",
                        "aliases": ["Checkpoint A · International Terminal A"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Checkpoint in the International Terminal A area.",
                    }
                ],
            },
            {
                "id": "t1",
                "marker_code": "T1",
                "marker_label": "Harvey Milk T1",
                "marker_offset": [10, -18],
                "label": "Harvey Milk Terminal 1",
                "summary": "Checkpoint B and B Mezzanine",
                "anchor": [37.6130906, -122.3848929],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [
                    {
                        "id": "sfo-checkpoint-b",
                        "label": "Checkpoint B",
                        "aliases": ["Checkpoint B · Harvey Milk Terminal 1"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Main Checkpoint B in Harvey Milk Terminal 1.",
                    },
                    {
                        "id": "sfo-checkpoint-b-mezzanine",
                        "label": "Checkpoint B - Mezzanine Level",
                        "aliases": [
                            "Checkpoint B - Mezzanine Level · Harvey Milk Terminal 1"
                        ],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Mezzanine-level Checkpoint B in Harvey Milk Terminal 1.",
                    },
                ],
            },
            {
                "id": "t2",
                "marker_code": "T2",
                "marker_label": "Terminal 2",
                "label": "Terminal 2",
                "summary": "Checkpoint D",
                "anchor": [37.6169552, -122.3826485],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [
                    {
                        "id": "sfo-checkpoint-d",
                        "label": "Checkpoint D",
                        "aliases": ["Checkpoint D · Terminal 2"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Checkpoint in Terminal 2.",
                    }
                ],
            },
            {
                "id": "t3",
                "marker_code": "T3",
                "marker_label": "Terminal 3",
                "marker_offset": [10, -16],
                "label": "Terminal 3",
                "summary": "Checkpoint F",
                "anchor": [37.6190694, -122.3870951],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [
                    {
                        "id": "sfo-checkpoint-f",
                        "label": "Checkpoint F",
                        "aliases": ["Checkpoint F · Terminal 3"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Checkpoint in Terminal 3.",
                    }
                ],
            },
            {
                "id": "intl-g",
                "marker_code": "INTL G",
                "marker_label": "International G",
                "marker_offset": [-10, 16],
                "label": "International Terminal G",
                "summary": "Checkpoint G",
                "anchor": [37.6176902, -122.3910682],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [
                    {
                        "id": "sfo-checkpoint-g",
                        "label": "Checkpoint G",
                        "aliases": ["Checkpoint G · International Terminal G"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Checkpoint in the International Terminal G area.",
                    }
                ],
            },
        ],
    },
}
