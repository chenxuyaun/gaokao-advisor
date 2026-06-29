"""Pydantic models for API request/response."""
from pydantic import BaseModel, Field
from typing import Optional, List


class RecommendRequest(BaseModel):
    province: str = "四川"
    score: int
    category: str = "物理类"
    subject_combo: str = "物化生"
    prefer_city: Optional[str] = None
    prefer_major_category: Optional[str] = None
    max_tuition: Optional[int] = None
    rush_ratio: float = Field(default=0.97, ge=0.80, le=0.99, description="冲刺上限比率")
    safe_ratio: float = Field(default=1.05, ge=1.00, le=1.20, description="稳妥上限比率")


class UniversityInfo(BaseModel):
    id: int
    name: str
    level: Optional[str] = None
    city: Optional[str] = None
    group_name: Optional[str] = None
    min_score: int
    min_rank: Optional[int] = None
    subject_requirement: Optional[str] = None
    major_category: Optional[str] = None
    tuition: Optional[int] = None
    is_sino_foreign: bool = False
    source: Optional[str] = None
    confidence: Optional[str] = None
    notes: Optional[str] = None
    avg_salary: Optional[int] = None
    employment_rate: Optional[float] = None
    career_path: Optional[str] = None
    zhang_xuefeng_comment: Optional[str] = None
    tier: str


class RecommendResponse(BaseModel):
    province: str
    score: int
    category: str
    estimated_rank: Optional[int] = None
    cutoff_score: Optional[int] = None
    special_cutoff: Optional[int] = None
    suggestions: List[UniversityInfo]
    tips: Optional[str] = None
    disclaimer: str = (
        "⚠️ 重要提醒：本系统基于2025年历史录取数据推算，2026年实际录取分数线会有波动。"
        "数据仅供参考，不构成志愿填报建议。最终填报请以四川省教育考试院官方系统为准。"
        "志愿填报关系考生前途，请务必多方核实、慎重决策。"
    )


# === v2: Major-first models ===

class SchoolInfo(BaseModel):
    id: int
    name: str
    level: Optional[str] = None
    city: Optional[str] = None
    min_score: int
    min_rank: Optional[int] = None
    tier: str
    confidence: Optional[str] = "MEDIUM"

class MajorGroup(BaseModel):
    major_category: str
    quality_score: int  # 0-100
    civil_service_note: str  # 考公方向
    growth_note: str  # 就业前景简述
    avg_salary: Optional[int] = None
    employment_rate: Optional[float] = None
    career_path: Optional[str] = None
    zhang_xuefeng_comment: Optional[str] = None
    ai_analysis: Optional[str] = None  # AI-generated career advice
    schools: List[SchoolInfo]

class RecommendV2Request(BaseModel):
    province: str = "四川"
    score: int
    category: str = "物理类"
    subject_combo: str = "物化生"

class RecommendV2Response(BaseModel):
    province: str
    score: int
    category: str
    estimated_rank: Optional[int] = None
    cutoff_score: Optional[int] = None
    majors: List[MajorGroup]
    ai_summary: Optional[str] = None  # Overall AI career advice
    disclaimer: str = (
        "⚠️ 重要提醒：本系统基于2025年历史录取数据推算，2026年实际录取分数线会有波动。"
        "数据仅供参考，不构成志愿填报建议。最终填报请以四川省教育考试院官方系统为准。"
    )
