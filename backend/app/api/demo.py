"""One-click demo cases: loads the synthetic sample_data folders as real applications."""
import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from app.core.database import get_db
from app.models.models import Application, Organization
from app.services.documents import store_upload

ROOT = Path(__file__).resolve().parent.parent.parent / "sample_data"
router = APIRouter(prefix="/demo", tags=["demo"])


def _read_cases() -> list[dict]:
    cases = []
    if not ROOT.exists():
        return cases
    for folder in sorted(ROOT.iterdir()):
        info_file = folder / "case_info.json"
        if folder.is_dir() and info_file.exists():
            info = json.loads(info_file.read_text(encoding="utf-8"))
            cases.append(
                {
                    "slug": folder.name,
                    "company": info["company"],
                    "sector": info.get("sector"),
                    "location": info.get("location"),
                    "project": info["project"],
                    "requested_amount_pkr": info["requested_amount_pkr"],
                    "documents": info["documents"],
                }
            )
    return cases


@router.get("/cases")
def list_cases():
    return _read_cases()


@router.post("/{slug}/load", status_code=201)
def load_case(slug: str, db: Session = Depends(get_db)):
    folder = (ROOT / slug).resolve()
    if folder.parent != ROOT.resolve() or not (folder / "case_info.json").exists():
        raise HTTPException(404, "Demo case not found")
    info = json.loads((folder / "case_info.json").read_text(encoding="utf-8"))

    org = Organization(
        name=info["company"], sector=info.get("sector"), location=info.get("location"), country="Pakistan"
    )
    db.add(org)
    db.flush()
    application = Application(
        organization_id=org.id,
        title=f"Green financing application - {info['company']}",
        project_description=info["project"],
        requested_amount=info["requested_amount_pkr"],
        currency="PKR",
    )
    db.add(application)
    db.commit()
    db.refresh(application)

    for name in info["documents"]:
        with open(folder / name, "rb") as handle:
            store_upload(db, application, UploadFile(file=handle, filename=name), None)
    return {"application_id": application.id}