"""Start an investigation and watch it finish.

Usage (server must be running):  python scripts\\run_investigation.py <application_id>
"""
import sys
import time

import httpx

BASE_URL = "http://127.0.0.1:8000"


def main(app_id: int) -> None:
    with httpx.Client(base_url=BASE_URL, timeout=60) as client:
        client.post(f"/applications/{app_id}/investigate?force=true").raise_for_status()
        print("Investigation started...")
        while True:
            time.sleep(2)
            info = client.get(f"/applications/{app_id}/investigation").json()
            runs = ", ".join(f"{r['agent_name']}={r['status']}" for r in info["agent_runs"])
            print(f"status={info['status']:<14} {runs}")
            if info["status"] != "investigating":
                break

        for run in info["agent_runs"]:
            if run["error"]:
                print(f"ERROR in {run['agent_name']}: {run['error']}")
            for warning in (run["output"] or {}).get("warnings", []):
                print(f"WARNING: {warning}")

        print(f"\nclaims={info['claim_count']}  evidence={info['evidence_count']}\n")
        for claim in client.get(f"/applications/{app_id}/claims").json():
            print(
                f"- [{claim['category']}] {claim['claim_text']}\n"
                f"    value={claim['value']} {claim['unit'] or ''}  "
                f"baseline={claim['baseline_period']}  page={claim['page_number']}"
            )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts\\run_investigation.py <application_id>")
        sys.exit(1)
    main(int(sys.argv[1]))