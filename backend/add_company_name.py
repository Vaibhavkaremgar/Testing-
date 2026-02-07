from app.database import SessionLocal, engine
from sqlalchemy import text

db = SessionLocal()

try:
    # Add company_name column to job_descriptions table
    db.execute(text("ALTER TABLE job_descriptions ADD COLUMN company_name VARCHAR(255)"))
    db.commit()
    print("Successfully added company_name column to job_descriptions table")
except Exception as e:
    print(f"Migration result: {e}")
    db.rollback()
finally:
    db.close()
