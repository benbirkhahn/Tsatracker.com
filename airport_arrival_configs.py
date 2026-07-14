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
    "EWR": {
        "decision_mode": "terminal_checkpoint",
        "has_published_hours": False,
        "routing_note": (
            "Choose the terminal on your boarding pass. Terminal B publishes "
            "three separate gate-range readings, so compare the range closest "
            "to your departure gate."
        ),
        "map": {
            "center": [40.6901, -74.1802],
            "bounds": [[40.6800, -74.1910], [40.6990, -74.1710]],
            "overview_zoom": 14.25,
            "detail_zoom": 16.25,
            "location_accuracy": "terminal_building_overview",
            "tile_url": USGS_IMAGERY_URL,
            "tile_attribution": USGS_IMAGERY_ATTRIBUTION,
        },
        "source": {
            "label": "Official EWR terminal guide",
            "url": "https://www.newarkairport.com/explore-ewr/terminals",
            "verified_on": "2026-07-13",
        },
        "terminals": [
            {
                "id": "terminal-a",
                "marker_code": "A",
                "marker_label": "Terminal A",
                "label": "Terminal A",
                "summary": "Terminal A checkpoint",
                "anchor": [40.6839579, -74.1861871],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [
                    {
                        "id": "ewr-terminal-a",
                        "label": "Terminal A",
                        "aliases": ["Terminal A"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Published Terminal A checkpoint reading.",
                    }
                ],
            },
            {
                "id": "terminal-b",
                "marker_code": "B",
                "marker_label": "Terminal B",
                "label": "Terminal B",
                "summary": "Three gate-range checkpoint readings",
                "anchor": [40.6902858, -74.1761701],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [
                    {
                        "id": "ewr-terminal-b-40-49",
                        "label": "Gates 40-49",
                        "aliases": ["Terminal B (40-49)"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Terminal B checkpoint reading for gates 40-49.",
                    },
                    {
                        "id": "ewr-terminal-b-51-57",
                        "label": "Gates 51-57",
                        "aliases": ["Terminal B (51-57)"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Terminal B checkpoint reading for gates 51-57.",
                    },
                    {
                        "id": "ewr-terminal-b-60-68",
                        "label": "Gates 60-68",
                        "aliases": ["Terminal B (60-68)"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Terminal B checkpoint reading for gates 60-68.",
                    },
                ],
            },
            {
                "id": "terminal-c",
                "marker_code": "C",
                "marker_label": "Terminal C",
                "label": "Terminal C",
                "summary": "Terminal C checkpoint",
                "anchor": [40.6960980, -74.1764498],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [
                    {
                        "id": "ewr-terminal-c",
                        "label": "Terminal C",
                        "aliases": ["Terminal C"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Published Terminal C checkpoint reading.",
                    }
                ],
            },
        ],
    },
    "LGA": {
        "decision_mode": "terminal_checkpoint",
        "has_published_hours": False,
        "routing_note": (
            "Choose Terminal B or Terminal C from your boarding pass. Each "
            "terminal has its own published checkpoint reading."
        ),
        "map": {
            "center": [40.7715, -73.8680],
            "bounds": [[40.7655, -73.8775], [40.7775, -73.8580]],
            "overview_zoom": 15,
            "detail_zoom": 16.5,
            "location_accuracy": "terminal_building_overview",
            "tile_url": USGS_IMAGERY_URL,
            "tile_attribution": USGS_IMAGERY_ATTRIBUTION,
        },
        "source": {
            "label": "Official LGA airport maps",
            "url": "https://www.laguardiaairport.com/at-airport/airport-maps",
            "verified_on": "2026-07-13",
        },
        "terminals": [
            {
                "id": "terminal-b",
                "marker_code": "B",
                "marker_label": "Terminal B",
                "label": "Terminal B",
                "summary": "Terminal B checkpoint",
                "anchor": [40.7729776, -73.8720645],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [
                    {
                        "id": "lga-terminal-b",
                        "label": "Terminal B",
                        "aliases": ["Terminal B"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Published Terminal B checkpoint reading.",
                    }
                ],
            },
            {
                "id": "terminal-c",
                "marker_code": "C",
                "marker_label": "Terminal C",
                "label": "Terminal C",
                "summary": "Terminal C checkpoint",
                "anchor": [40.7700148, -73.8629674],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [
                    {
                        "id": "lga-terminal-c",
                        "label": "Terminal C",
                        "aliases": ["Terminal C"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Published Terminal C checkpoint reading.",
                    }
                ],
            },
        ],
    },
    "BOS": {
        "decision_mode": "terminal_checkpoint",
        "has_published_hours": False,
        "routing_note": (
            "Choose the terminal and checkpoint shown on your boarding pass. "
            "Terminals A, B, and E publish more than one checkpoint, so compare "
            "the gate range or checkpoint number before choosing a line."
        ),
        "map": {
            "center": [42.3661, -71.0194],
            "bounds": [[42.3603, -71.0265], [42.3713, -71.0130]],
            "overview_zoom": 15.25,
            "detail_zoom": 17,
            "location_accuracy": "terminal_building_overview",
            "tile_url": USGS_IMAGERY_URL,
            "tile_attribution": USGS_IMAGERY_ATTRIBUTION,
        },
        "source": {
            "label": "Official BOS security wait times",
            "url": "https://www.massport.com/logan-airport/at-the-airport/security-wait-times",
            "verified_on": "2026-07-13",
        },
        "terminals": [
            {
                "id": "terminal-a",
                "marker_code": "A",
                "marker_label": "Terminal A",
                "marker_offset": [-10, -6],
                "label": "Terminal A",
                "summary": "Checkpoints 1 and 2",
                "anchor": [42.3654402, -71.0228987],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [
                    {
                        "id": "bos-checkpoint-1-a-gates",
                        "label": "Checkpoint 1: A Gates",
                        "aliases": ["Checkpoint 1: A Gates"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Standard screening checkpoint for Terminal A gates.",
                    },
                    {
                        "id": "bos-checkpoint-2-a-gates-precheck-only",
                        "label": "Checkpoint 2: A Gates PreCheck Only",
                        "aliases": ["Checkpoint 2: A Gates PreCheck Only"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "PreCheck-only checkpoint for Terminal A gates.",
                    },
                ],
            },
            {
                "id": "terminal-b",
                "marker_code": "B",
                "marker_label": "Terminal B",
                "marker_offset": [10, 12],
                "label": "Terminal B",
                "summary": "B1-B22 and B23-B40 checkpoint areas",
                "anchor": [42.36295, -71.01865],
                "location_accuracy": "terminal_building_overview_anchor",
                "checkpoints": [
                    {
                        "id": "bos-checkpoint-3-gates-b1-b22",
                        "label": "Checkpoint 3: Gates B1-B22",
                        "aliases": ["Checkpoint 3: Gates B1 - B22"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Terminal B checkpoint for gates B1-B22.",
                    },
                    {
                        "id": "bos-checkpoint-4-gates-b23-40",
                        "label": "Checkpoint 4: Gates B23-B40",
                        "aliases": ["Checkpoint 4: Gates B23 - 40"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Terminal B checkpoint for gates B23-B40.",
                    },
                ],
            },
            {
                "id": "terminal-c",
                "marker_code": "C",
                "marker_label": "Terminal C",
                "marker_offset": [10, 4],
                "label": "Terminal C",
                "summary": "Checkpoint 5",
                "anchor": [42.3667611, -71.0160810],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [
                    {
                        "id": "bos-checkpoint-5-terminal-c",
                        "label": "Checkpoint 5: Terminal C",
                        "aliases": ["Checkpoint 5: Terminal C"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Published checkpoint reading for Terminal C.",
                    }
                ],
            },
            {
                "id": "terminal-e",
                "marker_code": "E",
                "marker_label": "Terminal E",
                "marker_offset": [-10, -10],
                "label": "Terminal E",
                "summary": "Checkpoints 6 and 7",
                "anchor": [42.36905, -71.02045],
                "location_accuracy": "terminal_building_overview_anchor",
                "checkpoints": [
                    {
                        "id": "bos-checkpoint-6-all-e-gates",
                        "label": "Checkpoint 6: All E Gates",
                        "aliases": ["Checkpoint 6: All E Gates"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Terminal E checkpoint serving all E gates.",
                    },
                    {
                        "id": "bos-checkpoint-7-all-e-gates",
                        "label": "Checkpoint 7: All E Gates",
                        "aliases": ["Checkpoint 7: All E Gates"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Terminal E checkpoint serving all E gates.",
                    },
                ],
            },
        ],
    },
    "ORD": {
        "decision_mode": "terminal_checkpoint",
        "has_published_hours": False,
        "routing_note": (
            "Choose the terminal on your boarding pass. Terminals 1-3 are "
            "connected after security, while Terminal 5 is a separate screening "
            "environment; the panel keeps each published checkpoint distinct."
        ),
        "map": {
            "center": [41.9765, -87.8990],
            "bounds": [[41.9715, -87.9125], [41.9815, -87.8835]],
            "overview_zoom": 15,
            "detail_zoom": 16.5,
            "location_accuracy": "terminal_building_overview",
            "tile_url": USGS_IMAGERY_URL,
            "tile_attribution": USGS_IMAGERY_ATTRIBUTION,
        },
        "source": {
            "label": "Official ORD security information",
            "url": "https://www.flychicago.com/ohare/myflight/security/Pages/TSA.aspx",
            "verified_on": "2026-07-13",
        },
        "terminals": [
            {
                "id": "terminal-1",
                "marker_code": "T1",
                "marker_label": "Terminal 1",
                "marker_offset": [-14, -14],
                "label": "Terminal 1",
                "summary": "Terminal-level Economy and PreCheck feed",
                "anchor": [41.9788404, -87.9064815],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [
                    {
                        "id": "ord-terminal-1",
                        "label": "Terminal 1 security",
                        "aliases": [
                            "Terminal 1 — Economy",
                            "Terminal 1 — TSA PreCheck",
                            "Terminal 1 — Priority",
                        ],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "The live source groups Terminal 1 by lane type rather than checkpoint number.",
                    }
                ],
            },
            {
                "id": "terminal-2",
                "marker_code": "T2",
                "marker_label": "Terminal 2",
                "marker_offset": [12, 14],
                "label": "Terminal 2",
                "summary": "Checkpoint 5",
                "anchor": [41.9765332, -87.9050586],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [
                    {
                        "id": "ord-terminal-2-checkpoint-5",
                        "label": "Checkpoint 5",
                        "aliases": [
                            "Terminal 2 — Checkpoint 5 General",
                            "Terminal 2 — Checkpoint 5 TSA PreCheck",
                        ],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Terminal 2 checkpoint 5 general and PreCheck readings.",
                    }
                ],
            },
            {
                "id": "terminal-3",
                "marker_code": "T3",
                "marker_label": "Terminal 3",
                "marker_offset": [10, -12],
                "label": "Terminal 3",
                "summary": "Checkpoints 6, 7, 7A, 8, and 9",
                "anchor": [41.9767955, -87.9009121],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [
                    {
                        "id": "ord-terminal-3-checkpoint-6",
                        "label": "Checkpoint 6",
                        "aliases": ["Terminal 3 — Checkpoint 6"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Terminal 3 checkpoint 6 reading.",
                    },
                    {
                        "id": "ord-terminal-3-checkpoint-7",
                        "label": "Checkpoint 7",
                        "aliases": ["Terminal 3 — Checkpoint 7 General"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Terminal 3 checkpoint 7 general reading.",
                    },
                    {
                        "id": "ord-terminal-3-checkpoint-7a",
                        "label": "Checkpoint 7A",
                        "aliases": ["Terminal 3 — Checkpoint 7A"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Terminal 3 checkpoint 7A reading.",
                    },
                    {
                        "id": "ord-terminal-3-checkpoint-8",
                        "label": "Checkpoint 8",
                        "aliases": [
                            "Terminal 3 — Checkpoint 8 General",
                            "Terminal 3 — Checkpoint 8 TSA PreCheck",
                        ],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Terminal 3 checkpoint 8 general and PreCheck readings.",
                    },
                    {
                        "id": "ord-terminal-3-checkpoint-9",
                        "label": "Checkpoint 9",
                        "aliases": ["Terminal 3 — Checkpoint 9"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Terminal 3 checkpoint 9 feed reading; verify operating status with ORD.",
                    },
                ],
            },
            {
                "id": "terminal-5",
                "marker_code": "T5",
                "marker_label": "Terminal 5",
                "label": "Terminal 5",
                "summary": "Checkpoint 10",
                "anchor": [41.9757946, -87.8875129],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [
                    {
                        "id": "ord-terminal-5-checkpoint-10",
                        "label": "Checkpoint 10",
                        "aliases": ["Terminal 5 — Checkpoint 10"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Terminal 5 checkpoint 10 reading.",
                    }
                ],
            },
        ],
    },
}
