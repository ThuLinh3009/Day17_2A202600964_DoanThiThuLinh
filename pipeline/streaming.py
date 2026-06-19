"""In-memory streaming simulation — the lite path for the Kafka track.

Models the core Kafka idea (producer -> topic -> consumer) with a plain queue,
so students see partitioning-by-key, at-least-once redelivery, and idempotent
consumption without standing up a broker. The Docker bonus swaps this for
Redpanda/Kafka with the identical consumer logic.
"""
from __future__ import annotations
from collections import defaultdict, deque


class MiniTopic:
    """A partitioned, replayable log. Partition by key -> per-key ordering."""

    def __init__(self, partitions: int = 3) -> None:
        self.partitions = [deque() for _ in range(partitions)]

    def produce(self, key: str, value: dict) -> None:
        p = hash(key) % len(self.partitions)
        self.partitions[p].append({"key": key, "value": value})

    def __iter__(self):
        for part in self.partitions:
            yield from part


def consume_features(topic: MiniTopic) -> dict:
    """Idempotent consumer: maintains a per-user running feature, dedups on a
    seen-set of event ids so replays are safe (at-least-once -> effectively-once)."""
    seen: set[str] = set()
    features: dict[str, dict] = defaultdict(lambda: {"orders": 0, "spend": 0.0})
    for msg in topic:
        ev = msg["value"]
        if ev["event_id"] in seen:        # idempotency guard
            continue
        seen.add(ev["event_id"])
        f = features[msg["key"]]
        f["orders"] += 1
        f["spend"] = round(f["spend"] + float(ev["amount"]), 2)
    return dict(features)
