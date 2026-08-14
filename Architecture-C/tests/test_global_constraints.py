"""Tests unitaires pour utils/global_constraints.py — le filtrage qui
remplace la dépendance à un composant unique par une visibilité ciblée."""
import pytest

from schemas import GlobalConstraint
from utils.global_constraints import filter_constraints, constraints_block


def _gc(scope, text="x", category="security", applies_to=None):
    return GlobalConstraint(text=text, scope=scope, category=category,
                             applies_to=applies_to or [])


def test_all_volumes_applies_to_any_component():
    constraints = [_gc("all_volumes", text="chiffrement au repos")]
    assert filter_constraints("postgres-db", constraints) == constraints
    assert filter_constraints("frontend", constraints) == constraints


def test_all_components_applies_everywhere():
    constraints = [_gc("all_components", text="label team obligatoire")]
    assert filter_constraints("anything", constraints) == constraints
    # Doit aussi s'appliquer aux ressources SANS nom de composant
    # (fragments best-effort issus de unmapped_requirements) -- c'est
    # précisément le cas qui a manqué en production.
    assert filter_constraints(None, constraints) == constraints


def test_specific_only_applies_to_named_components():
    constraints = [_gc("specific", text="rate limiting", applies_to=["api-a", "api-b"])]
    assert filter_constraints("api-a", constraints) == constraints
    assert filter_constraints("api-c", constraints) == []


def test_specific_never_applies_to_unnamed_best_effort_resource():
    """Une ressource sans composant nommé (best-effort) ne peut par
    définition pas être dans une liste `applies_to` explicite -- elle ne
    doit donc PAS hériter d'une contrainte 'specific', contrairement à
    'all_volumes'/'all_containers'/'all_components' (voir test ci-dessus)."""
    constraints = [_gc("specific", text="rate limiting", applies_to=["api-a"])]
    assert filter_constraints(None, constraints) == []


def test_mixed_constraints_filtered_independently():
    global_one = _gc("all_containers", text="seccomp obligatoire")
    specific_other = _gc("specific", text="quota réseau", applies_to=["db"])
    constraints = [global_one, specific_other]

    assert filter_constraints("db", constraints) == constraints
    assert filter_constraints("frontend", constraints) == [global_one]


def test_constraints_block_empty_is_empty_string():
    """Ne pas gonfler le prompt d'un bloc vide quand rien n'est applicable."""
    assert constraints_block([]) == ""


def test_constraints_block_contains_scope_and_text():
    constraints = [_gc("all_volumes", text="chiffrement au repos", category="compliance")]
    block = constraints_block(constraints)
    assert "chiffrement au repos" in block
    assert "all_volumes" in block
    assert "compliance" in block
