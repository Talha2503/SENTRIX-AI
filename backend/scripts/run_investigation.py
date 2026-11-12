"""Start an investigation, watch it finish, and print the results.

Usage (server must be running):  python scripts\\run_investigation.py <application_id>
"""
import sys
import time

import httpx

BASE_URL = "http://127.0.0.1:8000"
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def main(app_id: int) -> None:
    with httpx.Client(base_url=BASE_URL, timeout=60) as client:
        client.post(f"/applications/{app_id}/investigate?force=true").raise_for_status()
        print("Investigation started...")
        seen = ""
        while True:
            time.sleep(3)
            info = client.get(f"/applications/{app_id}/investigation").json()
            line = ", ".join(f"{r['agent_name']}={r['status']}" for r in info["agent_runs"])
            if line != seen:
                print(f"status={info['status']:<14} {line}")
                seen = line
            if info["status"] != "investigating":
                break

        for run in info["agent_runs"]:
            if run["error"]:
                print(f"ERROR in {run['agent_name']}: {run['error']}")
            for warning in (run["output"] or {}).get("warnings", []):
                print(f"WARNING ({run['agent_name']}): {warning}")

        findings = client.get(f"/applications/{app_id}/findings").json()
        findings.sort(key=lambda f: (SEVERITY_ORDER.get(f["severity"], 3), f["id"]))
        print(f"\n=== FINDINGS ({len(findings)}) ===")
        for f in findings:
            print(f"[{f['severity'].upper():<6}] {f['status']:<24} verify={f['verification_status']:<14} {f['title']}")

        report = client.get(f"/applications/{app_id}/report")
        if report.status_code != 200:
            print("\nNo report was produced.")
            return
        content = report.json()["content"]
        print("\n=== EXECUTIVE SUMMARY ===")
        print(content["executive_summary"])
        print(f"(summary source: {content['executive_summary_source']})")
        overall = content["overall"]
        print("\n=== SCORES (risk / coverage / confidence) ===")
        for d in content["dimensions"].values():
            risk = "n/a" if d["risk_score"] is None else f"{d['risk_score']:.0f} ({d['risk_level']})"
            print(f"{d['label']:<28} risk={risk:<16} coverage={d['coverage'] * 100:.0f}% ({d['reliability']})  "
                  f"confidence={d['confidence']}")
        risk = "not given" if overall["risk_score"] is None else f"{overall['risk_score']:.0f} ({overall['risk_level']})"
        print(f"{'OVERALL':<28} risk={risk:<16} coverage={overall['coverage'] * 100:.0f}% ({overall['reliability']})")
        print("\n=== RECOMMENDED FOLLOW-UPS ===")
        for item in content["recommended_followups"]:
            print(f"- {item}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts\\run_investigation.py <application_id>")
        sys.exit(1)
    main(int(sys.argv[1]))