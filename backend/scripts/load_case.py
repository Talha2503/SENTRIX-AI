"""Load a synthetic sample case into a running SENTRIX backend.

Usage (server must be running):  python scripts\\load_case.py case_b_unsupported_claim
"""
import json
import sys
from pathlib import Path

import httpx

BASE_URL = "http://127.0.0.1:8000"
ROOT = Path(__file__).resolve().parent.parent / "sample_data"


def main(slug: str) -> None:
    folder = ROOT / slug
    info = json.loads((folder / "case_info.json").read_text(encoding="utf-8"))

    payload = {
        "organization": {
            "name": info["company"],
            "sector": info["sector"],
            "location": info["location"],
            "country": "Pakistan",
        },
        "title": f"Green financing application - {info['company']}",
        "project_description": info["project"],
        "requested_amount": info["requested_amount_pkr"],
        "currency": "PKR",
    }

    with httpx.Client(base_url=BASE_URL, timeout=120) as client:
        response = client.post("/applications", json=payload)
        response.raise_for_status()
        application = response.json()
        print(f"Created application #{application['id']}: {application['title']}")

        for name in info["documents"]:
            with open(folder / name, "rb") as f:
                response = client.post(
                    f"/applications/{application['id']}/documents",
                    files={"file": (name, f)},
                )
            response.raise_for_status()
            doc = response.json()
            print(f"  uploaded {doc['filename']:<32} type={doc['doc_type']:<22} "
                  f"status={doc['status']} pages={doc['page_count']}")

    print(f"Done. Open {BASE_URL}/applications/{application['id']}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python scripts\\load_case.py <case_folder_name>")
        sys.exit(1)
    main(sys.argv[1])