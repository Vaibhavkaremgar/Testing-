from typing import Dict, Optional

from pydantic import BaseModel


class UsageMetricSummary(BaseModel):
    total: Optional[int] = None
    used: int
    remaining: Optional[int] = None
    unlimited: bool = False


UsageSummaryResponse = Dict[str, UsageMetricSummary]
