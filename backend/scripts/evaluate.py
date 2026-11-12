"""SENTRIX AI evaluation harness.

Loads each synthetic case, runs the full investigation through the API, and compares the results with
ground truth computed independently of the agents (from the sample-data generator).

Usage (backend server running, from the backend folder):
    python scripts\\evaluate.py             # run all cases and keep the applications
    python scripts\\evaluate.py --cleanup   # delete the evaluation applications afterwards

Writes ..\\docs\\evaluation_results.md
"""
import argparse
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND = SCRIPT_DIR.parent
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(BACKEND))

import add_case_f  # noqa: E402
import generate_sample_data as g  # noqa: E402
from app.core.config import settings  # noqa: E402

BASE_URL = "http://127.0.0.1:8000"
DOCS_OUT = BACKEND.parent / "docs" / "evaluation_results.md"
ORDER = [
    "case_b_unsupported_claim",
    "case_f_alternative_explanation",
    "case_a_supported_claims",
    "case_e_incomplete_application",
]
FIN_KEYS = [
    "revenue", "operating_profit", "interest_expense", "net_profit", "current_assets",
    "current_liabilities", "total_borrowings", "equity", "operating_cash_flow",
]
RISKY = {"contradictory", "potential_anomaly"}
BANNED = re.compile(r"fraud|certified green|guarantee|illegal|criminal|deceiv|\bliar|\blying", re.I)
GAP_WORDS = re.compile(r"insufficient|not (?:adequately |sufficiently )?supported|unsupported|lacks", re.I)

REFS = {c["slug"]: c for c in g.CASES}
REFS[add_case_f.C["slug"]] = add_case_f.C


def norm(text: str) -> str:
    text = text.replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", text).strip().lower()


def fmt(good: int, total: int) -> str:
    return "n/a" if not total else f"{good}/{total} ({good / total:.0%})"


def pct(a: float, b: float) -> float:
    return (b - a) / abs(a) * 100


# ------------------------------------------------------------------ ground truth
def reference_fields(ref: dict) -> list[tuple[str, str, float]]:
    fields = []
    base, cmp_ = ref["base_year"], ref["cmp_year"]
    if ref["elec"]:
        fields += [("electricity_kwh", base, float(ref["elec"][0])), ("electricity_kwh", cmp_, float(ref["elec"][1]))]
    if ref["prod"]:
        fields += [("production_tonnes", base, float(ref["prod"][0])), ("production_tonnes", cmp_, float(ref["prod"][1]))]
    if ref["fin"]:
        for key in FIN_KEYS:
            fields.append((key, base, float(ref["fin"]["base"][key])))
            fields.append((key, cmp_, float(ref["fin"]["cmp"][key])))
    return fields


def reference_calcs(ref: dict) -> dict[str, float]:
    out = {}
    if ref["elec"] and ref["prod"]:
        e0, e1 = ref["elec"]
        p0, p1 = ref["prod"]
        out["electricity_change_pct"] = pct(e0, e1)
        out["production_change_pct"] = pct(p0, p1)
        out["kwh_per_tonne_change_pct"] = pct(e0 / p0, e1 / p1)
    if ref["fin"]:
        a, b = ref["fin"]["base"], ref["fin"]["cmp"]
        out["current_ratio"] = b["current_assets"] / b["current_liabilities"]
        out["debt_to_equity"] = b["total_borrowings"] / b["equity"]
        out["interest_cover"] = b["operating_profit"] / b["interest_expense"]
        out["net_margin_pct"] = b["net_profit"] / b["revenue"] * 100
        out["cash_conversion"] = b["operating_cash_flow"] / b["net_profit"]
        out["revenue_growth_pct"] = pct(a["revenue"], b["revenue"])
        out["net_profit_growth_pct"] = pct(a["net_profit"], b["net_profit"])
        out["requested_to_equity_pct"] = ref["amount_pkr"] / 1_000_000 / b["equity"] * 100
    return out


# ------------------------------------------------------------------ metrics
def extraction_accuracy(ref: dict, evidence: list[dict]) -> tuple[int, int]:
    fields = reference_fields(ref)
    good = 0
    for metric, period, expected in fields:
        tolerance = max(0.01, 0.001 * abs(expected))
        if any(
            e["metric"] == metric and e["reporting_period"] == period and e["evidence_type"] == "contextual"
            and e["value"] is not None and abs(e["value"] - expected) <= tolerance
            for e in evidence
        ):
            good += 1
    return good, len(fields)


def calc_value(evidence: list[dict], metric: str):
    items = [e for e in evidence if e["evidence_type"] == "calculation" and e["metric"] == metric and e["value"] is not None]
    return items[-1]["value"] if items else None


def calc_correctness(ref: dict, evidence: list[dict]) -> tuple[int, int]:
    expected = reference_calcs(ref)
    good = 0
    for metric, exp in expected.items():
        got = calc_value(evidence, metric)
        if got is not None and abs(got - exp) <= 0.02 + 0.001 * abs(exp):
            good += 1
    return good, len(expected)


def traceability(findings: list[dict], ev_by_id: dict) -> tuple[int, int]:
    sample = [f for f in findings if f["status"] not in ("insufficient_information", "not_assessed")]

    def traceable(f: dict) -> bool:
        items = [ev_by_id.get(i) for i in f["evidence_ids"]]
        if not items or any(e is None for e in items):
            return False
        return all(
            e["document_id"] is not None or e["evidence_type"] == "calculation"
            or e["extraction_method"] == "application_form"
            for e in items
        )

    return sum(1 for f in sample if traceable(f)), len(sample)


def quote_check(client: httpx.Client, evidence: list[dict]) -> tuple[int, int]:
    sources = [e for e in evidence if e["evidence_type"] == "claim_source"]
    cache: dict[int, dict[int, str]] = {}
    good = 0
    for e in sources:
        doc = e["document_id"]
        if doc not in cache:
            cache[doc] = {c["id"]: c["text"] for c in client.get(f"/documents/{doc}/chunks").json()}
        if e["excerpt"] and norm(e["excerpt"]) in norm(cache[doc].get(e["chunk_id"], "")):
            good += 1
    return good, len(sources)


# ------------------------------------------------------------------ behaviour checks per case
def case_checks(slug: str, ctx: dict) -> list[tuple[str, bool]]:
    claims, findings, evidence, report, runs = ctx["claims"], ctx["findings"], ctx["evidence"], ctx["report"], ctx["runs"]
    content = report["content"] if report else {}
    summary = content.get("executive_summary", "")
    overall = content.get("overall", {})
    dims = content.get("dimensions", {})
    emissions = [c for c in claims if c["category"] == "emissions" and c["value"] is not None]
    anomalies = [f for f in findings if f["status"] in RISKY]
    checks: list[tuple[str, bool]] = []

    def add(label: str, ok) -> None:
        checks.append((label, bool(ok)))

    add("Investigation completed and a report was produced", report is not None and ctx["status"] == "completed")
    add("No accusatory language in the summary or finding titles",
        not BANNED.search(summary + " " + " ".join(f["title"] for f in findings)))

    if slug.startswith("case_b"):
        add("40% emissions claim extracted as -40", any(c["value"] == -40 for c in emissions))
        add("Emissions claim extracted with no baseline", any(c["baseline_period"] is None for c in emissions))
        add("Missing baseline/method flagged as high-severity 'insufficient information'",
            any(f["status"] == "insufficient_information" and f["severity"] == "high" and "Emissions claim" in f["title"]
                for f in findings))
        add("Energy-efficiency claim flagged as contradicting the records",
            any(f["status"] == "contradictory" and "Energy-efficiency" in f["title"] for f in findings))
        add("Anomalies carry an adversarial verdict",
            bool(anomalies) and all(f["verification_status"] in ("verified", "disputed", "unresolved", "unsupported")
                                    for f in anomalies))
        kwh = calc_value(evidence, "kwh_per_tonne_change_pct")
        add("Electricity per tonne change is +12.4% (+/-0.2)", kwh is not None and abs(kwh - 12.4) <= 0.2)
        add("Practice claims reported as unverified",
            any(f["status"] == "unverified" and "practice claim" in f["title"] for f in findings))
        add("Summary says the claim is insufficiently supported (not fraud)", GAP_WORDS.search(summary))
        add("Overall risk given with coverage of at least 40%",
            overall.get("risk_score") is not None and overall.get("coverage", 0) >= 0.4)

    elif slug.startswith("case_f"):
        add("Baseline FY2025 attached to the emissions claim",
            any((c["baseline_period"] or "").replace(" ", "").upper() == "FY2025" for c in emissions))
        add("Verification triggered a targeted reassessment (taxonomy ran twice)",
            sum(1 for r in runs if r["agent_name"] == "green_taxonomy") >= 2)
        add("Electricity anomaly is DISPUTED (documented on-site solar plant)",
            any(f["status"] in RISKY and f["verification_status"] == "disputed" and "electricity" in f["title"].lower()
                for f in findings))
        elec = calc_value(evidence, "electricity_change_pct")
        add("Electricity change is +6.0% (+/-0.2)", elec is not None and abs(elec - 6.0) <= 0.2)
        add("Missing methodology still reported",
            any(f["status"] == "insufficient_information" and "Emissions claim" in f["title"] for f in findings))

    elif slug.startswith("case_a"):
        add("Emissions claim has baseline FY2025",
            any((c["baseline_period"] or "").replace(" ", "").upper() == "FY2025" for c in emissions))
        add("No contradictory findings", not any(f["status"] == "contradictory" for f in findings))
        add("No high-severity risk findings",
            not any(f["severity"] == "high" and f["status"] in RISKY for f in findings))
        add("Emissions change confirmed consistent with the records",
            any(f["status"] == "verified" and "consistent with the electricity records" in f["title"] for f in findings))
        add("Statement figures match the underlying records",
            any(f["status"] == "verified" and "match the underlying records" in f["title"] for f in findings))
        add("Overall risk is given and below 40",
            overall.get("risk_score") is not None and overall["risk_score"] < 40)

    elif slug.startswith("case_e"):
        add("No overall risk score is given (coverage too low)", overall.get("risk_score") is None)
        add("Overall coverage is below 40%", overall.get("coverage", 1) < 0.4)
        add("No contradictions or anomalies were invented", not anomalies)
        add("Financial stability reported as not assessed",
            dims.get("financial_stability", {}).get("risk_score", 0) is None)
        add("Missing financial data reported as insufficient information",
            any(f["category"] == "financial" and f["status"] == "insufficient_information" for f in findings))
    return checks


# ------------------------------------------------------------------ run one case
def collect(client: httpx.Client, app_id: int):
    inv = client.get(f"/applications/{app_id}/investigation").json()
    claims = client.get(f"/applications/{app_id}/claims").json()
    findings = client.get(f"/applications/{app_id}/findings").json()
    evidence = client.get(f"/applications/{app_id}/evidence").json()
    response = client.get(f"/applications/{app_id}/report")
    return inv, claims, findings, evidence, (response.json() if response.status_code == 200 else None)


def evaluate_case(client: httpx.Client, slug: str) -> dict:
    ref = REFS[slug]
    row: dict = {"slug": slug, "error": None}
    response = client.post(f"/demo/{slug}/load")
    response.raise_for_status()
    app_id = response.json()["application_id"]
    row["app_id"] = app_id

    started = time.time()
    client.post(f"/applications/{app_id}/investigate").raise_for_status()
    while True:
        time.sleep(3)
        status = client.get(f"/applications/{app_id}/investigation").json()["status"]
        print(f"    status: {status} ({time.time() - started:.0f}s)", end="\r")
        if status != "investigating":
            break
        if time.time() - started > 900:
            raise TimeoutError("the investigation did not finish within 15 minutes")
    row["seconds"] = time.time() - started

    inv, claims, findings, evidence, report = collect(client, app_id)
    runs = inv["agent_runs"]
    ev_by_id = {e["id"]: e for e in evidence}
    ctx = {"claims": claims, "findings": findings, "evidence": evidence, "report": report,
           "runs": runs, "status": inv["status"]}
    row["status"] = inv["status"]
    row["findings"] = len(findings)
    row["runs"] = (sum(1 for r in runs if r["status"] == "completed"), len(runs))
    row["success"] = inv["status"] == "completed" and report is not None and row["runs"][0] == row["runs"][1]
    row["extraction"] = extraction_accuracy(ref, evidence)
    row["calcs"] = calc_correctness(ref, evidence)
    row["trace"] = traceability(findings, ev_by_id)
    row["quotes"] = quote_check(client, evidence)
    row["checks"] = case_checks(slug, ctx)
    return row


def ensure_sample_data() -> None:
    others = [s for s in ORDER if not s.startswith("case_f")]
    if not all((g.OUT_DIR / s / "case_info.json").exists() for s in others):
        g.OUT_DIR.mkdir(exist_ok=True)
        for case in g.CASES:
            g.build_case(case)
    if not (g.OUT_DIR / add_case_f.C["slug"] / "case_info.json").exists():
        add_case_f.main()


# ------------------------------------------------------------------ reporting
def totals(rows: list[dict], key: str) -> tuple[int, int]:
    return sum(r[key][0] for r in rows if "error" in r and not r["error"]), sum(
        r[key][1] for r in rows if not r["error"]
    )


def write_markdown(rows: list[dict]) -> None:
    ok_rows = [r for r in rows if not r["error"]]
    checks_total = sum(len(r["checks"]) for r in ok_rows)
    checks_pass = sum(1 for r in ok_rows for _, ok in r["checks"] if ok)
    times = [r["seconds"] for r in ok_rows]
    lines = [
        "# SENTRIX AI - Evaluation results",
        "",
        f"Generated: {datetime.now():%Y-%m-%d %H:%M}  ",
        f"Language model: `{settings.GROQ_MODEL}` (Groq)",
        "",
        "## Scope and caveats",
        "",
        "- Four synthetic, fictional test cases (supported claims, unsupported claim, incomplete application, "
        "alternative explanation). Ground truth is computed independently of the agents.",
        "- This is a very small test set. Results show behaviour on controlled inputs, not general accuracy, and "
        "should not be read as a performance guarantee.",
        "- No model accuracy is claimed. Numbers are extracted and calculated by deterministic code; the language "
        "model only extracts claims and drafts commentary.",
        "- Scores use illustrative weights and thresholds (see README).",
        "",
        "## Summary metrics",
        "",
        "| Metric | Result |",
        "|---|---|",
        f"| End-to-end success (completed, report, all agent tasks completed) | "
        f"{fmt(sum(1 for r in ok_rows if r['success']), len(rows))} |",
        f"| Agent task completion rate | {fmt(*totals(rows, 'runs'))} |",
        f"| Extraction accuracy (numeric fields vs reference) | {fmt(*totals(rows, 'extraction'))} |",
        f"| Calculation correctness (vs independently computed values) | {fmt(*totals(rows, 'calcs'))} |",
        f"| Findings traceable to a source or calculation | {fmt(*totals(rows, 'trace'))} |",
        f"| Claim quotes found verbatim in their source passage | {fmt(*totals(rows, 'quotes'))} |",
        f"| Behaviour checks passed | {fmt(checks_pass, checks_total)} |",
        f"| Processing time per case | "
        f"{'n/a' if not times else f'{min(times):.0f}-{max(times):.0f} s (mean {sum(times) / len(times):.0f} s)'} |",
        "",
        "## Per case",
        "",
        "| Case | Time | Agent tasks | Extraction | Calculations | Traceable | Quotes | Behaviour checks |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        if r["error"]:
            lines.append(f"| {r['slug']} | error | {r['error']} | | | | | |")
            continue
        passed = sum(1 for _, ok in r["checks"] if ok)
        lines.append(
            f"| {r['slug']} | {r['seconds']:.0f} s | {fmt(*r['runs'])} | {fmt(*r['extraction'])} | "
            f"{fmt(*r['calcs'])} | {fmt(*r['trace'])} | {fmt(*r['quotes'])} | {passed}/{len(r['checks'])} |"
        )
    lines += ["", "## Behaviour checks", ""]
    for r in rows:
        lines.append(f"### {r['slug']}")
        lines.append("")
        if r["error"]:
            lines += [f"Error: {r['error']}", ""]
            continue
        for label, ok in r["checks"]:
            lines.append(f"- [{'x' if ok else ' '}] {label}")
        lines.append("")
    DOCS_OUT.parent.mkdir(parents=True, exist_ok=True)
    DOCS_OUT.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cleanup", action="store_true", help="delete the evaluation applications afterwards")
    args = parser.parse_args()

    ensure_sample_data()
    try:
        httpx.get(f"{BASE_URL}/health", timeout=5).raise_for_status()
    except Exception:
        print("The backend is not reachable. Start it with: uvicorn app.main:app --reload")
        sys.exit(1)

    rows = []
    with httpx.Client(base_url=BASE_URL, timeout=120) as client:
        for slug in ORDER:
            print(f"\n>>> {slug}")
            try:
                row = evaluate_case(client, slug)
            except Exception as exc:  # record the failure and continue
                row = {"slug": slug, "error": f"{type(exc).__name__}: {exc}"[:200]}
            rows.append(row)
            if row["error"]:
                print(f"\n    ERROR: {row['error']}")
                continue
            print(f"\n    {row['seconds']:.0f}s | agent tasks {fmt(*row['runs'])} | extraction {fmt(*row['extraction'])} "
                  f"| calculations {fmt(*row['calcs'])} | traceable {fmt(*row['trace'])} | quotes {fmt(*row['quotes'])}")
            for label, ok in row["checks"]:
                print(f"    [{'PASS' if ok else 'FAIL'}] {label}")
            if args.cleanup:
                client.delete(f"/applications/{row['app_id']}")

    write_markdown(rows)
    failed = [label for r in rows if not r["error"] for label, ok in r["checks"] if not ok]
    errors = [r for r in rows if r["error"]]
    print(f"\nResults written to {DOCS_OUT}")
    print(f"{len(failed)} behaviour check(s) failed, {len(errors)} case(s) errored.")
    sys.exit(0 if not failed and not errors else 2)


if __name__ == "__main__":
    main()