from __future__ import annotations

import json

from ats.evaluation import run_resume_parsing_benchmark


if __name__ == "__main__":
    result = run_resume_parsing_benchmark()
    print(json.dumps(result, indent=2, ensure_ascii=True))
