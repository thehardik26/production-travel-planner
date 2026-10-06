# Phase 6 - hybrid retrieval over a small destination-guide knowledge
# base. Modules:
#   embeddings.py        local (BAAI/bge-small-en-v1.5) dense embeddings
#   chunking.py           paragraph-aware chunking of guide text
#   knowledge_base.py     the seed corpus itself (SEED_KNOWLEDGE)
#   retrieval.py           HybridRetriever: dense (Qdrant) + BM25 + RRF fusion
#   reranking.py           cross-encoder (BAAI/bge-reranker-base) reranking
#   ingest.py              startup seeding (see app/main.py's lifespan)
#   destination_guide.py   the function ResearchAgent actually calls
