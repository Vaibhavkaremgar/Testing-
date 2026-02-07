from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import User, JobDescription, Candidate, Interview, EmailTemplate, Client, EmailCommunication

def verify_empty_database():
    db = SessionLocal()
    
    try:
        print("Verifying database is empty...\n")
        
        counts = {
            "Users": db.query(User).count(),
            "Job Descriptions": db.query(JobDescription).count(),
            "Candidates": db.query(Candidate).count(),
            "Interviews": db.query(Interview).count(),
            "Email Templates": db.query(EmailTemplate).count(),
            "Clients": db.query(Client).count(),
            "Email Communications": db.query(EmailCommunication).count()
        }
        
        all_empty = all(count == 0 for count in counts.values())
        
        for table, count in counts.items():
            status = "[EMPTY]" if count == 0 else f"[{count} RECORDS]"
            print(f"{status} {table}")
        
        print("\n" + "="*50)
        if all_empty:
            print("[SUCCESS] Database is completely empty!")
            print("Ready for production deployment.")
        else:
            print("[WARNING] Some tables still have data.")
        print("="*50)
        
    except Exception as e:
        print(f"Error verifying database: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    verify_empty_database()
