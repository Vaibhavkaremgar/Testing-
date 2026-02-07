from app.database import SessionLocal
from app.models import Candidate, Interview
import os
import shutil

db = SessionLocal()

# Delete all interviews first (foreign key constraint)
interviews_deleted = db.query(Interview).delete()
db.commit()
print(f'Deleted {interviews_deleted} interviews')

# Delete all candidates
candidates_deleted = db.query(Candidate).delete()
db.commit()
print(f'Deleted {candidates_deleted} candidates')

# Clear uploads directory
uploads_dir = 'uploads'
if os.path.exists(uploads_dir):
    for file in os.listdir(uploads_dir):
        file_path = os.path.join(uploads_dir, file)
        try:
            if os.path.isfile(file_path):
                os.unlink(file_path)
        except Exception as e:
            print(f'Error deleting {file_path}: {e}')
    print(f'Cleared uploads directory')

db.close()
print('✓ All candidate data cleared! Ready for fresh start.')
