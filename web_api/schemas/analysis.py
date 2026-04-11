"""
Pydantic v2 schemas for Analysis History API.
"""

from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, List, Dict, Any


class ReportsData(BaseModel):
    market: str = ""
    sentiment: str = ""
    news: str = ""
    fundamentals: str = ""


class ResearchData(BaseModel):
    investment_plan: str = ""
    trader_plan: str = ""
    bull_history: str = ""
    bear_history: str = ""


class RiskData(BaseModel):
    aggressive: str = ""
    conservative: str = ""
    neutral: str = ""
    final_decision: str = ""


class AnalysisHistoryBase(BaseModel):
    ticker: str
    analysis_date: str
    decision: str
    full_decision: Optional[str] = None


class AnalysisHistoryCreate(AnalysisHistoryBase):
    reports: Optional[ReportsData] = None
    research: Optional[ResearchData] = None
    risk: Optional[RiskData] = None


class AnalysisHistoryResponse(AnalysisHistoryBase):
    id: int
    reports: Optional[Dict[str, Any]] = None
    research: Optional[Dict[str, Any]] = None
    risk: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AnalysisHistoryList(BaseModel):
    items: List[AnalysisHistoryResponse]
    total: int
    page: int
    page_size: int


class PaginatedResponse(BaseModel):
    items: List[AnalysisHistoryResponse]
    total: int
    page: int
    page_size: int
    pages: int


class AnalysisExecutionResponse(BaseModel):
    id: int
    ticker: str
    analysis_date: str
    status: str
    progress: float
    current_stage: Optional[str] = None
    last_completed_milestone: Optional[str] = None
    current_milestone: Optional[str] = None
    retry_count: int
    resume_count: int
    decision: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedExecutionResponse(BaseModel):
    items: List[AnalysisExecutionResponse]
    total: int
    page: int
    page_size: int
    pages: int


class EngineInfoResponse(BaseModel):
    provider: str
    deep_model: str
    quick_model: str
    backend_url: str
    language: str
    selected_analyst_count: int
    fixed_agent_count: int
    total_agent_count: int
    cli_total_agent_count: int
    agent_count_matches_cli: bool
    supports_korean_summary: bool
    engine_explanation: str


class SystemStatsResponse(BaseModel):
    concurrent_runs: int
    running_executions: int
    resumable_executions: int
    failed_executions: int
    completed_executions: int
    total_executions: int
    active_leases: int


class ExecutionStepTimingResponse(BaseModel):
    milestone: str
    label: str
    completed_at: datetime
    elapsed_seconds: float


class ExecutionDetailResponse(AnalysisExecutionResponse):
    analysts: List[str]
    reports: Optional[Dict[str, Any]] = None
    research: Optional[Dict[str, Any]] = None
    risk: Optional[Dict[str, Any]] = None
    summary_report: Optional[str] = None
    started_at: datetime
    updated_at: Optional[datetime] = None
    elapsed_seconds: float
    workflow_steps: List[ExecutionStepTimingResponse]
