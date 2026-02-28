"""
Migration: Add last_login_at to users table
Run this in your database or use Alembic
"""

# SQLite
ALTER TABLE users ADD COLUMN last_login_at TIMESTAMP;

# Or run in Python:
# from app.database import engine
# from sqlalchemy import text
# with engine.connect() as conn:
#     conn.execute(text("ALTER TABLE users ADD COLUMN last_login_at TIMESTAMP"))
#     conn.commit()
