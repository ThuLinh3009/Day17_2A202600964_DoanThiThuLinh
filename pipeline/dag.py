"""A tiny pure-Python DAG runner — the lite-path orchestrator.

No Airflow needed to learn the *shape* of a DAG: tasks with declared upstream
deps, run in topological order, each task's return value passed to dependents.
The Docker bonus track swaps this for a real Airflow 3 DAG with the same stages.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class Task:
    name: str
    fn: Callable
    upstream: list[str] = field(default_factory=list)


class DAG:
    def __init__(self) -> None:
        self.tasks: dict[str, Task] = {}

    def task(self, name: str, upstream: list[str] | None = None):
        def deco(fn: Callable) -> Callable:
            self.tasks[name] = Task(name, fn, upstream or [])
            return fn
        return deco

    def _topo(self) -> list[str]:
        order, seen = [], set()

        def visit(n: str, stack: tuple[str, ...]) -> None:
            if n in order:
                return
            if n in stack:
                raise ValueError(f"cycle through {n}")
            for up in self.tasks[n].upstream:
                visit(up, stack + (n,))
            order.append(n)

        for name in self.tasks:
            visit(name, ())
        return order

    def run(self) -> dict:
        results: dict = {}
        for name in self._topo():
            t = self.tasks[name]
            args = [results[u] for u in t.upstream]
            results[name] = t.fn(*args)
        return results
