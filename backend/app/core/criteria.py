"""Explicit, versioned screening criteria (illustrative prototype rules)."""

CRITERIA_SET = {
    "name": "SENTRIX illustrative green criteria",
    "version": "0.1",
    "source": (
        "Simplified screening rules written for this prototype. They are NOT the official Pakistan "
        "Green Taxonomy or any SBP guideline. Replace them with the official criteria, and record "
        "their version, before any real use."
    ),
}

REQUIREMENTS = {
    "capacity_stated": {
        "label": "Installed capacity stated",
        "ask": "state the installed capacity (kW or MW) and the equipment specification",
    },
    "baseline_energy_data": {
        "label": "Baseline and current electricity records",
        "ask": "submit monthly electricity records for the baseline and reporting years",
    },
    "production_data": {
        "label": "Production records for normalisation",
        "ask": "submit production records for the same periods as the electricity records",
    },
    "claims_have_baseline": {
        "label": "Performance claims state a baseline",
        "ask": "state the baseline year for every quantified performance claim",
    },
    "treatment_capacity_stated": {
        "label": "Treatment capacity stated",
        "ask": "state the treatment capacity (for example m3 per day)",
    },
    "discharge_standard_stated": {
        "label": "Discharge standard referenced",
        "ask": "state the discharge standard the treated effluent must meet and provide test results",
    },
}

ACTIVITIES = [
    {
        "id": "RE-01",
        "name": "Renewable energy generation",
        "objective": "Climate change mitigation",
        "patterns": [r"\bsolar\b", r"\bpv\b", r"photovoltaic", r"wind (?:turbine|power|farm)", r"\bhydro"],
        "requirements": ["capacity_stated", "baseline_energy_data", "claims_have_baseline"],
    },
    {
        "id": "EE-01",
        "name": "Energy efficiency improvement",
        "objective": "Climate change mitigation",
        "patterns": [
            r"energy[- ]efficien", r"variable frequency", r"\bvfd", r"heat[- ]recovery",
            r"efficient (?:boiler|motor|drive|equipment)s?",
        ],
        "requirements": ["baseline_energy_data", "production_data", "claims_have_baseline"],
    },
    {
        "id": "WW-01",
        "name": "Wastewater and effluent treatment",
        "objective": "Pollution prevention and control",
        "patterns": [r"wastewater", r"effluent", r"water treatment"],
        "requirements": ["treatment_capacity_stated", "discharge_standard_stated"],
    },
]

EXCLUSION_PATTERNS = [r"\bcoal\b", r"diesel generator", r"fossil[- ]fuel", r"oil[- ]fired", r"thermal power plant"]