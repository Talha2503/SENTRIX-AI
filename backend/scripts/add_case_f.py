"""Add Case F (alternative explanation) to the synthetic sample data. All fictional.

Run from backend:  python scripts\\add_case_f.py
"""
import json

import generate_sample_data as g

C = {
    "slug": "case_f_alternative_explanation",
    "company": "Lakeview Textiles (Pvt) Ltd",
    "sector": "Manufacturing - textile processing",
    "location": "Faisalabad, Punjab",
    "project": "600 kW solar expansion and heat recovery on dyeing lines",
    "amount_pkr": 30_000_000,
    "base_year": "FY2025",
    "cmp_year": "FY2026",
    "claim_pct": 15,
    "elec": (4_000_000, 4_240_000),
    "prod": (20_000, 20_400),
    "fin": {
        "base": {"revenue": 700.0, "operating_profit": 85.0, "interest_expense": 20.0, "net_profit": 52.0,
                 "current_assets": 260.0, "current_liabilities": 190.0, "total_borrowings": 210.0,
                 "equity": 300.0, "operating_cash_flow": 66.0},
        "cmp": {"revenue": 740.0, "operating_profit": 90.0, "interest_expense": 19.0, "net_profit": 56.0,
                "current_assets": 280.0, "current_liabilities": 200.0, "total_borrowings": 200.0,
                "equity": 328.0, "operating_cash_flow": 70.0},
    },
}


def statement_lines():
    return [
        ("title", "Sustainability Statement FY2026"),
        ("p", C["company"]),
        ("p", f"Sector: {C['sector']}"),
        ("p", f"Location: {C['location']}"),
        ("gap", ""),
        ("h", "1. About the company"),
        ("p", f"{C['company']} operates a textile processing plant in {C['location']}. This statement "
              "summarises our environmental performance for FY2026."),
        ("gap", ""),
        ("h", "2. Carbon emissions performance"),
        ("p", "We reduced our electricity-related carbon emissions by 15% in FY2026."),
        ("gap", ""),
        ("h", "3. On-site generation"),
        ("p", "A 600 kW captive solar plant has been operational at our plant since July 2025 and supplies "
              "part of our electricity demand."),
        ("gap", ""),
        ("h", "4. Governance"),
        ("p", "Our board reviews operational performance each quarter. Sustainability topics are discussed "
              "alongside production, safety and finance matters. The management team is responsible for "
              "preparing this statement, and information is collected from the plant, finance and "
              "maintenance departments. The statement covers the financial year from 1 July 2025 to "
              "30 June 2026 and is intended to give lenders a clear picture of our current position and "
              "our plans. Quarterly management meetings also review customer requirements and supplier "
              "arrangements."),
        ("gap", ""),
        ("h", "5. Project for which financing is requested"),
        ("p", f"Project: {C['project']}."),
        ("p", f"Financing requested: PKR {C['amount_pkr']:,}."),
        ("gap", ""),
        ("h", "6. Reporting basis"),
        ("p", "Baseline year for all comparisons in this statement: FY2025. Boundary: the Faisalabad plant, "
              "all production lines. Electricity records cover total consumption from all sources."),
        ("gap", ""),
        ("p", "Prepared by: Head of Sustainability (fictional)    Date: 30 September 2026"),
    ]


def main():
    out = g.OUT_DIR / C["slug"]
    out.mkdir(parents=True, exist_ok=True)
    g.render_pdf(out / "sustainability_statement.pdf", statement_lines())
    g.write_monthly_csv(
        out / "electricity_records.csv", "electricity_kwh",
        [(C["base_year"], C["elec"][0]), (C["cmp_year"], C["elec"][1])], g.ELEC_WEIGHTS,
        extra=("source", "all sources"),
    )
    g.write_monthly_csv(
        out / "production_data.csv", "production_tonnes",
        [(C["base_year"], C["prod"][0]), (C["cmp_year"], C["prod"][1])], g.PROD_WEIGHTS,
    )
    g.render_pdf(out / "financial_statements.pdf", g.financial_lines(C))
    info = {
        "company": C["company"], "sector": C["sector"], "location": C["location"], "project": C["project"],
        "requested_amount_pkr": C["amount_pkr"],
        "documents": ["sustainability_statement.pdf", "electricity_records.csv", "production_data.csv",
                      "financial_statements.pdf"],
        "claimed_emissions_reduction_pct": C["claim_pct"],
        "derived_metrics": g.derived(C),
        "financial_ratios_cmp_year": g.ratios(C),
        "expected_outcome": (
            "The 15% claim is extracted without a baseline (the baseline appears in a later section), so the "
            "verification step should find it and trigger a targeted reassessment. Electricity records show +6.0% "
            "total consumption and kWh per tonne +3.9%, but the statement documents an operating captive solar plant, "
            "so the anomaly should be DISPUTED (alternative explanation documented), with a follow-up to obtain "
            "solar generation records. No methodology is documented. The report must not accuse the company."
        ),
        "synthetic": True,
    }
    (out / "case_info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(f"[ok] {C['slug']}")


if __name__ == "__main__":
    main()