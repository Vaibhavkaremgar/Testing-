import sys
sys.path.append('.')

from app.database import SessionLocal
from app.models import JobDescription

db = SessionLocal()

jobs = db.query(JobDescription).all()
print(f'Total jobs: {len(jobs)}')

for job in jobs:
    print(f'{job.id}: {job.title} - Active: {job.is_active}')

db.close()
