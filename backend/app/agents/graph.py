"""Central investigation engine (LangGraph).

Day 3 graph:  intake_check -> (conditional) -> document_intelligence -> finalize
Later days plug the other agents in between, using the same state and run_agent helper.
"""
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from app.agents import document_intelligence
from app.agents.base import reset_investigation, run_agent
from app.core.database import SessionLocal
from app.models.models import Application, Document

EXPECTED_DOC_TYPES = ["sustainability_report", "energy_records", "production_data", "financial_statement"]


class InvestigationState(TypedDict, total=False):
    application_id: int
    status: str
    coverage: dict


def intake_check(state: InvestigationState) -> dict:
    app_id = state["application_id"]
    with SessionLocal() as db:
        reset_investigation(db, app_id)
        docs = db.scalars(select(Document).where(Document.application_id == app_id)).all()
        processed = [d for d in docs if d.status == "processed"]
        present = sorted({d.doc_type for d in processed})
        coverage = {
            "documents_total": len(docs),
            "documents_processed": len(processed),
            "present_types": present,
            "missing_types": [t for t in EXPECTED_DOC_TYPES if t not in present],
        }
        application = db.get(Application, app_id)
        application.status = "investigating"
        db.commit()
        run_agent(db, app_id, "orchestrator", "intake check: which evidence is available?", lambda: coverage)
    return {"coverage": coverage, "status": "investigating" if processed else "insufficient_information"}


def route_after_intake(state: InvestigationState) -> str:
    return "document_intelligence" if state.get("status") == "investigating" else "finalize"


def document_intelligence_node(state: InvestigationState) -> dict:
    app_id = state["application_id"]
    with SessionLocal() as db:
        run_agent(
            db,
            app_id,
            "document_intelligence",
            "extract claims, figures and tables with source references",
            lambda: document_intelligence.run(db, app_id),
        )
    return {}


def finalize(state: InvestigationState) -> dict:
    app_id = state["application_id"]
    with SessionLocal() as db:
        application = db.get(Application, app_id)
        # Interim status for Day 3; later days replace this with "completed" once a report exists.
        application.status = "extracted" if state.get("status") == "investigating" else "completed"
        db.commit()
    return {}


def build_graph():
    graph = StateGraph(InvestigationState)
    graph.add_node("intake_check", intake_check)
    graph.add_node("document_intelligence", document_intelligence_node)
    graph.add_node("finalize", finalize)
    graph.add_edge(START, "intake_check")
    graph.add_conditional_edges(
        "intake_check",
        route_after_intake,
        {"document_intelligence": "document_intelligence", "finalize": "finalize"},
    )
    graph.add_edge("document_intelligence", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


GRAPH = build_graph()


def run_investigation(application_id: int) -> dict:
    return GRAPH.invoke({"application_id": application_id})