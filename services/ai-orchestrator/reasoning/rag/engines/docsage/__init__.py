"""DocSage engine — structured-SQL multi-entity RAG (P15-S11 D3-D6).

Composed of 4 collaborating modules + glue:

  types.py            — SchemaDefinition + Row + Citation Pydantic shapes
  prompts.py          — Vietnamese prompts (versioned)
  schema_discovery.py — Schema Discovery (D3)
  extraction.py       — Structured Extraction (D4)
  sql_reasoning.py    — SQL Reasoning + executor (D5)
  __init__.py         — glue: DocSageEngine.answer() (D6 lands at the router)

Public API:
  from ai_orchestrator.reasoning.rag.engines.docsage import DocSageEngine
"""
from .types import (
    Citation,
    Column,
    JoinKey,
    Row,
    SchemaDefinition,
    Table,
)
from .schema_discovery import SchemaDiscovery, corpus_hash_of
from .extraction import ExtractionResult, StructuredExtraction
from .sql_reasoning import SQLAnswer, SQLReasoning
from .engine import DocSageEngine

__all__ = [
    "Citation",
    "Column",
    "DocSageEngine",
    "ExtractionResult",
    "JoinKey",
    "Row",
    "SchemaDefinition",
    "SchemaDiscovery",
    "SQLAnswer",
    "SQLReasoning",
    "StructuredExtraction",
    "Table",
    "corpus_hash_of",
]
