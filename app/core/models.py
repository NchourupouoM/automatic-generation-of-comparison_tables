import datetime
import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy import String, Text, TIMESTAMP, ForeignKey, Boolean, Integer, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class TemplateModel(Base):
    """
    Represents the 'templates' table.
    Stores domain-specific schemas (JSON Schema) curated by humans or generated on-demand.
    """
    __tablename__ = "templates"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    schema_json: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))

    comparison_tables: Mapped[List["ComparisonTableModel"]] = relationship(
        "ComparisonTableModel", 
        back_populates="template"
    )


class ValidationTaskModel(Base):
    """
    Represents the 'validation_tasks' table.
    Acts as a persistent sequential buffer (FIFO queue) for Human-In-The-Loop schema creation.
    """
    __tablename__ = "validation_tasks"

    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING_SCHEMA_VALIDATION")
    proposed_properties: Mapped[Optional[List[Dict[str, str]]]] = mapped_column(JSONB, nullable=True)
    raw_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    document_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, default="single")
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))

    # AJOUT RELATION : Liaison en cascade vers l'ensemble des fragments (chunks) du proceeding [3]
    chunks: Mapped[List["ProceedingChunkModel"]] = relationship(
        "ProceedingChunkModel",
        back_populates="validation_task",
        cascade="all, delete-orphan",
        passive_deletes=True
    )


# ===========================================================================
# NOUVELLE TABLE : Proceeding Chunks (Stockage persistant des fragments) [3]
# ===========================================================================
class ProceedingChunkModel(Base):
    """
    Represents the 'proceeding_chunks' table.
    Persists the isolated markdown text segments of each paper in a proceeding [3].
    """
    __tablename__ = "proceeding_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("validation_tasks.task_id", ondelete="CASCADE"), 
        nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    authors: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    text_segment: Mapped[str] = mapped_column(Text, nullable=False)  # Le texte brut de ce fragment précis [3]
    domain_hint: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))

    # Relation inverse
    validation_task: Mapped[ValidationTaskModel] = relationship(
        "ValidationTaskModel", 
        back_populates="chunks"
    )


class ComparisonTableModel(Base):
    """
    Represents the 'comparison_tables' table.
    Groups comparative rows aligned under a shared research problem context.
    """
    __tablename__ = "comparison_tables"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    research_problem: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[Optional[str]] = mapped_column(String(100), ForeignKey("templates.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))

    template: Mapped[Optional[TemplateModel]] = relationship("TemplateModel", back_populates="comparison_tables")
    rows: Mapped[List["ExtractedRowModel"]] = relationship(
        "ExtractedRowModel", 
        back_populates="comparison_table", 
        cascade="all, delete-orphan", 
        passive_deletes=True
    )


class PaperEntityModel(Base):
    """
    Represents the 'paper_entities' table — the canonical, de-duplicated identity
    of a paper. The same baseline cited across many comparison tables resolves to
    a single entity here, turning a pile of isolated tables into a linked graph.
    """
    __tablename__ = "paper_entities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Deterministic identity key: normalized DOI if present, else a slug of the title.
    canonical_key: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    canonical_title: Mapped[str] = mapped_column(String(500), nullable=False)
    authors: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    doi: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    mention_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))

    mentions: Mapped[List["ExtractedRowModel"]] = relationship(
        "ExtractedRowModel", back_populates="entity"
    )


class ExtractedRowModel(Base):
    """
    Represents the 'extracted_rows' table.
    Captures both bibliographic and dynamic clinical/dietary variables (Phi) of a paper.
    """
    __tablename__ = "extracted_rows"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    table_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("comparison_tables.id", ondelete="CASCADE"), nullable=False)
    paper_title: Mapped[str] = mapped_column(String(500), nullable=False)
    authors: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)
    is_proposed_method: Mapped[bool] = mapped_column(Boolean, default=False)
    bibliographic_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    domain_properties: Mapped[Dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # Grounding: list of {field, quote} verbatim source excerpts for this row.
    evidence: Mapped[Optional[List[Dict[str, str]]]] = mapped_column(JSONB, nullable=True)
    # Entity resolution: canonical paper this row is a mention of.
    entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("paper_entities.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(TIMESTAMP, server_default=text("CURRENT_TIMESTAMP"))

    comparison_table: Mapped["ComparisonTableModel"] = relationship("ComparisonTableModel", back_populates="rows")
    entity: Mapped[Optional["PaperEntityModel"]] = relationship("PaperEntityModel", back_populates="mentions")