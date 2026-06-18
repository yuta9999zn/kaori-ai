"""DocSage Pydantic shapes.

Shared by all 4 modules (Schema Discovery / Extraction / SQL Reasoning /
Engine assembly). Validated by Issue #3 output_schema on every LLM call
so a model never returns "almost-JSON" — it returns a parsed dict that
already matches the model.

Naming convention: all names match the spec in
docs/specs/RAG_VECTORLESS_AND_STRUCTURED.md §4.3.
"""
from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ─── Schema (output of D3) ──────────────────────────────────────────


class Column(BaseModel):
    """One column inside a `Table`. Bounded vocab on `sql_type` so D5
    can spin up the TEMP table without trusting LLM-emitted SQL types."""
    name:      str  = Field(..., max_length=32)
    sql_type:  str  = Field(..., max_length=16)
    nullable:  bool = True
    role:      str  = Field(..., max_length=16)
    fk_target: Optional[str] = Field(default=None, max_length=64)

    @field_validator("sql_type")
    @classmethod
    def _sql_type_in_vocab(cls, v: str) -> str:
        allowed = {"TEXT", "INTEGER", "NUMERIC", "DATE", "TIMESTAMP", "BOOLEAN"}
        if v.upper() not in allowed:
            raise ValueError(f"sql_type must be one of {sorted(allowed)}; got {v!r}")
        return v.upper()

    @field_validator("role")
    @classmethod
    def _role_in_vocab(cls, v: str) -> str:
        allowed = {"key", "attribute", "measure", "fk"}
        if v not in allowed:
            raise ValueError(f"role must be one of {sorted(allowed)}; got {v!r}")
        return v

    @field_validator("name")
    @classmethod
    def _name_is_identifier(cls, v: str) -> str:
        # snake_case ASCII identifier — defence-in-depth before D5
        # interpolates into CREATE TEMP TABLE.
        if not v or not v.replace("_", "").isalnum() or not v[0].isalpha():
            raise ValueError(f"column name must be snake_case alnum; got {v!r}")
        return v.lower()


class Table(BaseModel):
    name:    str           = Field(..., max_length=32)
    columns: list[Column]  = Field(..., min_length=1, max_length=12)

    @field_validator("name")
    @classmethod
    def _name_is_identifier(cls, v: str) -> str:
        if not v or not v.replace("_", "").isalnum() or not v[0].isalpha():
            raise ValueError(f"table name must be snake_case alnum; got {v!r}")
        return v.lower()


class JoinKey(BaseModel):
    """One join between two tables in the discovered schema. D5 walks
    these to pick the right ON clause when composing SQL."""
    left_table:  str = Field(..., max_length=32)
    left_column: str = Field(..., max_length=32)
    right_table: str = Field(..., max_length=32)
    right_column: str = Field(..., max_length=32)


class SchemaDefinition(BaseModel):
    """D3 output. Cached row in docsage_schemas; D4 reads it before
    per-doc extraction; D5 reads it to compose SQL."""
    tables:         list[Table]    = Field(..., min_length=1, max_length=5)
    join_keys:      list[JoinKey]  = Field(default_factory=list, max_length=10)
    question_class: str            = Field(..., max_length=20)

    @field_validator("question_class")
    @classmethod
    def _class_in_vocab(cls, v: str) -> str:
        # Matches mig 066 chk_docsage_question_class.
        allowed = {"comparison", "aggregation", "relationship", "ranking"}
        if v not in allowed:
            raise ValueError(f"question_class must be one of {sorted(allowed)}; got {v!r}")
        return v


# ─── Extraction (output of D4) ──────────────────────────────────────


class Row(BaseModel):
    """One extracted entity-row, tagged with the table it belongs to
    and the source segment for citations."""
    table:          str                  = Field(..., max_length=32)
    values:         dict[str, Any]
    source_segment: Optional[tuple[int, int]] = None   # (page_from, page_to)


# ─── Answer (output of D5) ──────────────────────────────────────────


class Citation(BaseModel):
    """Source attribution attached to every DocSage answer. Mirrors the
    base Citation in reasoning/rag/engines/base.py but tightens the
    engine field to 'docsage'."""
    engine:      str
    doc_id:      str
    source_segment: Optional[tuple[int, int]] = None
    sql_query:   Optional[str] = None
    table_names: list[str]     = Field(default_factory=list)
