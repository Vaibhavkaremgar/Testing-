from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import User, JobDescription, Candidate, Interview, EmailTemplate, Client, EmailCommunication

def clear_all_data():
    db = SessionLocal()
    
    try:
        print("Clearing all data from database...")
        
        # Delete in order to respect foreign key constraints
        print("Deleting email communications...")
        db.query(EmailCommunication).delete()
        
        print("Deleting interviews...")
        db.query(Interview).delete()
        
        print("Deleting candidates...")
        db.query(Candidate).delete()
        
        print("Deleting email templates...")
        db.query(EmailTemplate).delete()
        
        print("Deleting job descriptions...")
        db.query(JobDescription).delete()
        
        print("Deleting clients...")
        db.query(Client).delete()
        
        print("Deleting users...")
        db.query(User).delete()
        
        db.commit()
        print("\n[SUCCESS] All data cleared successfully!")
        print("\nDatabase is now empty and ready for production deployment.")
        
    except Exception as e:
        print(f"Error clearing data: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    clear_all_data()
