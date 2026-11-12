"""Qualitative climate screening reference (illustrative, NOT hazard data)."""

REFERENCE = {
    "name": "SENTRIX illustrative climate screening reference",
    "version": "0.1",
    "note": (
        "Qualitative notes based on general regional knowledge. It does not use flood maps, climate "
        "projections or asset-level data, so it cannot replace a site-specific climate risk assessment."
    ),
}

# (hazard, level, note); level is "elevated" or "moderate"
REGIONS = [
    {
        "name": "Karachi and the Sindh coast",
        "keys": ["karachi"],
        "hazards": [
            ("Extreme heat", "elevated", "Hot climate with recurrent heatwaves; affects workforce safety, cooling load and equipment."),
            ("Urban and monsoon flooding", "elevated", "Low-lying coastal city; drainage capacity is often exceeded in heavy rain."),
            ("Tropical cyclone and coastal storm", "moderate", "Arabian Sea cyclones occasionally threaten the coast."),
            ("Water stress", "moderate", "Reliance on piped and tanker water supply."),
        ],
    },
    {
        "name": "Punjab industrial belt",
        "keys": ["lahore", "faisalabad", "sialkot", "gujranwala", "multan", "sheikhupura", "punjab"],
        "hazards": [
            ("Extreme heat", "elevated", "Very hot summers; affects workforce safety and cooling demand."),
            ("Monsoon and riverine flooding", "moderate", "Highly site-specific; low-lying sites near rivers face higher exposure."),
            ("Winter smog and air quality", "moderate", "Seasonal smog can disrupt operations and logistics."),
            ("Water stress and groundwater depletion", "elevated", "Heavy reliance on groundwater in industrial areas."),
        ],
    },
    {
        "name": "Interior Sindh",
        "keys": ["hyderabad", "sukkur", "larkana", "sindh"],
        "hazards": [
            ("Extreme heat", "elevated", "Among the hottest regions of the country in summer."),
            ("Riverine and monsoon flooding", "elevated", "Low-lying Indus plain; flood exposure depends heavily on the exact site."),
            ("Water stress", "moderate", "Dependence on canal and groundwater supply."),
        ],
    },
    {
        "name": "Islamabad and northern Pakistan",
        "keys": ["islamabad", "rawalpindi", "peshawar", "khyber", "gilgit"],
        "hazards": [
            ("Extreme heat", "moderate", "Hot summers, milder than the south."),
            ("Flash floods and landslides", "moderate", "Depends on proximity to hill streams and slopes."),
        ],
    },
    {
        "name": "Balochistan",
        "keys": ["quetta", "balochistan"],
        "hazards": [
            ("Drought and water stress", "elevated", "Arid climate with limited water resources."),
            ("Extreme heat", "elevated", "Very hot summers in much of the province."),
            ("Flash floods", "moderate", "Episodic heavy rain on dry ground."),
        ],
    },
]

DEFAULT_REGION = {
    "name": "Pakistan (national-level screening)",
    "hazards": [
        ("Extreme heat", "elevated", "National-level assumption; the exact location was not recognised."),
        ("Flooding", "moderate", "Monsoon flooding affects many regions; exposure is site-specific."),
        ("Water stress", "moderate", "Water availability is a general national concern."),
    ],
}

# Transition exposure by sector keyword: energy- and export-intensive sectors face more cost and buyer pressure.
TRANSITION_RULES = [
    {
        "level": "elevated",
        "patterns": [r"cement", r"steel", r"ceramic", r"glass", r"brick", r"fertili", r"chemical",
                     r"paper", r"textile", r"dyeing", r"leather"],
        "why": "Energy-intensive and/or export-oriented sector: exposed to energy price changes, "
               "tightening efficiency expectations and buyer sustainability requirements.",
    },
    {
        "level": "moderate",
        "patterns": [r"packag", r"food", r"plastic", r"manufactur"],
        "why": "Moderately energy-dependent sector: exposed to energy costs and growing buyer sustainability "
               "requirements, with less direct carbon intensity.",
    },
]
DEFAULT_TRANSITION = {
    "level": "moderate",
    "why": "Sector not listed in the reference; a moderate default is assumed and should be reviewed.",
}