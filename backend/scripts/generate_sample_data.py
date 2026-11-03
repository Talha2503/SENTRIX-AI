"""Generate synthetic SENTRIX demo cases.

All companies, people and numbers are FICTIONAL and for demonstration only.
Run from the backend folder:  python scripts\\generate_sample_data.py
"""
import csv
import json
import textwrap
from pathlib import Path

import pymupdf

OUT_DIR = Path(__file__).resolve().parent.parent / "sample_data"
EMISSION_FACTOR = 0.45  # kg CO2e per kWh (illustrative synthetic factor, not an official value)

FY_MONTHS = [7, 8, 9, 10, 11, 12, 1, 2, 3, 4, 5, 6]  # fiscal year runs July to June
ELEC_WEIGHTS = [0.10, 0.10, 0.09, 0.085, 0.075, 0.07, 0.07, 0.07, 0.075, 0.08, 0.09, 0.095]
PROD_WEIGHTS = [0.085, 0.085, 0.083, 0.083, 0.082, 0.082, 0.083, 0.083, 0.084, 0.083, 0.083, 0.084]

FIN_ROWS = [
    ("Revenue", "revenue"),
    ("Operating profit", "operating_profit"),
    ("Interest expense", "interest_expense"),
    ("Net profit", "net_profit"),
    ("Current assets", "current_assets"),
    ("Current liabilities", "current_liabilities"),
    ("Total borrowings", "total_borrowings"),
    ("Shareholders' equity", "equity"),
    ("Net cash from operating activities", "operating_cash_flow"),
]

CASES = [
    {
        "slug": "case_b_unsupported_claim",
        "company": "Zenith Packaging Industries (Pvt) Ltd",
        "sector": "Manufacturing - industrial packaging",
        "location": "Korangi Industrial Area, Karachi, Sindh",
        "project": "1.2 MW rooftop solar PV system and energy-efficient motors and drives",
        "amount_pkr": 50_000_000,
        "base_year": "FY2025",
        "cmp_year": "FY2026",
        "claim_pct": 40,
        "baseline_stated": False,
        "method_stated": False,
        "appendix": False,
        "elec": (2_400_000, 2_832_000),
        "prod": (12_000, 12_600),
        "docs": ["electricity", "production", "financials"],
        "fin": {
            "base": {"revenue": 820.0, "operating_profit": 98.0, "interest_expense": 38.0,
                     "net_profit": 61.0, "current_assets": 310.0, "current_liabilities": 245.0,
                     "total_borrowings": 380.0, "equity": 290.0, "operating_cash_flow": 74.0},
            "cmp": {"revenue": 905.0, "operating_profit": 107.0, "interest_expense": 41.0,
                    "net_profit": 68.0, "current_assets": 332.0, "current_liabilities": 262.0,
                    "total_borrowings": 395.0, "equity": 330.0, "operating_cash_flow": 79.0},
        },
        "expected": (
            "Emissions claim should be flagged as insufficiently supported: no baseline year and no "
            "calculation method. Electricity +18% and production +5% imply kWh per tonne +12.4%, which "
            "conflicts with the energy-efficiency claim. Verification must test alternative explanations "
            "(energy source, reporting boundary, production mix). Practice claims have no supporting "
            "records. The report must NOT call the company fraudulent."
        ),
    },
    {
        "slug": "case_a_supported_claims",
        "company": "Crescent Ceramics (Pvt) Ltd",
        "sector": "Manufacturing - ceramics",
        "location": "SITE Industrial Area, Karachi, Sindh",
        "project": "Kiln heat-recovery system and variable frequency drives",
        "amount_pkr": 35_000_000,
        "base_year": "FY2025",
        "cmp_year": "FY2026",
        "claim_pct": 8,
        "baseline_stated": True,
        "method_stated": True,
        "appendix": True,
        "elec": (3_000_000, 2_760_000),
        "prod": (15_000, 15_450),
        "docs": ["electricity", "production", "financials"],
        "fin": {
            "base": {"revenue": 1150.0, "operating_profit": 160.0, "interest_expense": 30.0,
                     "net_profit": 98.0, "current_assets": 480.0, "current_liabilities": 300.0,
                     "total_borrowings": 350.0, "equity": 520.0, "operating_cash_flow": 130.0},
            "cmp": {"revenue": 1240.0, "operating_profit": 175.0, "interest_expense": 28.0,
                    "net_profit": 108.0, "current_assets": 520.0, "current_liabilities": 310.0,
                    "total_borrowings": 330.0, "equity": 600.0, "operating_cash_flow": 142.0},
        },
        "expected": (
            "Emissions claim (8% absolute reduction) has a stated baseline year, a stated method and a "
            "consistent calculation; electricity records (-8.0%) and production records (+3.0%) agree. "
            "Practice claims reference appendix items. Claims should be marked supported."
        ),
    },
    {
        "slug": "case_e_incomplete_application",
        "company": "Sapphire Leather Works (Pvt) Ltd",
        "sector": "Manufacturing - leather goods",
        "location": "Sialkot, Punjab",
        "project": "Effluent treatment upgrade and energy-efficient boilers",
        "amount_pkr": 20_000_000,
        "base_year": "FY2025",
        "cmp_year": "FY2026",
        "claim_pct": 25,
        "baseline_stated": False,
        "method_stated": False,
        "appendix": False,
        "elec": None,
        "prod": None,
        "docs": [],
        "fin": None,
        "expected": (
            "Only a sustainability statement was submitted. The system must report insufficient "
            "information (no electricity, production or financial records) and must NOT invent "
            "conclusions or scores for dimensions it cannot assess."
        ),
    },
]


# ---------------------------------------------------------------- helpers
def pct_change(old, new):
    return round((new - old) / old * 100, 1)


def month_labels(fy):
    end = int(fy[2:])
    return [f"{end - 1 if m >= 7 else end}-{m:02d}" for m in FY_MONTHS]


def split_total(total, weights):
    values = [round(total * w) for w in weights]
    values[-1] += total - sum(values)
    return values


def derived(c):
    if not c["elec"] or not c["prod"]:
        return None
    e0, e1 = c["elec"]
    p0, p1 = c["prod"]
    i0, i1 = e0 / p0, e1 / p1
    em0 = e0 * EMISSION_FACTOR / 1000
    em1 = e1 * EMISSION_FACTOR / 1000
    return {
        "electricity_change_pct": pct_change(e0, e1),
        "production_change_pct": pct_change(p0, p1),
        "kwh_per_tonne_base": round(i0, 2),
        "kwh_per_tonne_cmp": round(i1, 2),
        "kwh_per_tonne_change_pct": pct_change(i0, i1),
        "electricity_emissions_estimate_t_base": round(em0, 1),
        "electricity_emissions_estimate_t_cmp": round(em1, 1),
        "electricity_emissions_estimate_change_pct": pct_change(em0, em1),
        "note": (
            "Estimates use an illustrative factor. A change in electricity use alone does not prove a "
            "change in emissions: energy source, boundary and production mix can differ."
        ),
    }


def ratios(c):
    if not c["fin"]:
        return None
    f = c["fin"]["cmp"]
    return {
        "current_ratio": round(f["current_assets"] / f["current_liabilities"], 2),
        "debt_to_equity": round(f["total_borrowings"] / f["equity"], 2),
        "interest_cover": round(f["operating_profit"] / f["interest_expense"], 2),
        "net_margin_pct": round(f["net_profit"] / f["revenue"] * 100, 1),
        "revenue_growth_pct": pct_change(c["fin"]["base"]["revenue"], f["revenue"]),
    }


# ---------------------------------------------------------------- PDF rendering
STYLES = {
    "title": ("hebo", 16, 24),
    "h": ("hebo", 12, 18),
    "p": ("helv", 10, 14),
    "mono": ("cour", 9, 12),
    "note": ("heit", 8, 11),
}
WRAP = {"title": 60, "h": 80, "p": 92, "note": 110}


def page_header(page):
    page.insert_text(
        (50, 30),
        "SYNTHETIC DEMONSTRATION DATA - FICTIONAL COMPANY",
        fontname="hebo",
        fontsize=8,
        color=(0.6, 0.0, 0.0),
    )


def render_pdf(path, lines):
    doc = pymupdf.open()
    page = doc.new_page()
    page_header(page)
    y = 60
    for style, text in lines:
        if style == "gap":
            y += 8
            continue
        font, size, lead = STYLES[style]
        chunks = [text] if style == "mono" else (textwrap.wrap(text, WRAP[style]) or [""])
        for chunk in chunks:
            if y > 790:
                page = doc.new_page()
                page_header(page)
                y = 60
            page.insert_text((50, y), chunk, fontname=font, fontsize=size)
            y += lead
    total = len(doc)
    for i, pg in enumerate(doc):
        pg.insert_text((250, 825), f"Page {i + 1} of {total}", fontname="helv", fontsize=8)
    doc.save(str(path))
    doc.close()


# ---------------------------------------------------------------- document content
def statement_lines(c):
    base, cmp_ = c["base_year"], c["cmp_year"]
    d = derived(c)
    L = []
    L.append(("title", f"Sustainability Statement {cmp_}"))
    L.append(("p", c["company"]))
    L.append(("p", f"Sector: {c['sector']}"))
    L.append(("p", f"Location: {c['location']}"))
    L.append(("gap", ""))

    L.append(("h", "1. About the company"))
    L.append(("p", f"{c['company']} operates a manufacturing plant in {c['location']}. "
                   f"This statement summarises our environmental performance for {cmp_}."))
    L.append(("gap", ""))

    L.append(("h", "2. Carbon emissions performance"))
    if c["baseline_stated"]:
        L.append(("p", f"Compared with our baseline year ({base}), our electricity-related carbon "
                       f"emissions fell by {c['claim_pct']}% in {cmp_}."))
    else:
        L.append(("p", f"We reduced our carbon emissions by {c['claim_pct']}% over the reporting "
                       f"period, demonstrating our leadership in climate action."))
    L.append(("gap", ""))

    if c["method_stated"] and d:
        e0, e1 = c["elec"]
        p0, p1 = c["prod"]
        L.append(("h", "3. Methodology and boundary"))
        L.append(("p", "Emissions are calculated following the GHG Protocol Corporate Standard "
                       "(Scope 2, location-based): electricity consumed (kWh) multiplied by an emission "
                       f"factor of {EMISSION_FACTOR} kg CO2e per kWh (illustrative synthetic factor). "
                       "Boundary: the Karachi plant, all production lines. Baseline year: "
                       f"{base} (1 July to 30 June)."))
        L.append(("gap", ""))
        L.append(("mono", f"{'Metric':<34}{base:>14}{cmp_:>14}"))
        L.append(("mono", "-" * 62))
        L.append(("mono", f"{'Electricity consumed (kWh)':<34}{e0:>14,}{e1:>14,}"))
        L.append(("mono", f"{'Production (tonnes)':<34}{p0:>14,}{p1:>14,}"))
        L.append(("mono", f"{'Emissions (t CO2e)':<34}"
                          f"{d['electricity_emissions_estimate_t_base']:>14,.1f}"
                          f"{d['electricity_emissions_estimate_t_cmp']:>14,.1f}"))
        L.append(("mono", f"{'Electricity per tonne (kWh/t)':<34}"
                          f"{d['kwh_per_tonne_base']:>14,.1f}{d['kwh_per_tonne_cmp']:>14,.1f}"))
    else:
        L.append(("h", "3. Our approach"))
        L.append(("p", "Our approach follows industry best practice and is applied consistently "
                       "across the business."))
    L.append(("gap", ""))

    L.append(("h", "4. Energy efficiency"))
    if c["method_stated"] and d:
        L.append(("p", f"Electricity use per tonne produced changed from {d['kwh_per_tonne_base']:.1f} to "
                       f"{d['kwh_per_tonne_cmp']:.1f} kWh per tonne ({d['kwh_per_tonne_change_pct']}%), "
                       "based on the attached electricity and production records."))
    else:
        L.append(("p", "We have improved our energy efficiency through continuous investment in "
                       "modern equipment and better operating practices."))
    L.append(("gap", ""))

    L.append(("h", "5. Sustainable production practices"))
    refs = [" (see Appendix A, item 1)", " (see Appendix A, item 2)", " (see Appendix A, item 3)"]
    if not c["appendix"]:
        refs = ["", "", ""]
    L.append(("p", f"- We adopted sustainable production practices across all production lines{refs[0]}."))
    L.append(("p", f"- We implemented a wastewater recycling programme{refs[1]}."))
    L.append(("p", f"- We reduced our reliance on virgin raw materials{refs[2]}."))
    L.append(("gap", ""))

    L.append(("h", "6. Project for which financing is requested"))
    L.append(("p", f"Project: {c['project']}."))
    L.append(("p", f"Financing requested: PKR {c['amount_pkr']:,}."))
    L.append(("p", "We expect the project to lower grid electricity demand (projection only, not yet "
                   "measured)."))
    L.append(("gap", ""))
    L.append(("p", "Prepared by: Head of Sustainability (fictional)    Date: 30 September 2026"))

    if c["appendix"]:
        L.append(("gap", ""))
        L.append(("h", "Appendix A - Supporting record references"))
        L.append(("p", "1. Variable frequency drives installed on 14 production motors - work order "
                       "WO-2026-031, completed 2025-11-20."))
        L.append(("p", "2. Wastewater recycling unit commissioned - commissioning certificate "
                       "CC-2026-007, dated 2026-02-12."))
        L.append(("p", "3. Recycled raw material purchases - purchase orders PO-2026-0412 to "
                       "PO-2026-0455."))
    return L


def financial_lines(c):
    base, cmp_ = c["base_year"], c["cmp_year"]
    L = [
        ("title", "Summary Financial Statements"),
        ("p", c["company"]),
        ("note", "Synthetic summary prepared for demonstration. Amounts in PKR million."),
        ("gap", ""),
        ("h", f"Selected financial information, years ended 30 June {base[2:]} and {cmp_[2:]}"),
        ("gap", ""),
        ("mono", f"{'PKR million':<40}{base:>12}{cmp_:>12}"),
        ("mono", "-" * 64),
    ]
    for label, key in FIN_ROWS:
        L.append(("mono", f"{label:<40}{c['fin']['base'][key]:>12,.1f}{c['fin']['cmp'][key]:>12,.1f}"))
    L.append(("gap", ""))
    L.append(("note", "Source: company management accounts (synthetic). Not independently audited."))
    return L


# ---------------------------------------------------------------- build
def write_monthly_csv(path, value_name, series, weights, extra=None):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        header = ["month", "fiscal_year", value_name] + ([extra[0]] if extra else [])
        w.writerow(header)
        for fy, total in series:
            for label, val in zip(month_labels(fy), split_total(total, weights)):
                w.writerow([label, fy, val] + ([extra[1]] if extra else []))


def build_case(c):
    out = OUT_DIR / c["slug"]
    out.mkdir(parents=True, exist_ok=True)
    files = []

    render_pdf(out / "sustainability_statement.pdf", statement_lines(c))
    files.append("sustainability_statement.pdf")

    if "electricity" in c["docs"] and c["elec"]:
        series = [(c["base_year"], c["elec"][0]), (c["cmp_year"], c["elec"][1])]
        write_monthly_csv(out / "electricity_records.csv", "electricity_kwh", series,
                          ELEC_WEIGHTS, extra=("source", "grid"))
        files.append("electricity_records.csv")

    if "production" in c["docs"] and c["prod"]:
        series = [(c["base_year"], c["prod"][0]), (c["cmp_year"], c["prod"][1])]
        write_monthly_csv(out / "production_data.csv", "production_tonnes", series, PROD_WEIGHTS)
        files.append("production_data.csv")

    if "financials" in c["docs"] and c["fin"]:
        render_pdf(out / "financial_statements.pdf", financial_lines(c))
        files.append("financial_statements.pdf")

    info = {
        "company": c["company"],
        "sector": c["sector"],
        "location": c["location"],
        "project": c["project"],
        "requested_amount_pkr": c["amount_pkr"],
        "documents": files,
        "claimed_emissions_reduction_pct": c["claim_pct"],
        "baseline_stated": c["baseline_stated"],
        "method_stated": c["method_stated"],
        "derived_metrics": derived(c),
        "financial_ratios_cmp_year": ratios(c),
        "expected_outcome": c["expected"],
        "synthetic": True,
    }
    with open(out / "case_info.json", "w", encoding="utf-8") as f:
        json.dump(info, f, indent=2)

    print(f"[ok] {c['slug']}: {', '.join(files)}")


if __name__ == "__main__":
    OUT_DIR.mkdir(exist_ok=True)
    for case in CASES:
        build_case(case)
    print(f"Done. Files are in: {OUT_DIR}")