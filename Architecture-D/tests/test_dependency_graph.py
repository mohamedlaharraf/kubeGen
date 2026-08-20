"""tests/test_dependency_graph.py"""

import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.dependency_graph import find_circular_dependencies, find_dangling_dependencies  # noqa: E402


@dataclass
class _FakeComponent:
    component_name: str
    depends_on: list = field(default_factory=list)


def test_no_cycle_in_simple_chain():
    components = [
        _FakeComponent("gateway", depends_on=["worker"]),
        _FakeComponent("worker", depends_on=["db-proxy"]),
        _FakeComponent("db-proxy", depends_on=[]),
    ]
    assert find_circular_dependencies(components) == []


def test_direct_cycle_is_detected():
    components = [
        _FakeComponent("a", depends_on=["b"]),
        _FakeComponent("b", depends_on=["a"]),
    ]
    cycles = find_circular_dependencies(components)
    assert len(cycles) >= 1
    assert set(cycles[0]) == {"a", "b"}


def test_indirect_cycle_is_detected():
    components = [
        _FakeComponent("a", depends_on=["b"]),
        _FakeComponent("b", depends_on=["c"]),
        _FakeComponent("c", depends_on=["a"]),
    ]
    cycles = find_circular_dependencies(components)
    assert len(cycles) >= 1
    assert {"a", "b", "c"}.issubset(set(cycles[0]))


def test_self_dependency_is_detected():
    components = [_FakeComponent("a", depends_on=["a"])]
    cycles = find_circular_dependencies(components)
    assert len(cycles) == 1


def test_dangling_dependency_is_detected():
    components = [_FakeComponent("a", depends_on=["typo-name"])]
    errors = find_dangling_dependencies(components)
    assert len(errors) == 1
    assert "typo-name" in errors[0]


def test_no_dependencies_is_clean():
    components = [_FakeComponent("a"), _FakeComponent("b")]
    assert find_circular_dependencies(components) == []
    assert find_dangling_dependencies(components) == []
