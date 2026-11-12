"""Central investigation engine (LangGraph).

intake_check -> document_intelligence -> [financial | taxonomy | greenwashing | climate] (parallel)
 -> consolidate -> adversarial_verification -> (targeted_reassessment -> adversarial_verification)* 
 -> decision_intelligence -> finalize
"""
from collections import Counter
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import select

from app.agents import (
    adversarial,
    climate,
    decision,
    document_intelligence,
    financial,
    greenwashing,
    taxonomy,
)
from app.agents.base import reset_investigation, run_agent
from app.core.database import SessionLocal
from app.models.models import Application, Document, Finding

EXPECTED_DOC_TYPES = ["sustainability_report", "energy_records", "production_data", "financial_statement"]
MAX_REASSESSMENT_ROUNDS = 1


class InvestigationState(TypedDict, total=False):
    application_id: int
    status: str
    coverage: dict
    reassess: bool
    reassess_round: int


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
    return {
        "coverage": coverage,
        "status": "investigating" if processed else "insufficient_information",
        "reassess": False,
        "reassess_round": 0,
    }


def route_after_intake(state: InvestigationState) -> str:
    return "document_intelligence" if state.get("status") == "investigating" else "decision_intelligence"


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


def verification_node(state: InvestigationState) -> dict:
    app_id = state["application_id"]
    allow = state.get("reassess_round", 0) < MAX_REASSESSMENT_ROUNDS
    with SessionLocal() as db:
        out = run_agent(
            db, app_id, "adversarial_verification",
            "challenge high-impact findings; test alternative explanations",
            lambda: adversarial.run(db, app_id, allow),
        )
    return {"reassess": bool(out.get("reassess_claim_ids")) and allow}


def route_after_verification(state: InvestigationState) -> str:
    return "targeted_reassessment" if state.get("reassess") else "decision_intelligence"


def targeted_reassessment_node(state: InvestigationState) -> dict:
    app_id = state["application_id"]
    with SessionLocal() as db:
        run_agent(db, app_id, "green_taxonomy",
                  "targeted reassessment after verification updated a claim",
                  lambda: taxonomy.run(db, app_id))
        run_agent(db, app_id, "greenwashing_detection",
                  "targeted reassessment after verification updated a claim",
                  lambda: greenwashing.run(db, app_id))
    return {"reassess": False, "reassess_round": state.get("reassess_round", 0) + 1}


def finalize(state: InvestigationState) -> dict:
    app_id = state["application_id"]
    with SessionLocal() as db:
        application = db.get(Application, app_id)
        application.status = "completed"
        db.commit()
    return {}


def build_graph():
    graph = StateGraph(InvestigationState)
    graph.add_node("intake_check", intake_check)
    graph.add_node("document_intelligence", make_agent_node(
        "document_intelligence", "extract claims, figures and tables with source references", document_intelligence))
    graph.add_node("financial_intelligence", make_agent_node(
        "financial_intelligence", "calculate financial indicators and flag exceptions", financial))
    graph.add_node("green_taxonomy", make_agent_node(
        "green_taxonomy", "screen the project against the green criteria set", taxonomy))
    graph.add_node("greenwashing_detection", make_agent_node(
        "greenwashing_detection", "check claims against baselines, methods and records", greenwashing))
    graph.add_node("climate_risk", make_agent_node(
        "climate_risk", "screen physical and transition climate exposure", climate))
    graph.add_node("consolidate", consolidate)
    graph.add_node("adversarial_verification", verification_node)
    graph.add_node("targeted_reassessment", targeted_reassessment_node)
    graph.add_node("decision_intelligence", make_agent_node(
        "decision_intelligence", "score dimensions and write the investigation report", decision))
    graph.add_node("finalize", finalize)

    graph.add_edge(START, "intake_check")
    graph.add_conditional_edges(
        "intake_check", route_after_intake,
        {"document_intelligence": "document_intelligence", "decision_intelligence": "decision_intelligence"},
    )
    parallel = ["financial_intelligence", "green_taxonomy", "greenwashing_detection", "climate_risk"]
    for node in parallel:
        graph.add_edge("document_intelligence", node)
    graph.add_edge(parallel, "consolidate")
    graph.add_edge("consolidate", "adversarial_verification")
    graph.add_conditional_edges(
        "adversarial_verification", route_after_verification,
        {"targeted_reassessment": "targeted_reassessment", "decision_intelligence": "decision_intelligence"},
    )
    graph.add_edge("targeted_reassessment", "adversarial_verification")
    graph.add_edge("decision_intelligence", "finalize")
    graph.add_edge("finalize", END)
    return graph.compile()


GRAPH = build_graph()


def run_investigation(application_id: int) -> dict:
    return GRAPH.invoke({"application_id": application_id})