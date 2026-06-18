"""Domain knowledge base — the store of industry/regulatory knowledge the AI
reasons WITH (CR-0017).

Distinct from memory (reasoning/memory/*, which is the AI's own recalled
experience) and from the per-tenant RAG corpus (bronze_files, the customer's
uploaded data). This is the curated "kho tri thức ngành" — churn benchmarks,
RFM segmentation, retention playbooks, NOV/ROI rules — that lets the AI
generalise ("học 1 hiểu 10").

4-tier source authority per docs/strategic/REASONING_LAYER.md Phần 10.
"""
from .embed import embed_text
from .store import KnowledgeDocument, KnowledgeStore

__all__ = ["KnowledgeDocument", "KnowledgeStore", "embed_text"]
