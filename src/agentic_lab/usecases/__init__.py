"""Use cases — each wires the shared agent loop to a concrete business task,
providing a tool registry, a system prompt, and a deterministic mock policy so
it runs with or without a live LLM."""

from . import product_enrichment, rfq_intake

REGISTRY = {
    "rfq_intake": rfq_intake,
    "product_enrichment": product_enrichment,
}

__all__ = ["rfq_intake", "product_enrichment", "REGISTRY"]
