"""Financial Intelligence agent: deterministic ratios from the extracted statement figures."""
from sqlalchemy.orm import Session

from app.models.models import Application
from app.services.calculations import add_calc_evidence, metric_by_period, pct_change
from app.services.findings import add_finding

AGENT = "financial_intelligence"

METRICS = [
    "revenue", "operating_profit", "interest_expense", "net_profit", "current_assets",
    "current_liabilities", "total_borrowings", "equity", "operating_cash_flow",
]

NOTE = (
    "Computed deterministically from figures extracted from the submitted statements; "
    "the inputs themselves are not independently verified."
)
CAVEAT = "Thresholds are illustrative design assumptions, not regulatory or banking limits."
FOLLOWUP = "Ask the applicant to explain the drivers and provide the latest audited statements and debt schedule."

# name, numerator, denominator, multiplier, unit, direction, medium threshold, high threshold, label
RATIO_RULES = [
    ("current_ratio", "current_assets", "current_liabilities", 1.0, "x", "min", 1.2, 1.0, "Liquidity (current ratio)"),
    ("debt_to_equity", "total_borrowings", "equity", 1.0, "x", "max", 1.5, 2.0, "Leverage (debt to equity)"),
    ("interest_cover", "operating_profit", "interest_expense", 1.0, "x", "min", 3.0, 1.5, "Interest cover"),
    ("net_margin_pct", "net_profit", "revenue", 100.0, "%", "min", 3.0, 0.0, "Net profit margin"),
    ("cash_conversion", "operating_cash_flow", "net_profit", 1.0, "x", "min", 0.8, 0.0,
     "Cash conversion (operating cash flow / net profit)"),
]

# metric, indicator name, label, medium threshold (% change), high threshold (% change)
TREND_RULES = [
    ("revenue", "revenue_growth_pct", "Revenue growth", -10.0, -25.0),
    ("net_profit", "net_profit_growth_pct", "Net profit growth", -20.0, -50.0),
]


def run(db: Session, application_id: int) -> dict:
    application = db.get(Application, application_id)
    by = {m: metric_by_period(db, application_id, m) for m in METRICS}

    if not by["revenue"]:
        add_finding(
            db, application_id, AGENT, "financial",
            "Financial indicators could not be assessed",
            "No readable financial statement figures (revenue, profit, assets, liabilities, borrowings, "
            "equity) were found in the submitted documents, so financial stability is not assessed. "
            "This is a data gap, not a negative finding.",
            severity="medium", status="insufficient_information",
            followup="Request the latest financial statements for at least two periods.",
        )
        db.commit()
        return {"assessed": False, "reason": "no financial statement figures found"}

    periods = sorted(set().union(*[set(v) for v in by.values()]))
    cur = periods[-1]
    prior = periods[-2] if len(periods) > 1 else None

    indicators: dict[str, float] = {}
    limitations: list[str] = []
    all_calc = []
    exceptions = 0

    for name, num, den, mult, unit, direction, medium, high, label in RATIO_RULES:
        n, d = by[num].get(cur), by[den].get(cur)
        if n is None or d is None or d.value <= 0:
            limitations.append(f"{label}: inputs missing or not positive for {cur}")
            continue
        value = n.value / d.value * mult
        calc = add_calc_evidence(
            db, application_id, name, round(value, 4), unit, cur,
            f"{name} {cur} = {num} {n.value:,.1f} / {den} {d.value:,.1f}"
            f"{' x 100' if mult == 100 else ''} = {value:,.2f}{unit}",
        )
        indicators[name] = round(value, 2)
        all_calc.append(calc)

        severity = None
        if direction == "min":
            severity = "high" if value < high else "medium" if value < medium else None
        else:
            severity = "high" if value > high else "medium" if value > medium else None
        if severity:
            exceptions += 1
            threshold = high if severity == "high" else medium
            side = "below" if direction == "min" else "above"
            add_finding(
                db, application_id, AGENT, "financial",
                f"{label} is {value:.2f}{unit}, {side} the illustrative {threshold:g}{unit} threshold",
                f"{label} for {cur}: {num.replace('_', ' ')} {n.value:,.1f} and {den.replace('_', ' ')} "
                f"{d.value:,.1f} (PKR million where applicable) give {value:.2f}{unit}. {CAVEAT} "
                "A single-period ratio does not show whether the position is improving or typical for the sector.",
                severity=severity, status="potential_anomaly", confidence=0.8, confidence_notes=NOTE,
                followup=FOLLOWUP, evidence=[calc, n, d],
            )

    if prior:
        for metric, name, label, medium, high in TREND_RULES:
            a, b = by[metric].get(prior), by[metric].get(cur)
            change = pct_change(a.value, b.value) if a and b else None
            if change is None:
                continue
            calc = add_calc_evidence(
                db, application_id, name, round(change, 2), "%", f"{prior}->{cur}",
                f"{metric} {prior} {a.value:,.1f} -> {cur} {b.value:,.1f} = {change:+.1f}%",
            )
            indicators[name] = round(change, 1)
            all_calc.append(calc)
            severity = "high" if change < high else "medium" if change < medium else None
            if severity:
                exceptions += 1
                add_finding(
                    db, application_id, AGENT, "financial",
                    f"{label} is {change:+.1f}% ({prior} to {cur})",
                    f"{metric.replace('_', ' ').title()} moved from {a.value:,.1f} to {b.value:,.1f}. {CAVEAT}",
                    severity=severity, status="potential_anomaly", confidence=0.8, confidence_notes=NOTE,
                    followup=FOLLOWUP, evidence=[calc, a, b],
                )

    equity = by["equity"].get(cur)
    if (
        application.requested_amount
        and application.currency == "PKR"
        and equity is not None
        and equity.unit == "PKR million"
        and equity.value > 0
    ):
        requested_m = application.requested_amount / 1_000_000
        pct = requested_m / equity.value * 100
        calc = add_calc_evidence(
            db, application_id, "requested_to_equity_pct", round(pct, 2), "%", cur,
            f"requested PKR {requested_m:,.1f}m / equity {equity.value:,.1f}m = {pct:.1f}%",
        )
        indicators["requested_to_equity_pct"] = round(pct, 1)
        all_calc.append(calc)
        severity = "high" if pct > 100 else "medium" if pct > 50 else None
        if severity:
            exceptions += 1
            add_finding(
                db, application_id, AGENT, "financial",
                f"Requested financing is {pct:.0f}% of shareholders' equity",
                f"The request (PKR {requested_m:,.1f} million) compared with equity of {equity.value:,.1f} million "
                f"for {cur}. {CAVEAT}",
                severity=severity, status="potential_anomaly", confidence=0.8, confidence_notes=NOTE,
                followup="Review debt capacity, security and repayment sources.", evidence=[calc, equity],
            )

    if exceptions == 0 and all_calc:
        listing = "; ".join(f"{k} = {v}" for k, v in indicators.items())
        add_finding(
            db, application_id, AGENT, "financial",
            "Financial indicators are within the illustrative thresholds",
            f"For {cur}: {listing}. {CAVEAT}",
            severity="low", status="verified", confidence=0.8, confidence_notes=NOTE, evidence=all_calc,
        )
    if limitations:
        add_finding(
            db, application_id, AGENT, "financial",
            "Some financial indicators could not be computed",
            "; ".join(limitations) + ". These indicators are not assessed.",
            severity="low", status="insufficient_information",
            followup="Provide the missing statement lines.",
        )

    db.commit()
    return {"assessed": True, "period": cur, "indicators": indicators, "exceptions": exceptions,
            "limitations": limitations}