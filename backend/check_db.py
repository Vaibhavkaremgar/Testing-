from app.database import SessionLocal
from app.models import User, JobDescription, Candidate

def check_database():
    db = SessionLocal()
    try:
        users = db.query(User).count()
        jobs = db.query(JobDescription).count()
        candidates = db.query(Candidate).count()
        
        print(f"Users: {users}")
        print(f"Jobs: {jobs}")
        print(f"Candidates: {candidates}")
        
        if users == 0:
            print("Database is empty - need to run seed script")
        else:
            print("Database has data")
            
    except Exception as e:
        print(f"Database error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_database()