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
