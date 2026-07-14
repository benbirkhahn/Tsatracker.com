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
    "ATL": {
        "decision_mode": "terminal_checkpoint",
        "has_published_hours": True,
        "all_checkpoints_reach_all_gates": True,
        "routing_note": (
            "All concourses and aircraft gates are accessible from any security checkpoint. "
            "ATL publishes separate live readings for Main, North, Lower North, South, and International Main."
        ),
        "map": {
            "center": [33.6407, -84.4277],
            "bounds": [[33.6265, -84.4535], [33.6528, -84.4020]],
            "overview_zoom": 13.75,
            "detail_zoom": 15.5,
            "location_accuracy": "checkpoint_area_overview",
            "tile_url": USGS_IMAGERY_URL,
            "tile_attribution": USGS_IMAGERY_ATTRIBUTION,
        },
        "source": {
            "label": "Official ATL live wait times",
            "url": "https://dev.atl.com/atlsync/security-wait-times/",
            "verified_on": "2026-07-13",
        },
        "terminals": [
            {
                "id": "main",
                "marker_code": "MAIN",
                "marker_label": "Domestic Main",
                "marker_offset": [0, 18],
                "label": "Main Checkpoint",
                "summary": "Domestic Terminal Main",
                # Domestic Terminal, west of Concourse T; not a concourse pin.
                "anchor": [33.6409, -84.4440],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "atl-main",
                        "label": "Main Checkpoint",
                        "aliases": [
                            "Main Checkpoint",
                            "Main Security Checkpoint",
                            "Domestic Terminal Main",
                        ],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "24 hours",
                        "note": "Main domestic checkpoint on the official ATL live dashboard.",
                    }
                ],
            },
            {
                "id": "north",
                "marker_code": "NORTH",
                "marker_label": "Domestic North",
                "marker_offset": [-18, -10],
                "label": "North Checkpoint",
                "summary": "Domestic Terminal North",
                # North end of the Domestic Terminal checkpoint area.
                "anchor": [33.64105, -84.4449],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "atl-north",
                        "label": "North Checkpoint",
                        "aliases": [
                            "North Checkpoint",
                            "North Security Checkpoint",
                            "Domestic Terminal North",
                        ],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "4:00 a.m. - 9:00 p.m.",
                        "note": "North domestic checkpoint on the official ATL live dashboard.",
                    }
                ],
            },
            {
                "id": "lower-north",
                "marker_code": "LOWER N",
                "marker_label": "Lower North",
                "marker_offset": [18, -10],
                "label": "Lower North Checkpoint",
                "summary": "Domestic Terminal Lower North",
                # Lower North remains within the Domestic Terminal footprint.
                "anchor": [33.64075, -84.44485],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "atl-lower-north",
                        "label": "Lower North Checkpoint",
                        "aliases": [
                            "Lower North Checkpoint",
                            "Lower North Security Checkpoint",
                            "Domestic Terminal Lower North",
                        ],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "3:30 a.m. - 9:00 p.m.",
                        "note": "Lower North domestic checkpoint on the official ATL live dashboard.",
                    }
                ],
            },
            {
                "id": "south",
                "marker_code": "SOUTH",
                "marker_label": "Domestic South",
                "marker_offset": [18, 14],
                "label": "South Checkpoint",
                "summary": "Domestic Terminal South",
                # South end of the Domestic Terminal checkpoint area.
                "anchor": [33.6405, -84.4439],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "atl-south",
                        "label": "South Checkpoint",
                        "aliases": [
                            "South Checkpoint",
                            "South Security Checkpoint",
                            "Domestic Terminal South",
                        ],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "4:00 a.m. - 9:00 p.m.",
                        "note": "South domestic checkpoint on the official ATL live dashboard.",
                    }
                ],
            },
            {
                "id": "international-main",
                "marker_code": "INTL",
                "marker_label": "International Main",
                "marker_offset": [-20, 0],
                "label": "International Main Checkpoint",
                "summary": "International Terminal Departures",
                # International Terminal, east of Concourse F.
                "anchor": [33.64037, -84.41821],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "atl-international-main",
                        "label": "International Main Checkpoint",
                        "aliases": [
                            "International Main Checkpoint",
                            "International Terminal Departures",
                            "International Main",
                        ],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "4:30 a.m. - 12:00 a.m.; PreCheck 7:00-10:00 a.m. and 2:00-7:00 p.m.",
                        "note": "International checkpoint on the official ATL live dashboard.",
                    }
                ],
            },
        ],
    },
    "CLT": {
        "decision_mode": "terminal_checkpoint",
        "has_published_hours": True,
        "all_checkpoints_reach_all_gates": True,
        "routing_note": (
            "All concourses and aircraft gates are accessible from any security checkpoint. "
            "Checkpoint 2 is the primary hub for dedicated Main PreCheck lanes."
        ),
        "map": {
            "center": [35.2140, -80.9431],
            "bounds": [[35.2075, -80.9525], [35.2205, -80.9325]],
            "overview_zoom": 14.25,
            "detail_zoom": 16,
            "location_accuracy": "checkpoint_area_overview",
            "tile_url": USGS_IMAGERY_URL,
            "tile_attribution": USGS_IMAGERY_ATTRIBUTION,
        },
        "source": {
            "label": "Official CLT Security Dashboard",
            "url": "https://www.cltairport.com/airport-info/security/",
            "verified_on": "2026-07-13",
        },
        "terminals": [
            {
                "id": "checkpoint-1",
                "marker_code": "C1",
                "marker_label": "Checkpoint 1",
                "marker_offset": [-16, 10],
                "label": "Checkpoint 1",
                "summary": "B-side checkpoint",
                # West side of CLT's single passenger terminal, near Concourses A/B.
                "anchor": [35.2206, -80.9448],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "clt-checkpoint-1",
                        "label": "Checkpoint 1",
                        "aliases": [
                            "Checkpoint 1",
                            "Checkpoint 1 (Standard)",
                            "Checkpoint 1 (main)",
                        ],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "3:45 a.m. - 8 p.m.",
                        "note": "Standard, special-assistance, and family screening at Checkpoint 1.",
                    }
                ],
            },
            {
                "id": "checkpoint-2",
                "marker_code": "C2",
                "marker_label": "Checkpoint 2",
                "marker_offset": [0, -14],
                "label": "Checkpoint 2",
                "summary": "Main PreCheck checkpoint",
                # Central terminal frontage; CLT's dedicated Main PreCheck location.
                "anchor": [35.2206, -80.9433],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "clt-checkpoint-2",
                        "label": "Checkpoint 2",
                        "aliases": [
                            "Checkpoint 2",
                            "Checkpoint 2 (Standard)",
                            "Checkpoint 2 (PreCheck)",
                            "Checkpoint 2 (main)",
                        ],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "Standard/Special Assistance 7 p.m. - 11 p.m.; Main PreCheck 3:45 a.m. - 11 p.m.; Employee 8 p.m. - 11 p.m.",
                        "note": "Checkpoint 2 is the main PreCheck checkpoint at CLT.",
                    }
                ],
            },
            {
                "id": "checkpoint-3",
                "marker_code": "C3",
                "marker_label": "Checkpoint 3",
                "marker_offset": [16, 10],
                "label": "Checkpoint 3",
                "summary": "D/E-side checkpoint",
                # East side of the passenger terminal, near Concourses D/E.
                "anchor": [35.2206, -80.9418],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "clt-checkpoint-3",
                        "label": "Checkpoint 3",
                        "aliases": [
                            "Checkpoint 3",
                            "Checkpoint 3 (Standard)",
                            "Checkpoint 3 (main)",
                        ],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "3:45 a.m. - 8 p.m.",
                        "note": "Standard, special-assistance, and employee screening at Checkpoint 3.",
                    }
                ],
            },
        ],
    },
    "JAX": {
        "decision_mode": "terminal_checkpoint",
        "has_published_hours": True,
        "all_checkpoints_reach_all_gates": True,
        "routing_note": (
            "JAX uses a single central checkpoint in the main terminal building. "
            "The PreCheck and Premier/Special Needs lanes close around 7:00 p.m., so late departures use Standard screening."
        ),
        "map": {
            "center": [30.4941, -81.6879],
            "bounds": [[30.4902, -81.6946], [30.4994, -81.6810]],
            "overview_zoom": 14.75,
            "detail_zoom": 16.25,
            "location_accuracy": "checkpoint_area_overview",
            "tile_url": USGS_IMAGERY_URL,
            "tile_attribution": USGS_IMAGERY_ATTRIBUTION,
        },
        "source": {
            "label": "Official JAX Live Wait Times",
            "url": "https://www.flyjax.com/content.aspx?id=3583",
            "verified_on": "2026-07-13",
        },
        "terminals": [
            {
                "id": "main",
                "marker_code": "JAX",
                "marker_label": "Main Terminal",
                "marker_offset": [0, 0],
                "label": "Main Checkpoint",
                "summary": "Central terminal checkpoint",
                # Central area of the Main Terminal building; not the adjacent roadway.
                "anchor": [30.4915, -81.6846],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "jax-main",
                        "label": "Main Checkpoint",
                        "aliases": ["Standard", "Priority Lane", "TSA Pre"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "4:00 a.m. - 7:00 p.m.",
                        "note": "JAX central checkpoint. PreCheck and special-needs lanes close around 7:00 p.m.",
                    }
                ],
            }
        ],
    },
    "JFK": {
        "decision_mode": "terminal_checkpoint",
        "has_published_hours": False,
        "all_checkpoints_reach_all_gates": False,
        "routing_note": (
            "JFK behaves like separate mini-airports. Terminal choice matters, and changing terminals means leaving security and reclearing at the new terminal."
        ),
        "map": {
            "center": [40.6413, -73.7781],
            "bounds": [[40.6267, -73.7958], [40.6565, -73.7582]],
            "overview_zoom": 13.75,
            "detail_zoom": 15.5,
            "location_accuracy": "checkpoint_area_overview",
            "tile_url": USGS_IMAGERY_URL,
            "tile_attribution": USGS_IMAGERY_ATTRIBUTION,
        },
        "source": {
            "label": "Official JFK terminal wait times",
            "url": "https://www.jfkairport.com/to-and-from/security-wait-times",
            "verified_on": "2026-07-14",
        },
        "terminals": [
            {
                "id": "terminal-1",
                "marker_code": "T1",
                "marker_label": "Terminal 1",
                "marker_offset": [-18, 8],
                "label": "Terminal 1",
                "summary": "Terminal 1 departures",
                # Current Terminal 1 departures building, west of Terminal 4.
                "anchor": [40.6428, -73.7914],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "jfk-terminal-1",
                        "label": "Terminal 1",
                        "aliases": ["Terminal 1", "T1", "Terminal 1 (General TSA)", "Terminal 1 (TSA Pre✓)"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Terminal 1 wait-time checkpoint from the official terminal page.",
                    }
                ],
            },
            {
                "id": "terminal-4",
                "marker_code": "T4",
                "marker_label": "Terminal 4",
                "marker_offset": [16, -8],
                "label": "Terminal 4",
                "summary": "Terminal 4 departures",
                # Terminal 4 departures building.
                "anchor": [40.6441, -73.7828],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "jfk-terminal-4",
                        "label": "Terminal 4",
                        "aliases": ["Terminal 4", "T4", "Terminal 4 (General TSA)", "Terminal 4 (TSA Pre✓)", "Terminal 4 (Visitor Customs)"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Terminal 4 wait-time checkpoint from the official terminal page.",
                    }
                ],
            },
            {
                "id": "terminal-5",
                "marker_code": "T5",
                "marker_label": "Terminal 5",
                "marker_offset": [-20, -8],
                "label": "Terminal 5",
                "summary": "Terminal 5 departures",
                # Terminal 5 departures building, east of the TWA Hotel complex.
                "anchor": [40.6456, -73.7779],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "jfk-terminal-5",
                        "label": "Terminal 5",
                        "aliases": ["Terminal 5", "T5", "Terminal 5 (General TSA)", "Terminal 5 (TSA Pre✓)"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Terminal 5 wait-time checkpoint from the official terminal page.",
                    }
                ],
            },
            {
                "id": "terminal-7",
                "marker_code": "T7",
                "marker_label": "Terminal 7",
                "marker_offset": [18, 8],
                "label": "Terminal 7",
                "summary": "Terminal 7 departures",
                # Terminal 7 departures area, north of Terminal 4.
                "anchor": [40.6485, -73.7832],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "jfk-terminal-7",
                        "label": "Terminal 7",
                        "aliases": ["Terminal 7", "T7", "Terminal 7 (General TSA)", "Terminal 7 (TSA Pre✓)"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Terminal 7 wait-time checkpoint from the official terminal page.",
                    }
                ],
            },
            {
                "id": "terminal-8",
                "marker_code": "T8",
                "marker_label": "Terminal 8",
                "marker_offset": [0, -16],
                "label": "Terminal 8",
                "summary": "Terminal 8 departures",
                # Terminal 8 departures building, west/northwest of Terminal 1.
                "anchor": [40.6471, -73.7900],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "jfk-terminal-8",
                        "label": "Terminal 8",
                        "aliases": ["Terminal 8", "T8", "Terminal 8 (General TSA)", "Terminal 8 (TSA Pre✓)"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Terminal 8 wait-time checkpoint from the official terminal page.",
                    }
                ],
            },
        ],
    },
    "MCO": {
        "decision_mode": "terminal_checkpoint",
        "has_published_hours": False,
        "all_checkpoints_reach_all_gates": False,
        "routing_note": (
            "MCO publishes separate east, west, and south security checkpoints. Match the checkpoint to your departure side rather than using a single airport-wide line."
        ),
        "map": {
            "center": [28.4312, -81.3081],
            "bounds": [[28.4232, -81.3190], [28.4398, -81.2962]],
            "overview_zoom": 14.0,
            "detail_zoom": 15.7,
            "location_accuracy": "checkpoint_area_overview",
            "tile_url": USGS_IMAGERY_URL,
            "tile_attribution": USGS_IMAGERY_ATTRIBUTION,
        },
        "source": {
            "label": "Official MCO security wait times",
            "url": "https://flymco.com/security/",
            "verified_on": "2026-07-14",
        },
        "terminals": [
            {
                "id": "west",
                "marker_code": "WEST",
                "marker_label": "West",
                "marker_offset": [-18, 8],
                "label": "West Security",
                "summary": "West security checkpoint",
                "anchor": [28.4328, -81.3104],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "mco-west",
                        "label": "West Security",
                        "aliases": ["West Standard", "West PreCheck", "West Security"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "West checkpoint from the official MCO wait-time feed.",
                    }
                ],
            },
            {
                "id": "south",
                "marker_code": "SOUTH",
                "marker_label": "South",
                "marker_offset": [0, -18],
                "label": "South Security",
                "summary": "South security checkpoint",
                "anchor": [28.4288, -81.3078],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "mco-south",
                        "label": "South Security",
                        "aliases": ["South Standard", "South PreCheck", "South Security"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "South checkpoint from the official MCO wait-time feed.",
                    }
                ],
            },
            {
                "id": "east",
                "marker_code": "EAST",
                "marker_label": "East",
                "marker_offset": [18, 8],
                "label": "East Security",
                "summary": "East security checkpoint",
                "anchor": [28.4316, -81.3028],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "mco-east",
                        "label": "East Security",
                        "aliases": ["East Standard", "East PreCheck", "East Security"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "East checkpoint from the official MCO wait-time feed.",
                    }
                ],
            },
        ],
    },
    "SEA": {
        "decision_mode": "terminal_checkpoint",
        "has_published_hours": True,
        "all_checkpoints_reach_all_gates": True,
        "routing_note": (
            "SEA states that all gates are accessible from any security checkpoint. "
            "Choose the checkpoint that matches your lane type and published hours."
        ),
        "map": {
            "center": [47.4502, -122.3088],
            "bounds": [[47.4408, -122.3248], [47.4592, -122.2922]],
            "overview_zoom": 13.75,
            "detail_zoom": 15.25,
            "location_accuracy": "checkpoint_area_overview",
            "tile_url": USGS_IMAGERY_URL,
            "tile_attribution": USGS_IMAGERY_ATTRIBUTION,
        },
        "source": {
            "label": "Official SEA Security Dashboard",
            "url": "https://www.portseattle.org/Security",
            "verified_on": "2026-07-13",
        },
        "terminals": [
            {
                "id": "checkpoint-1",
                "marker_code": "C1",
                "marker_label": "Checkpoint 1",
                "marker_offset": [-16, 8],
                "label": "Checkpoint 1",
                "summary": "A & S gates",
                # South end of the Main Terminal's Gina Marie Lindsey Arrivals Hall.
                "anchor": [47.4399, -122.3008],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "sea-checkpoint-1",
                        "label": "Checkpoint 1",
                        "aliases": ["Checkpoint 1"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "4:00 a.m. - 8:00 p.m.",
                        "note": "Closest to A and S gates; general screening, TSA PreCheck, and CLEAR options.",
                    }
                ],
            },
            {
                "id": "checkpoint-2",
                "marker_code": "C2",
                "marker_label": "Checkpoint 2",
                "marker_offset": [16, 8],
                "label": "Checkpoint 2",
                "summary": "A & S gates",
                # South ticketing area, immediately north of Checkpoint 1.
                "anchor": [47.4413, -122.3010],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "sea-checkpoint-2",
                        "label": "Checkpoint 2",
                        "aliases": ["Checkpoint 2"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "4:00 a.m. - 4:00 p.m.",
                        "note": "Closest to A and S gates; general screening plus SEA Spot Saver during published hours.",
                    }
                ],
            },
            {
                "id": "checkpoint-3",
                "marker_code": "C3",
                "marker_label": "Checkpoint 3",
                "marker_offset": [0, -18],
                "label": "Checkpoint 3",
                "summary": "A & S gates",
                # South-central Main Terminal ticketing area.
                "anchor": [47.4424, -122.3011],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "sea-checkpoint-3",
                        "label": "Checkpoint 3",
                        "aliases": ["Checkpoint 3"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "4:00 a.m. - 11:30 p.m.",
                        "note": "Central option with general screening, TSA PreCheck, Touchless ID, and premium-lane options.",
                    }
                ],
            },
            {
                "id": "checkpoint-4",
                "marker_code": "C4",
                "marker_label": "Checkpoint 4",
                "marker_offset": [0, 0],
                "label": "Checkpoint 4",
                "summary": "Central Terminal",
                # Central Terminal checkpoint area.
                "anchor": [47.4435, -122.3013],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "sea-checkpoint-4",
                        "label": "Checkpoint 4",
                        "aliases": ["Checkpoint 4"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "Open 24 hours",
                        "note": "Closest to the Central Terminal plus B and C gates; general, premium, family, SEA Spot Saver, and CLEAR options.",
                    }
                ],
            },
            {
                "id": "checkpoint-5",
                "marker_code": "C5",
                "marker_label": "Checkpoint 5",
                "marker_offset": [-16, -8],
                "label": "Checkpoint 5",
                "summary": "C, D, and N gates",
                # North-central Main Terminal ticketing area.
                "anchor": [47.4446, -122.3014],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "sea-checkpoint-5",
                        "label": "Checkpoint 5",
                        "aliases": ["Checkpoint 5"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "4:00 a.m. - 8:00 p.m.",
                        "note": "Closest to C, D, and N gates; TSA PreCheck-focused.",
                    }
                ],
            },
            {
                "id": "checkpoint-6",
                "marker_code": "C6",
                "marker_label": "Checkpoint 6",
                "marker_offset": [16, -8],
                "label": "Checkpoint 6",
                "summary": "C, D, and N gates",
                # North end of the Main Terminal checkpoint sequence.
                "anchor": [47.4456, -122.3017],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "sea-checkpoint-6",
                        "label": "Checkpoint 6",
                        "aliases": ["Checkpoint 6"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "4:00 a.m. - 10:00 p.m.",
                        "note": "Closest to C, D, and N gates; general, premium, PreCheck, Touchless ID, and CLEAR options.",
                    }
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
    "DEN": {
        "decision_mode": "terminal_checkpoint",
        "has_published_hours": True,
        "all_checkpoints_reach_all_gates": True,
        "lane_types": ["STANDARD", "PRECHECK", "CLEAR"],
        "routing_note": (
            "DEN uses East and West Security on Level 6. Both checkpoints feed the same concourse train, so compare the current lane with the checkpoint closest to your arrival side."
        ),
        "map": {
            # Keep the Jeppesen Terminal in the overview: East and West
            # Security are on Level 6 there, south of Concourse A/B/C.
            "center": [39.8535, -104.6737],
            "bounds": [[39.8472, -104.6804], [39.8615, -104.6660]],
            "overview_zoom": 14.25,
            "detail_zoom": 16.25,
            "location_accuracy": "checkpoint_area_overview",
            "tile_url": USGS_IMAGERY_URL,
            "tile_attribution": USGS_IMAGERY_ATTRIBUTION,
        },
        "source": {
            "label": "Official DEN security wait times",
            "url": "https://www.flydenver.com/security/",
            "verified_on": "2026-07-14",
        },
        "terminals": [
            {
                "id": "west",
                "marker_code": "WEST",
                "marker_label": "West Security",
                "label": "West Security",
                "summary": "West checkpoint on Level 6",
                # Northwest end of Jeppesen Terminal, not a gate concourse.
                "anchor": [39.8512, -104.67455],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "den-west",
                        "label": "West Security",
                        "aliases": [
                            "West Security",
                            "West Security Checkpoint",
                            "West Security (Level 6)",
                        ],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "3:00 a.m. - 1:00 a.m.",
                        "note": "West Security checkpoint on Level 6 of Jeppesen Terminal.",
                    }
                ],
            },
            {
                "id": "east",
                "marker_code": "EAST",
                "marker_label": "East Security",
                "label": "East Security",
                "summary": "East checkpoint on Level 6",
                # Northeast end of Jeppesen Terminal, directly opposite West.
                "anchor": [39.8512, -104.67305],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "den-east",
                        "label": "East Security",
                        "aliases": [
                            "East Security",
                            "East Security Checkpoint",
                            "East Security (Level 6)",
                        ],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "3:00 a.m. - 1:00 a.m.",
                        "note": "East Security checkpoint on Level 6 of Jeppesen Terminal.",
                    }
                ],
            },
        ],
    },
    "IAD": {
        "decision_mode": "terminal_checkpoint",
        "has_published_hours": True,
        "all_checkpoints_reach_all_gates": True,
        "lane_types": ["STANDARD", "PRECHECK"],
        "routing_note": (
            "IAD keeps the security choice in the main terminal. East, West, and TSA PreCheck are published separately, so choose the checkpoint that matches the lane you want to use."
        ),
        "map": {
            "center": [38.9531, -77.4565],
            "bounds": [[38.9480, -77.4625], [38.9586, -77.4415]],
            "overview_zoom": 14.25,
            "detail_zoom": 16.25,
            "location_accuracy": "checkpoint_area_overview",
            "tile_url": USGS_IMAGERY_URL,
            "tile_attribution": USGS_IMAGERY_ATTRIBUTION,
        },
        "source": {
            "label": "Official IAD security information",
            "url": "https://www.flydulles.com/travel-information/security-information",
            "verified_on": "2026-07-14",
        },
        "terminals": [
            {
                "id": "east",
                "marker_code": "EAST",
                "marker_label": "East Checkpoint",
                "label": "East Checkpoint",
                "summary": "East checkpoint",
                # East end of the Dulles Main Terminal security hall.
                "anchor": [38.9529, -77.4463],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "iad-east",
                        "label": "East Checkpoint",
                        "aliases": [
                            "East Checkpoint",
                            "East Security Checkpoint",
                            "Terminal East",
                        ],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "Open 24 hours",
                        "note": "East checkpoint on the IAD main terminal side.",
                    }
                ],
            },
            {
                "id": "west",
                "marker_code": "WEST",
                "marker_label": "West Checkpoint",
                "label": "West Checkpoint",
                "summary": "West checkpoint",
                # West end of the Dulles Main Terminal security hall.
                "anchor": [38.9529, -77.4493],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "iad-west",
                        "label": "West Checkpoint",
                        "aliases": [
                            "West Checkpoint",
                            "West Security Checkpoint",
                            "Terminal West",
                        ],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "4:45 a.m. - 9:00 p.m.",
                        "note": "West checkpoint on the IAD main terminal side.",
                    }
                ],
            },
            {
                "id": "precheck",
                "marker_code": "PRE",
                "marker_label": "TSA PreCheck",
                "label": "TSA PreCheck",
                "summary": "TSA PreCheck lane",
                "anchor": [38.9529, -77.4480],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "iad-precheck",
                        "label": "TSA PreCheck",
                        "aliases": [
                            "TSA PreCheck",
                            "TSA Pre✓",
                            "PreCheck",
                        ],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "4:00 a.m. - 9:00 p.m.",
                        "note": "Published TSA PreCheck hours on the IAD security page.",
                    }
                ],
            },
        ],
    },
    "IAH": {
        "decision_mode": "terminal_checkpoint",
        "has_published_hours": True,
        "all_checkpoints_reach_all_gates": False,
        "lane_types": ["STANDARD", "PRECHECK", "CLEAR"],
        "routing_note": (
            "IAH publishes checkpoint hours by terminal. A and C split into north and south security areas, so use the terminal on your boarding pass before comparing lanes."
        ),
        "map": {
            "center": [29.9902, -95.3368],
            "bounds": [[29.9831, -95.3492], [29.9978, -95.3245]],
            "overview_zoom": 13.8,
            "detail_zoom": 15.8,
            "location_accuracy": "terminal_building_overview",
            "tile_url": USGS_IMAGERY_URL,
            "tile_attribution": USGS_IMAGERY_ATTRIBUTION,
        },
        "source": {
            "label": "Official IAH security page",
            "url": "https://www.fly2houston.com/iah/security",
            "verified_on": "2026-07-14",
        },
        "terminals": [
            {
                "id": "terminal-a",
                "marker_code": "A",
                "marker_label": "Terminal A",
                "label": "Terminal A",
                "summary": "A North and A South checkpoints",
                # Terminal A's security area, west of Terminal B.
                "anchor": [29.9856, -95.3440],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [
                    {
                        "id": "iah-terminal-a-north",
                        "label": "Terminal A North",
                        "aliases": [
                            "Terminal A North",
                            "Terminal A North (Standard)",
                            "Terminal A North (TSA PreCheck)",
                            "Terminal A North (CLEAR)",
                        ],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "3:30 a.m. - 7:30 p.m.",
                        "note": "Published hours for Terminal A North on the official IAH security page.",
                    },
                    {
                        "id": "iah-terminal-a-south",
                        "label": "Terminal A South",
                        "aliases": [
                            "Terminal A South",
                            "Terminal A South (Standard)",
                            "Terminal A South (TSA PreCheck)",
                        ],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "3:30 a.m. - 12:00 a.m.",
                        "note": "Published hours for Terminal A South on the official IAH security page.",
                    },
                ],
            },
            {
                "id": "terminal-b",
                "marker_code": "B",
                "marker_label": "Terminal B",
                "label": "Terminal B",
                "summary": "Terminal B checkpoint",
                "anchor": [29.9891, -95.3466],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [
                    {
                        "id": "iah-terminal-b",
                        "label": "Terminal B",
                        "aliases": ["Terminal B", "Terminal B (Standard)"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "Closed",
                        "note": "Published status on the official IAH security page.",
                    }
                ],
            },
            {
                "id": "terminal-c",
                "marker_code": "C",
                "marker_label": "Terminal C",
                "label": "Terminal C",
                "summary": "C North and C South checkpoints",
                # Terminal C's central terminal building.
                "anchor": [29.9869, -95.3394],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [
                    {
                        "id": "iah-terminal-c-north",
                        "label": "Terminal C North",
                        "aliases": [
                            "Terminal C North",
                            "Terminal C North (Standard)",
                            "Terminal C North (TSA PreCheck)",
                            "Terminal C North (CLEAR)",
                        ],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "4:00 a.m. - 10:00 p.m.",
                        "note": "Published hours for Terminal C North on the official IAH security page.",
                    },
                    {
                        "id": "iah-terminal-c-south",
                        "label": "Terminal C South",
                        "aliases": [
                            "Terminal C South",
                            "Terminal C South (Standard)",
                            "Terminal C South (TSA PreCheck)",
                        ],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "4:00 a.m. - 7:30 p.m.",
                        "note": "Published hours for Terminal C South on the official IAH security page.",
                    },
                ],
            },
            {
                "id": "terminal-d",
                "marker_code": "D",
                "marker_label": "Terminal D",
                "label": "Terminal D",
                "summary": "Terminal D checkpoint",
                # Terminal D / Mickey Leland International Terminal west pier.
                "anchor": [29.9890, -95.3386],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [
                    {
                        "id": "iah-terminal-d",
                        "label": "Terminal D",
                        "aliases": ["Terminal D", "Terminal D (Standard)"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "4:00 a.m. - 12:30 a.m.",
                        "note": "Published hours for Terminal D on the official IAH security page.",
                    }
                ],
            },
            {
                "id": "terminal-e",
                "marker_code": "E",
                "marker_label": "Terminal E",
                "label": "Terminal E",
                "summary": "Terminal E checkpoint",
                # Terminal E building, east of the D/E connector.
                "anchor": [29.9852, -95.3339],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [
                    {
                        "id": "iah-terminal-e",
                        "label": "Terminal E",
                        "aliases": ["Terminal E", "Terminal E (Standard)", "Terminal E (CLEAR)"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "4:00 a.m. - 12:00 a.m.",
                        "note": "Published hours for Terminal E on the official IAH security page.",
                    }
                ],
            },
        ],
    },
    "BWI": {
        "decision_mode": "terminal_checkpoint",
        "has_published_hours": True,
        "all_checkpoints_reach_all_gates": False,
        "lane_types": ["STANDARD", "PRIORITY", "PRECHECK", "CLEAR"],
        "routing_note": (
            "BWI publishes live waits for four checkpoint areas on the homepage. "
            "Choose the checkpoint and lane that match your concourse before you leave."
        ),
        "map": {
            "center": [39.1747196, -76.6707551],
            "bounds": [[39.1703, -76.6769], [39.1809, -76.6620]],
            "overview_zoom": 14.2,
            "detail_zoom": 16.2,
            "location_accuracy": "checkpoint_area_overview",
            "tile_url": USGS_IMAGERY_URL,
            "tile_attribution": USGS_IMAGERY_ATTRIBUTION,
        },
        "source": {
            "label": "Official BWI homepage security widget",
            "url": "https://bwiairport.com/",
            "verified_on": "2026-07-14",
        },
        "terminals": [
            {
                "id": "a",
                "marker_code": "A",
                "label": "Checkpoint A",
                "summary": "Checkpoint A",
                # West side of the Main Terminal, by Concourse A.
                "anchor": [39.1792, -76.6724],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "bwi-a",
                        "label": "Checkpoint A",
                        "aliases": ["Checkpoint A"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "4:00 a.m. - 8:00 p.m.",
                        "note": "Live BWI homepage wait-time checkpoint for the A side.",
                    }
                ],
            },
            {
                "id": "b",
                "marker_code": "B",
                "label": "Checkpoint B",
                "summary": "Checkpoint B",
                # Main Terminal checkpoint area between Concourses A and B.
                "anchor": [39.1791, -76.6706],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "bwi-b",
                        "label": "Checkpoint B",
                        "aliases": ["Checkpoint B"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "Open 24 hours",
                        "note": "Live BWI homepage wait-time checkpoint for the central concourses.",
                    }
                ],
            },
            {
                "id": "c",
                "marker_code": "C",
                "label": "Checkpoint C",
                "summary": "Checkpoint C",
                # Central Main Terminal checkpoint area by Concourse C.
                "anchor": [39.1789, -76.6685],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "bwi-c",
                        "label": "Checkpoint C",
                        "aliases": ["Checkpoint C"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "4:00 a.m. - 8:00 p.m.",
                        "note": "Live BWI homepage wait-time checkpoint for the C side.",
                    }
                ],
            },
            {
                "id": "de",
                "marker_code": "D/E",
                "label": "Checkpoint D/E",
                "summary": "Checkpoint D/E",
                # East side of the Main Terminal, serving Concourses D and E.
                "anchor": [39.1791, -76.6669],
                "location_accuracy": "checkpoint_area_anchor",
                "checkpoints": [
                    {
                        "id": "bwi-de",
                        "label": "Checkpoint D/E",
                        "aliases": ["Checkpoint D/E", "Checkpoint D/E*"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "Open 24 hours",
                        "note": "Live BWI homepage wait-time checkpoint for Concourses D and E.",
                    }
                ],
            },
        ],
    },
    "DTW": {
        "decision_mode": "terminal_checkpoint",
        "has_published_hours": False,
        "routing_note": (
            "DTW publishes separate live waits for McNamara and Evans. Choose "
            "the terminal that matches your airline before you leave."
        ),
        "map": {
            "center": [42.2170, -83.3509],
            "bounds": [[42.2046, -83.3628], [42.2290, -83.3432]],
            "overview_zoom": 13.8,
            "detail_zoom": 16,
            "location_accuracy": "terminal_building_overview",
            "tile_url": USGS_IMAGERY_URL,
            "tile_attribution": USGS_IMAGERY_ATTRIBUTION,
        },
        "source": {
            "label": "Official DTW security wait times",
            "url": "https://www.metroairport.com/",
            "verified_on": "2026-07-14",
        },
        "terminals": [
            {
                "id": "mcnamara",
                "marker_code": "MCN",
                "marker_label": "McNamara",
                "label": "McNamara Terminal",
                "summary": "McNamara terminal wait time",
                "anchor": [42.2087129, -83.3553797],
                "location_accuracy": "terminal_curb_anchor",
                "checkpoints": [
                    {
                        "id": "dtw-mcnamara",
                        "label": "McNamara Terminal",
                        "aliases": ["McNamara Terminal", "Metro Airport McNamara Terminal"],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "McNamara terminal wait time from the public DTW widget.",
                    }
                ],
            },
            {
                "id": "evans",
                "marker_code": "EVN",
                "marker_label": "Evans",
                "label": "Evans Terminal",
                "summary": "Evans terminal wait time",
                "anchor": [42.2262159, -83.3464256],
                "location_accuracy": "terminal_curb_anchor",
                "checkpoints": [
                    {
                        "id": "dtw-evans",
                        "label": "Evans Terminal",
                        "aliases": [
                            "Evans Terminal",
                            "North Terminal",
                            "Metro Airport North Terminal",
                        ],
                        "primary_for": [],
                        "alternate_for": [],
                        "hours": "",
                        "note": "Evans terminal wait time from the public DTW widget.",
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
    "DFW": {
        "decision_mode": "terminal_checkpoint",
        "has_published_hours": False,
        "routing_note": (
            "Choose Terminal A, B, C, D, or E from your boarding pass. DFW "
            "publishes several checkpoint readings per terminal; compare the "
            "checkpoint name and lane before heading to security."
        ),
        "map": {
            "center": [32.8980, -97.0402],
            "bounds": [[32.8870, -97.0470], [32.9080, -97.0335]],
            "overview_zoom": 14.75,
            "detail_zoom": 16.5,
            "location_accuracy": "terminal_building_overview",
            "tile_url": USGS_IMAGERY_URL,
            "tile_attribution": USGS_IMAGERY_ATTRIBUTION,
        },
        "source": {
            "label": "Official DFW security information",
            "url": "https://www.dfwairport.com/security/",
            "verified_on": "2026-07-13",
        },
        "terminals": [
            {
                "id": "terminal-a",
                "marker_code": "A",
                "marker_label": "Terminal A",
                "marker_offset": [10, -10],
                "label": "Terminal A",
                "summary": "Checkpoints A12, A21, and A35",
                "anchor": [32.9045373, -97.0371022],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [
                    {
                        "id": "dfw-a12",
                        "label": "A12",
                        "aliases": ["A12", "A12 (General)", "A12 (Priority)"],
                        "primary_for": [], "alternate_for": [], "hours": "",
                        "note": "Published checkpoint reading for Terminal A near A12.",
                    },
                    {
                        "id": "dfw-a21",
                        "label": "A21",
                        "aliases": ["A21", "A21 (General)", "A21 (Priority)", "A21 (TSA Pre)"],
                        "primary_for": [], "alternate_for": [], "hours": "",
                        "note": "Published Standard, Priority, and PreCheck readings near A21.",
                    },
                    {
                        "id": "dfw-a35",
                        "label": "A35",
                        "aliases": ["A35", "A35 (General)", "A35 (Priority)"],
                        "primary_for": [], "alternate_for": [], "hours": "",
                        "note": "Published checkpoint reading for Terminal A near A35.",
                    },
                ],
            },
            {
                "id": "terminal-b",
                "marker_code": "B",
                "marker_label": "Terminal B",
                "marker_offset": [-10, -10],
                "label": "Terminal B",
                "summary": "Checkpoints B9 and B30",
                "anchor": [32.9047891, -97.0437526],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [
                    {
                        "id": "dfw-b9", "label": "B9",
                        "aliases": ["B9", "B9 (General)", "B9 (Priority)", "B9 (TSA Pre)"],
                        "primary_for": [], "alternate_for": [], "hours": "",
                        "note": "Published Standard, Priority, and PreCheck readings near B9.",
                    },
                    {
                        "id": "dfw-b30", "label": "B30",
                        "aliases": ["B30", "B30 (General)", "B30 (Priority)", "B30 (TSA Pre)"],
                        "primary_for": [], "alternate_for": [], "hours": "",
                        "note": "Published Standard, Priority, and PreCheck readings near B30.",
                    },
                ],
            },
            {
                "id": "terminal-c",
                "marker_code": "C",
                "marker_label": "Terminal C",
                "marker_offset": [10, 8],
                "label": "Terminal C",
                "summary": "Checkpoints C10, C11, and C20",
                "anchor": [32.8977107, -97.0365668],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [
                    {
                        "id": "dfw-c10", "label": "C10",
                        "aliases": ["C10", "C10 (General)", "C10 (Priority)", "C10 (TSA Pre)"],
                        "primary_for": [], "alternate_for": [], "hours": "",
                        "note": "Published Standard, Priority, and PreCheck readings near C10.",
                    },
                    {
                        "id": "dfw-c11", "label": "C11",
                        "aliases": ["C11", "C11 (General)", "C11 (Priority)", "C11 (TSA Pre)"],
                        "primary_for": [], "alternate_for": [], "hours": "",
                        "note": "Published Standard, Priority, and PreCheck readings near C11.",
                    },
                    {
                        "id": "dfw-c20", "label": "C20",
                        "aliases": ["C20", "C20 (General)", "C20 (TSA Pre)"],
                        "primary_for": [], "alternate_for": [], "hours": "",
                        "note": "Published Standard and PreCheck readings near C20.",
                    },
                ],
            },
            {
                "id": "terminal-d",
                "marker_code": "D",
                "marker_label": "Terminal D",
                "marker_offset": [-10, 8],
                "label": "Terminal D",
                "summary": "Checkpoints D18, D22, and D30",
                "anchor": [32.8978960, -97.0435516],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [
                    {
                        "id": "dfw-d18", "label": "D18",
                        "aliases": ["D18", "D18 (General)", "D18 (TSA Pre)"],
                        "primary_for": [], "alternate_for": [], "hours": "",
                        "note": "Published Standard and PreCheck readings near D18.",
                    },
                    {
                        "id": "dfw-d22", "label": "D22",
                        "aliases": ["D22", "D22 (General)"],
                        "primary_for": [], "alternate_for": [], "hours": "",
                        "note": "Published checkpoint reading near D22.",
                    },
                    {
                        "id": "dfw-d30", "label": "D30",
                        "aliases": ["D30", "D30 (General)", "D30 (TSA Pre)"],
                        "primary_for": [], "alternate_for": [], "hours": "",
                        "note": "Published Standard and PreCheck readings near D30.",
                    },
                ],
            },
            {
                "id": "terminal-e",
                "marker_code": "E",
                "marker_label": "Terminal E",
                "label": "Terminal E",
                "summary": "Checkpoints E8, E16, E18, and E33",
                "anchor": [32.8897745, -97.0363673],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [
                    {
                        "id": "dfw-e8", "label": "E8",
                        "aliases": ["E8", "E8 (General)", "E8 (Priority)", "E8 (TSA Pre)"],
                        "primary_for": [], "alternate_for": [], "hours": "",
                        "note": "Published Standard, Priority, and PreCheck readings near E8.",
                    },
                    {
                        "id": "dfw-e16", "label": "E16",
                        "aliases": ["E16", "E16 (TSA Pre)"],
                        "primary_for": [], "alternate_for": [], "hours": "",
                        "note": "Published PreCheck reading near E16.",
                    },
                    {
                        "id": "dfw-e18", "label": "E18",
                        "aliases": ["E18", "E18 (General)", "E18 (TSA Pre)"],
                        "primary_for": [], "alternate_for": [], "hours": "",
                        "note": "Published Standard and PreCheck readings near E18.",
                    },
                    {
                        "id": "dfw-e33", "label": "E33",
                        "aliases": ["E33", "E33 (General)", "E33 (Priority)"],
                        "primary_for": [], "alternate_for": [], "hours": "",
                        "note": "Published checkpoint reading near E33.",
                    },
                ],
            },
        ],
    },
    "PHL": {
        "decision_mode": "terminal_checkpoint",
        "has_published_hours": False,
        "routing_note": (
            "Choose the checkpoint area on your boarding pass. All PHL terminals "
            "are connected after screening, but checkpoint availability changes; "
            "verify the current status with PHL before heading to a different area."
        ),
        "map": {
            "center": [39.8762, -75.2446],
            "bounds": [[39.8715, -75.2540], [39.8820, -75.2350]],
            "overview_zoom": 15.25,
            "detail_zoom": 17,
            "location_accuracy": "terminal_building_overview",
            "tile_url": USGS_IMAGERY_URL,
            "tile_attribution": USGS_IMAGERY_ATTRIBUTION,
        },
        "source": {
            "label": "Official PHL checkpoint information",
            "url": "https://www.phl.org/flights/security-information/checkpoint-hours",
            "verified_on": "2026-07-13",
        },
        "terminals": [
            {
                "id": "a-west", "marker_code": "A-W", "marker_label": "A-West",
                "marker_offset": [-10, 10], "label": "A-West",
                "summary": "A-West checkpoint area", "anchor": [39.8731426, -75.2519383],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [{
                    "id": "phl-a-west", "label": "A-West",
                    "aliases": ["A-West", "A-West General"],
                    "primary_for": [], "alternate_for": [], "hours": "",
                    "note": "Published checkpoint reading for the A-West area; verify current availability with PHL.",
                }],
            },
            {
                "id": "a-east", "marker_code": "A-E", "marker_label": "A-East",
                "marker_offset": [8, -10], "label": "A-East",
                "summary": "A-East Standard and PreCheck", "anchor": [39.8738227, -75.2472237],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [{
                    "id": "phl-a-east", "label": "A-East",
                    "aliases": ["A-East", "A-East General", "A-East TSA PreCheck"],
                    "primary_for": [], "alternate_for": [], "hours": "",
                    "note": "Published Standard and PreCheck readings for the A-East area.",
                }],
            },
            {
                "id": "b", "marker_code": "B", "marker_label": "Terminal B",
                "marker_offset": [-8, 10], "label": "Terminal B",
                "summary": "Terminal B checkpoint", "anchor": [39.8744920, -75.2437474],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [{
                    "id": "phl-b", "label": "B",
                    "aliases": ["B", "B General"],
                    "primary_for": [], "alternate_for": [], "hours": "",
                    "note": "Published checkpoint reading for Terminal B.",
                }],
            },
            {
                "id": "c", "marker_code": "C", "marker_label": "Terminal C",
                "marker_offset": [8, -10], "label": "Terminal C",
                "summary": "PreCheck-only checkpoint", "anchor": [39.8749401, -75.2412406],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [{
                    "id": "phl-c", "label": "C",
                    "aliases": ["C", "C General"],
                    "primary_for": [], "alternate_for": [], "hours": "",
                    "note": "PHL currently identifies Terminal C as a PreCheck-only checkpoint.",
                }],
            },
            {
                "id": "d-e", "marker_code": "D/E", "marker_label": "D/E",
                "marker_offset": [-8, 8], "label": "D/E",
                "summary": "Shared D/E Standard and PreCheck", "anchor": [39.8779073, -75.2398912],
                "location_accuracy": "terminal_building_overview_anchor",
                "checkpoints": [{
                    "id": "phl-d-e", "label": "D/E",
                    "aliases": ["D/E", "D/E General", "D/E TSA PreCheck"],
                    "primary_for": [], "alternate_for": [], "hours": "",
                    "note": "Shared checkpoint readings for the Terminal D/E area.",
                }],
            },
            {
                "id": "f", "marker_code": "F", "marker_label": "Terminal F",
                "marker_offset": [8, -10], "label": "Terminal F",
                "summary": "Terminal F checkpoint", "anchor": [39.8807808, -75.2374961],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [{
                    "id": "phl-f", "label": "F",
                    "aliases": ["F", "F General"],
                    "primary_for": [], "alternate_for": [], "hours": "",
                    "note": "Published checkpoint reading for Terminal F; verify current availability with PHL.",
                }],
            },
        ],
    },
    "MIA": {
        "decision_mode": "terminal_checkpoint",
        "has_published_hours": True,
        "routing_note": (
            "Choose the North, Central, or South terminal complex from your boarding pass. "
            "MIA publishes ten numbered checkpoints plus DFIS, while the current live feed "
            "reports only checkpoint 2 in North Terminal and checkpoint 9 in South Terminal."
        ),
        "map": {
            "center": [25.7946, -80.2785],
            "bounds": [[25.7895, -80.2850], [25.8000, -80.2720]],
            "overview_zoom": 15,
            "detail_zoom": 17,
            "location_accuracy": "terminal_complex_overview",
            "tile_url": USGS_IMAGERY_URL,
            "tile_attribution": USGS_IMAGERY_ATTRIBUTION,
        },
        "source": {
            "label": "Official MIA airport security information",
            "url": "https://www.miami-airport.com/airport-security.asp",
            "verified_on": "2026-07-13",
        },
        "terminals": [
            {
                "id": "north-terminal-d",
                "marker_code": "N",
                "marker_label": "North / D",
                "marker_offset": [10, -12],
                "label": "North Terminal (D)",
                "summary": "Checkpoints 1-4 and DFIS",
                "anchor": [25.7972066, -80.2793055],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [
                    {
                        "id": "mia-1", "label": "Checkpoint 1",
                        "aliases": ["1", "1 General", "Checkpoint 1", "Checkpoint 1 General"],
                        "primary_for": [], "alternate_for": [], "hours": "4:00 a.m.-8:15 p.m.",
                        "note": "North Terminal D checkpoint with published PreCheck and American Airlines priority access.",
                        "published_only": True,
                    },
                    {
                        "id": "mia-2", "label": "Checkpoint 2",
                        "aliases": ["2", "2 General", "2 Priority", "Checkpoint 2", "Checkpoint 2 General", "Checkpoint 2 Priority"],
                        "primary_for": [], "alternate_for": [], "hours": "3:30 a.m.-11:45 p.m.",
                        "note": "North Terminal D checkpoint represented in the current MIA live feed.",
                    },
                    {
                        "id": "mia-3", "label": "Checkpoint 3",
                        "aliases": ["3", "3 General", "Checkpoint 3", "Checkpoint 3 General"],
                        "primary_for": [], "alternate_for": [], "hours": "4:00 a.m.-9:45 p.m.",
                        "note": "North Terminal D checkpoint with published American Airlines priority access.",
                        "published_only": True,
                    },
                    {
                        "id": "mia-4", "label": "Checkpoint 4",
                        "aliases": ["4", "4 General", "Checkpoint 4", "Checkpoint 4 General"],
                        "primary_for": [], "alternate_for": [], "hours": "4:00 a.m.-8:15 p.m.",
                        "note": "Published North Terminal D checkpoint without a current separate live row.",
                        "published_only": True,
                    },
                    {
                        "id": "mia-dfis", "label": "DFIS checkpoint",
                        "aliases": ["DFIS", "DFIS General", "Checkpoint DFIS"],
                        "primary_for": [], "alternate_for": [], "hours": "5:15 a.m.-9:30 p.m.",
                        "note": "Published North Terminal DFIS checkpoint without a current separate live row.",
                        "published_only": True,
                    },
                ],
            },
            {
                "id": "central-terminal",
                "marker_code": "C",
                "marker_label": "Central / E-F-G",
                "marker_offset": [-12, 6],
                "label": "Central Terminal (E/F/G)",
                "summary": "Checkpoints 5, 6, and 7",
                "anchor": [25.7935915, -80.2795948],
                "location_accuracy": "terminal_complex_overview_anchor",
                "checkpoints": [
                    {
                        "id": "mia-5", "label": "Checkpoint 5",
                        "aliases": ["5", "5 General", "Checkpoint 5", "Checkpoint 5 General"],
                        "primary_for": [], "alternate_for": [], "hours": "4:00 a.m.-10:45 p.m.",
                        "note": "Published Central Terminal checkpoint with PreCheck access.",
                        "published_only": True,
                    },
                    {
                        "id": "mia-6", "label": "Checkpoint 6",
                        "aliases": ["6", "6 General", "Checkpoint 6", "Checkpoint 6 General"],
                        "primary_for": [], "alternate_for": [], "hours": "3:30 a.m.-10:45 p.m.",
                        "note": "Published Central Terminal checkpoint with PreCheck access.",
                        "published_only": True,
                    },
                    {
                        "id": "mia-7", "label": "Checkpoint 7",
                        "aliases": ["7", "7 General", "Checkpoint 7", "Checkpoint 7 General"],
                        "primary_for": [], "alternate_for": [], "hours": "4:00 a.m.-8:15 p.m.",
                        "note": "Published Central Terminal checkpoint with PreCheck access.",
                        "published_only": True,
                    },
                ],
            },
            {
                "id": "south-terminal",
                "marker_code": "S",
                "marker_label": "South / H-J",
                "marker_offset": [12, 10],
                "label": "South Terminal (H/J)",
                "summary": "Checkpoints 8, 9, and 10",
                "anchor": [25.7919533, -80.2755418],
                "location_accuracy": "terminal_complex_overview_anchor",
                "checkpoints": [
                    {
                        "id": "mia-8", "label": "Checkpoint 8",
                        "aliases": ["8", "8 General", "Checkpoint 8", "Checkpoint 8 General"],
                        "primary_for": [], "alternate_for": [], "hours": "4:00 a.m.-8:15 p.m.",
                        "note": "Published South Terminal checkpoint with PreCheck access.",
                        "published_only": True,
                    },
                    {
                        "id": "mia-9", "label": "Checkpoint 9",
                        "aliases": ["9", "9 General", "9 Priority", "9 Clear", "Checkpoint 9", "Checkpoint 9 General", "Checkpoint 9 Priority", "Checkpoint 9 Clear"],
                        "primary_for": [], "alternate_for": [], "hours": "Open 24 hours",
                        "note": "South Terminal checkpoint represented in the current MIA live feed.",
                    },
                    {
                        "id": "mia-10", "label": "Checkpoint 10",
                        "aliases": ["10", "10 General", "Checkpoint 10", "Checkpoint 10 General"],
                        "primary_for": [], "alternate_for": [], "hours": "4:15 a.m.-7:15 p.m.",
                        "note": "Published South Terminal checkpoint with PreCheck access.",
                        "published_only": True,
                    },
                ],
            },
        ],
    },
    "LAX": {
        "decision_mode": "terminal_checkpoint",
        "has_published_hours": False,
        "routing_note": (
            "Choose the departure terminal on your boarding pass. The official LAX live page "
            "currently reports only Tom Bradley International Terminal; other terminal markers "
            "are routing context and do not imply a current wait or operating status."
        ),
        "map": {
            "center": [33.9434, -118.4042],
            "bounds": [[33.9388, -118.4120], [33.9490, -118.3960]],
            "overview_zoom": 15.25,
            "detail_zoom": 17,
            "location_accuracy": "terminal_building_overview",
            "tile_url": USGS_IMAGERY_URL,
            "tile_attribution": USGS_IMAGERY_ATTRIBUTION,
        },
        "source": {
            "label": "Official LAX security wait times",
            "url": "https://www.flylax.com/wait-times",
            "verified_on": "2026-07-13",
        },
        "terminals": [
            {
                "id": "terminal-1", "marker_code": "T1", "marker_label": "Terminal 1",
                "marker_offset": [25, -20], "label": "Terminal 1",
                "summary": "Terminal 1 passenger screening", "anchor": [33.9465762, -118.4008810],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [{
                    "id": "lax-terminal-1", "label": "Terminal 1 security",
                    "aliases": ["Terminal 1", "T1"], "primary_for": [], "alternate_for": [], "hours": "",
                    "note": "Official terminal routing marker; the current LAX feed has no separate Terminal 1 row.",
                    "published_only": True,
                }],
            },
            {
                "id": "terminal-2", "marker_code": "T2", "marker_label": "Terminal 2",
                "marker_offset": [20, -25], "label": "Terminal 2",
                "summary": "Terminal 2 passenger screening", "anchor": [33.9460769, -118.4040902],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [{
                    "id": "lax-terminal-2", "label": "Terminal 2 security",
                    "aliases": ["Terminal 2", "T2"], "primary_for": [], "alternate_for": [], "hours": "",
                    "note": "Official terminal routing marker; the current LAX feed has no separate Terminal 2 row.",
                    "published_only": True,
                }],
            },
            {
                "id": "terminal-3", "marker_code": "T3", "marker_label": "Terminal 3",
                "marker_offset": [-20, -5], "label": "Terminal 3",
                "summary": "Terminal 3 passenger screening", "anchor": [33.9458664, -118.4064624],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [{
                    "id": "lax-terminal-3", "label": "Terminal 3 security",
                    "aliases": ["Terminal 3", "T3"], "primary_for": [], "alternate_for": [], "hours": "",
                    "note": "Official terminal routing marker; the current LAX feed has no separate Terminal 3 row.",
                    "published_only": True,
                }],
            },
            {
                "id": "terminal-b", "marker_code": "TBIT", "marker_label": "Terminal B",
                "marker_offset": [-25, 0], "label": "Tom Bradley International Terminal (B)",
                "summary": "Current Standard and PreCheck feed", "anchor": [33.9428311, -118.4096740],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [{
                    "id": "lax-tbit", "label": "TBIT security",
                    "aliases": ["TBIT", "Terminal B", "Tom Bradley International Terminal"],
                    "primary_for": [], "alternate_for": [], "hours": "",
                    "note": "Tom Bradley International Terminal is the terminal currently represented in the official live feed.",
                }],
            },
            {
                "id": "terminal-4", "marker_code": "T4", "marker_label": "Terminal 4",
                "marker_offset": [-30, -10], "label": "Terminal 4",
                "summary": "Terminal 4 passenger screening", "anchor": [33.9417734, -118.4069898],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [{
                    "id": "lax-terminal-4", "label": "Terminal 4 security",
                    "aliases": ["Terminal 4", "T4"], "primary_for": [], "alternate_for": [], "hours": "",
                    "note": "Official terminal routing marker; the current LAX feed has no separate Terminal 4 row.",
                    "published_only": True,
                }],
            },
            {
                "id": "terminal-5", "marker_code": "T5", "marker_label": "Terminal 5",
                "marker_offset": [-5, 20], "label": "Terminal 5",
                "summary": "Terminal 5 passenger screening", "anchor": [33.9413955, -118.4047147],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [{
                    "id": "lax-terminal-5", "label": "Terminal 5 security",
                    "aliases": ["Terminal 5", "T5"], "primary_for": [], "alternate_for": [], "hours": "",
                    "note": "Official terminal routing marker; the current LAX feed has no separate Terminal 5 row.",
                    "published_only": True,
                }],
            },
            {
                "id": "terminal-6", "marker_code": "T6", "marker_label": "Terminal 6",
                "marker_offset": [15, -5], "label": "Terminal 6",
                "summary": "Terminal 6 passenger screening", "anchor": [33.9416089, -118.4018947],
                "location_accuracy": "terminal_building_centroid",
                "checkpoints": [{
                    "id": "lax-terminal-6", "label": "Terminal 6 security",
                    "aliases": ["Terminal 6", "T6"], "primary_for": [], "alternate_for": [], "hours": "",
                    "note": "Official terminal routing marker; the current LAX feed has no separate Terminal 6 row.",
                    "published_only": True,
                }],
            },
            {
                "id": "terminal-7-8", "marker_code": "T7/8", "marker_label": "Terminals 7/8",
                "marker_offset": [35, 15], "label": "Terminals 7/8",
                "summary": "Shared United terminal area", "anchor": [33.9418821, -118.3998094],
                "location_accuracy": "terminal_building_overview_anchor",
                "checkpoints": [{
                    "id": "lax-terminal-7-8", "label": "Terminal 7/8 security",
                    "aliases": ["Terminal 7", "Terminal 8", "T7", "T8"],
                    "primary_for": [], "alternate_for": [], "hours": "",
                    "note": "Terminal 7 screening serves the connected Terminal 7/8 area; the current feed has no separate row.",
                    "published_only": True,
                }],
            },
        ],
    },
}
