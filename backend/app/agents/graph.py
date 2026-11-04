"""Central investigation engine (LangGraph).

intake_check -> document_intelligence -> [financial | taxonomy | greenwashing] (parallel) -> consolidate -> finalize
Later days add climate risk, adversarial verification and the decision agent to this same graph.
"""
from collections import Counter
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from app.agents import document_intelligence, financial, greenwashing, taxonomy
from app.agents.base import reset_investigation, run_agent
from app.core.database import SessionLocal
from app.models.models import Application, Document, Finding

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


def make_agent_node(agent_name: str, task: str, module):
    def node(state: InvestigationState) -> dict:
        app_id = state["application_id"]
        with SessionLocal() as db:
            run_agent(db, app_id, agent_name, task, lambda: module.run(db, app_id))
        return {}

    return node


def consolidate(state: InvestigationState) -> dict:
    app_id = state["application_id"]
    with SessionLocal() as db:
        findings = db.scalars(select(Finding).where(Finding.application_id == app_id)).all()

        def summary() -> dict:
            return {
                "findings_total": len(findings),
                "by_status": dict(Counter(f.status for f in findings)),
                "by_severity": dict(Counter(f.severity for f in findings)),
                "by_agent": dict(Counter(f.agent_name for f in findings)),
                "needs_verification": [
                    f.id for f in findings
                    if f.severity == "high" or f.status in ("contradictory", "potential_anomaly")
                ],
                "missing_document_types": state.get("coverage", {}).get("missing_types", []),
            }

        run_agent(db, app_id, "orchestrator", "consolidate findings; flag items for adversarial review", summary)
    return {}


def finalize(state: InvestigationState) -> dict:
    app_id = state["application_id"]
    with SessionLocal() as db:
        application = db.get(Application, app_id)
        # Interim status: later days replace this with "completed" once a report exists.
        application.status = "analysed" if state.get("status") == "investigating" else "completed"
        db.commit()
    return {}


def build_graph():
    graph = StateGraph(InvestigationState)
    graph.add_node("intake_check", intake_check)
    graph.add_node(
        "document_intelligence",
        make_agent_node("document_intelligence", "extract claims, figures and tables with source references",
                        document_intelligence),
    )
    graph.add_node(
        "financial_intelligence",
        make_agent_node("financial_intelligence", "calculate financial indicators and flag exceptions", financial),
    )
    graph.add_node(
        "green_taxonomy",
        make_agent_node("green_taxonomy", "screen the project against the green criteria set", taxonomy),
    )
    graph.add_node(
        "greenwashing_detection",
        make_agent_node("greenwashing_detection", "check claims against baselines, methods and records",
                        greenwashing),
    )
    graph.add_node("consolidate", consolidate)
    graph.add_node("finalize", finalize)

    graph.add_edge(START, "intake_check")
    graph.add_conditional_edges(
        "intake_check",
        route_after_intake,
        {"document_intelligence": "document_intelligence", "finalize": "finalize"},
    )
    for node in ("financial_intelligence", "green_taxonomy", "greenwashing_detection"):
        graph.add_edge("document_intelligence", node)
    graph.add_edge(["financial_intelligence", "green_taxonomy", "greenwashing_detection"], "consolidate")
    graph.add_edge("consolidate", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


GRAPH = build_graph()


def run_investigation(application_id: int) -> dict:
    return GRAPH.invoke({"application_id": application_id})