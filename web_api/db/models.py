"""SQLAlchemy models for TradingAgents database."""

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.sql import func

from web_api.db.database import Base


class AnalysisHistory(Base):
    """Store analysis history for quick retrieval."""

    __tablename__ = "analysis_history"

    id = Column(Integer, primary_key=True, index=True)
    ticker = Column(String, index=True, nullable=False)
    analysis_date = Column(String, index=True, nullable=False)
    decision = Column(String, nullable=False)
    full_decision = Column(Text, nullable=True)

    # Reports stored as JSON for flexibility
    reports = Column(JSON, nullable=True)
    research = Column(JSON, nullable=True)
    risk = Column(JSON, nullable=True)

    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return f"<AnalysisHistory(ticker='{self.ticker}', date='{self.analysis_date}', decision='{self.decision}')>"


class AnalysisExecution(Base):
    """Store resumable web API execution metadata."""

    __tablename__ = "analysis_executions"

    id = Column(Integer, primary_key=True, index=True)
    execution_key = Column(String, unique=True, index=True, nullable=False)
    thread_id = Column(String, unique=True, index=True, nullable=False)
    ticker = Column(String, index=True, nullable=False)
    analysis_date = Column(String, index=True, nullable=False)
    analysts_json = Column(JSON, nullable=False)
    config_hash = Column(String, index=True, nullable=False)
    graph_version = Column(String, nullable=False)
    checkpoint_schema_version = Column(String, nullable=False)
    status = Column(String, index=True, nullable=False)
    retry_count = Column(Integer, nullable=False, default=0, server_default="0")
    resume_count = Column(Integer, nullable=False, default=0, server_default="0")
    last_completed_milestone = Column(String, nullable=True)
    current_milestone = Column(String, nullable=True)
    last_error_type = Column(String, nullable=True)
    last_error_message = Column(Text, nullable=True)
    lease_owner = Column(String, index=True, nullable=True)
    lease_expires_at = Column(DateTime(timezone=True), index=True, nullable=True)
    analysis_history_id = Column(
        Integer,
        ForeignKey("analysis_history.id"),
        unique=True,
        index=True,
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def __repr__(self):
        return (
            "<AnalysisExecution("
            f"execution_key='{self.execution_key}', ticker='{self.ticker}', status='{self.status}'"
            ")>"
        )


class AnalysisCheckpoint(Base):
    """Store durable milestone checkpoints for an execution."""

    __tablename__ = "analysis_checkpoints"
    __table_args__ = (
        UniqueConstraint(
            "execution_id",
            "milestone",
            name="uq_analysis_checkpoints_execution_milestone",
        ),
        UniqueConstraint(
            "execution_id",
            "milestone",
            "checkpoint_id",
            name="uq_analysis_checkpoints_execution_milestone_checkpoint",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    execution_id = Column(
        Integer,
        ForeignKey("analysis_executions.id"),
        index=True,
        nullable=False,
    )
    milestone = Column(String, nullable=False)
    checkpoint_id = Column(String, nullable=False)
    checkpoint_ns = Column(String, nullable=False, default="", server_default="")
    step_index = Column(Integer, nullable=False)
    summary_json = Column(JSON, nullable=True)
    status = Column(String, index=True, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return (
            "<AnalysisCheckpoint("
            f"execution_id='{self.execution_id}', milestone='{self.milestone}', checkpoint_id='{self.checkpoint_id}'"
            ")>"
        )
