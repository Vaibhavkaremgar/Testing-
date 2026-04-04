import json

from ats.evaluation import run_resume_format_benchmark


if __name__ == "__main__":
    result = run_resume_format_benchmark()
    print(json.dumps(result, indent=2))
