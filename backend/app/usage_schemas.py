from typing import Dict

from pydantic import BaseModel


class UsageMetricSummary(BaseModel):
    total: int
    used: int
    remaining: int


UsageSummaryResponse = Dict[str, UsageMetricSummary]
