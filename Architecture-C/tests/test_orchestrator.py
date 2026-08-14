"""
tests/test_orchestrator.py — teste les décisions de routage de
`Orchestrator` DIRECTEMENT, sans passer par un run complet du graphe
(voir tests/test_generator_validator_loop.py et tests/test_repair_loop.py
pour les tests de bout en bout via LangGraph).

Complémentaire, pas redondant : ces tests isolent la LOGIQUE de décision
(un simple if/else pur, sans LLM, sans I/O) de son intégration dans le
graphe -- rapides, déterministes, faciles à étendre si la logique de
routage évolue.
"""
import pytest

from config import settings
from orchestrator import Orchestrator
from schemas import PipelineState, ValidationError, RepairRequest


@pytest.fixture
def orchestrator():
    return Orchestrator()


# --- route_after_generation_validation ------------------------------------

def test_routes_forward_when_no_validation_errors(orchestrator):
    state = PipelineState(user_request="x", validation_errors=[])
    assert orchestrator.route_after_generation_validation(state) == "forward"


def test_routes_to_fix_when_errors_and_budget_remains(orchestrator):
    state = PipelineState(
        user_request="x",
        validation_errors=[ValidationError(rule="x", message="x")],
        iteration_count=0,
    )
    assert orchestrator.route_after_generation_validation(state) == "fix"


def test_routes_forward_when_iteration_budget_exhausted_even_with_errors(orchestrator):
    state = PipelineState(
        user_request="x",
        validation_errors=[ValidationError(rule="x", message="x")],
        iteration_count=settings.MAX_ITERATIONS,
    )
    assert orchestrator.route_after_generation_validation(state) == "forward"


def test_routes_forward_on_blocking_error_regardless_of_validation_errors(orchestrator):
    """Une erreur bloquante prime toujours sur la boucle -- le pipeline
    reste strict sur ce point, même avec ce nouveau mécanisme."""
    state = PipelineState(
        user_request="x",
        error="crash simulé",
        validation_errors=[ValidationError(rule="x", message="x")],
        iteration_count=0,
    )
    assert orchestrator.route_after_generation_validation(state) == "forward"


@pytest.mark.parametrize("iteration_count", [0, 1, settings.MAX_ITERATIONS - 1])
def test_routes_to_fix_at_every_iteration_below_the_bound(orchestrator, iteration_count):
    state = PipelineState(
        user_request="x",
        validation_errors=[ValidationError(rule="x", message="x")],
        iteration_count=iteration_count,
    )
    assert orchestrator.route_after_generation_validation(state) == "fix"


# --- route_after_final_verification ----------------------------------------

def test_routes_end_when_no_repair_requests(orchestrator):
    state = PipelineState(user_request="x", repair_requests=[])
    assert orchestrator.route_after_final_verification(state) == "end"


def test_routes_to_repair_when_requests_and_budget_remains(orchestrator):
    state = PipelineState(
        user_request="x",
        repair_requests=[RepairRequest(
            target_resource="Deployment/x", target_agent="agent2_template",
            missing_constraint="x", reason="x",
        )],
        repair_attempt=0,
    )
    assert orchestrator.route_after_final_verification(state) == "repair"


def test_routes_end_when_repair_budget_exhausted_even_with_requests(orchestrator):
    state = PipelineState(
        user_request="x",
        repair_requests=[RepairRequest(
            target_resource="Deployment/x", target_agent="agent2_template",
            missing_constraint="x", reason="x",
        )],
        repair_attempt=settings.MAX_REPAIR_ATTEMPTS,
    )
    assert orchestrator.route_after_final_verification(state) == "end"


def test_routes_end_on_blocking_error_regardless_of_repair_requests(orchestrator):
    state = PipelineState(
        user_request="x",
        error="crash simulé",
        repair_requests=[RepairRequest(
            target_resource="Deployment/x", target_agent="agent2_template",
            missing_constraint="x", reason="x",
        )],
        repair_attempt=0,
    )
    assert orchestrator.route_after_final_verification(state) == "end"


# --- construction du graphe --------------------------------------------

def test_build_returns_a_cached_compiled_graph(orchestrator):
    g1 = orchestrator.build()
    g2 = orchestrator.build()
    assert g1 is g2, "build() doit mettre le graphe en cache, pas le reconstruire à chaque appel"
