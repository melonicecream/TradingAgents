from enum import Enum
from typing import List, Optional, Dict
from pydantic import BaseModel


class AnalystType(str, Enum):
    MARKET = "market"
    SOCIAL = "social"
    NEWS = "news"
    FUNDAMENTALS = "fundamentals"


class Language(str, Enum):
    ENGLISH = "English"
    KOREAN = "한국어"
    JAPANESE = "日本語"
    CHINESE = "中文"
    SPANISH = "Español"
