"""
Migration: add missing columns to user_dashboard_preferences table.
Run on server: python migrate_dashboard_prefs.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal
from sqlalchemy import text

db = SessionLocal()
try:
    # Check which columns already exist
    existing = {
        row[0]
        for row in db.execute(text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='user_dashboard_preferences'"
        )).fetchall()
    }
    print("Existing columns:", existing)

    migrations = []

    if "user_id" not in existing:
        migrations.append(
            "ALTER TABLE user_dashboard_preferences ADD COLUMN user_id UUID REFERENCES users(id)"
        )

    if "widget_id" not in existing:
        migrations.append(
            "ALTER TABLE user_dashboard_preferences ADD COLUMN widget_id INTEGER REFERENCES analytics_widgets(id)"
        )

    if "position" not in existing:
        migrations.append(
            "ALTER TABLE user_dashboard_preferences ADD COLUMN position INTEGER"
        )

    if "size" not in existing:
        migrations.append(
            "ALTER TABLE user_dashboard_preferences ADD COLUMN size VARCHAR(50)"
        )

    if "is_enabled" not in existing:
        migrations.append(
            "ALTER TABLE user_dashboard_preferences ADD COLUMN is_enabled BOOLEAN DEFAULT TRUE"
        )

    if not migrations:
        print("All columns already exist — nothing to do.")
    else:
        for sql in migrations:
            print(f"Running: {sql}")
            db.execute(text(sql))
        db.commit()
        print(f"Done. Applied {len(migrations)} migration(s).")

except Exception as e:
    db.rollback()
    print(f"ERROR: {e}")
    import traceback; traceback.print_exc()
finally:
    db.close()
