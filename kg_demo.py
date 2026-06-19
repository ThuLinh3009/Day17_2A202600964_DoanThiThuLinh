"""Bonus (§13) — knowledge graph vs vector RAG on a MULTI-HOP question.

    python kg_demo.py

The docs state two facts separately: a widget is an *accessory*, and accessories
ship from *Hanoi*. Answering "where does a widget ship from?" needs BOTH facts
joined. Flat chunk-retrieval RAG can't: no single chunk contains the whole chain.
A knowledge graph can: it walks widget -> accessory -> Hanoi. Zero-key — the
deterministic extractor stands in for an LLM.
"""
from pipeline import config
from pipeline.kg import (
    ingest_docs_to_graph, query, returnable_products, traverse, vector_foil,
)

QUESTION = "Where does a widget ship from?"
SUBJECT, ANSWER_HINT = "widget", "hanoi"


def main() -> dict:
    graph = ingest_docs_to_graph(config.DOCS_DIR)
    print("=== Day 17 bonus: Knowledge Graph vs Vector RAG ===")
    print(f"  nodes (entities): {len(graph)}")
    for node, edges in sorted(graph.items()):
        for rel, obj in edges:
            print(f"    ({node}) -[{rel}]-> ({obj})")

    print(f"\n  Q: {QUESTION!r}")

    # --- Vector RAG foil: the fact is split across chunks ---
    foil = vector_foil(config.DOCS_DIR, SUBJECT, ANSWER_HINT)
    print("\n  [Vector RAG] flat chunk retrieval:")
    print(f"    chunk mentioning '{SUBJECT}' : {foil['chunk_with_subject']!r}")
    print(f"    chunk mentioning '{ANSWER_HINT}'  : {foil['chunk_with_answer']!r}")
    print(f"    one chunk that answers it (has BOTH): {foil['single_chunk_answers_it']}  "
          f"=> flat retrieval CANNOT bridge the two facts")

    # --- Knowledge graph: real multi-hop traversal ---
    hops = traverse(graph, SUBJECT, "SHIPS_FROM")
    print("\n  [Knowledge graph] multi-hop traverse:")
    for h in hops:
        print("    " + "  ->  ".join(h["path"]) + f"   ({h['hops']} hops)  => {h['answer']}")

    # --- the original 1-hop / multi-node queries still work ---
    print("\n  1-hop  widget / RETURNABLE_WITHIN :", query(graph, "widget", "RETURNABLE_WITHIN"))
    print("  multi-node 'what is returnable?'  :", returnable_products(graph))
    return {
        "n_nodes": len(graph),
        "single_chunk_answers_it": foil["single_chunk_answers_it"],
        "multihop_answer": hops[0]["answer"] if hops else None,
        "multihop_hops": hops[0]["hops"] if hops else 0,
    }


if __name__ == "__main__":
    main()
