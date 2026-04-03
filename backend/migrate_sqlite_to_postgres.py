"""
Migrate data from SQLite (talentai.db) to PostgreSQL.

Usage:
    1. Set POSTGRES_URL in this script or as env var
    2. Run: python migrate_sqlite_to_postgres.py
"""

import sqlite3
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

SQLITE_PATH = os.path.join(os.path.dirname(__file__), "talentai.db")
POSTGRES_URL = os.getenv("DATABASE_URL", "postgresql://username:password@localhost:5432/talentai")

TABLES_IN_ORDER = [
    "users",
    "job_descriptions",
    "candidates",
    "interviews",
    "email_templates",
    "activity_logs",
    "clients",
    "email_communications",
    "analytics_widgets",
    "user_dashboard_preferences",
    "wallet_transactions",
]

def get_sqlite_data(table: str):
    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT * FROM {table}")
        rows = [dict(row) for row in cursor.fetchall()]
        return rows
    except Exception as e:
        print(f"  [SKIP] {table}: {e}")
        return []
    finally:
        conn.close()

def migrate():
    if not os.path.exists(SQLITE_PATH):
        print(f"SQLite file not found: {SQLITE_PATH}")
        sys.exit(1)

    print(f"Source: {SQLITE_PATH}")
    print(f"Target: {POSTGRES_URL}\n")

    # Create all tables in PostgreSQL using SQLAlchemy models
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "app"))
    os.environ["DATABASE_URL"] = POSTGRES_URL

    from app.database import Base
    import app.models  # noqa: F401 - registers all models

    pg_engine = create_engine(POSTGRES_URL)
    Base.metadata.create_all(pg_engine)
    print("Tables created in PostgreSQL.\n")

    Session = sessionmaker(bind=pg_engine)
    session = Session()

    for table in TABLES_IN_ORDER:
        rows = get_sqlite_data(table)
        if not rows:
            print(f"  {table}: 0 rows (skipped)")
            continue

        try:
            # Disable triggers/constraints temporarily for clean insert
            session.execute(text(f"ALTER TABLE {table} DISABLE TRIGGER ALL"))
            session.execute(text(f"DELETE FROM {table}"))

            for row in rows:
                cols = ", ".join(row.keys())
                placeholders = ", ".join([f":{k}" for k in row.keys()])
                session.execute(text(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"), row)

            # Reset sequence for id column
            session.execute(text(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                f"COALESCE(MAX(id), 1)) FROM {table}"
            ))

            session.execute(text(f"ALTER TABLE {table} ENABLE TRIGGER ALL"))
            session.commit()
            print(f"  {table}: {len(rows)} rows migrated")
        except Exception as e:
            session.rollback()
            print(f"  {table}: ERROR - {e}")

    session.close()
    print("\nMigration complete!")

if __name__ == "__main__":
    migrate()
