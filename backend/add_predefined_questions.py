"""Add predefined_questions column to candidates table"""
from sqlalchemy import create_engine, text
from app.config import settings

engine = create_engine(settings.DATABASE_URL)

with engine.connect() as conn:
    try:
        conn.execute(text("ALTER TABLE candidates ADD COLUMN predefined_questions TEXT"))
        conn.commit()
        print("✅ Added predefined_questions column")
    except Exception as e:
        print(f"Column might already exist: {e}")
