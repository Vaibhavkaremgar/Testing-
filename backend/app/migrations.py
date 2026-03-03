"""
Auto-migration script - runs on startup
"""
from sqlalchemy import inspect, text

from app.database import engine
from app.models import AnalyticsWidget, UserDashboardPreference


def run_migrations():
    """Run all pending migrations"""
    try:
        inspector = inspect(engine)

        with engine.connect() as conn:
            # Existing migration: users.last_login_at
            columns = [col["name"] for col in inspector.get_columns("users")]
            if "last_login_at" not in columns:
                print("Running migration: adding users.last_login_at...")
                conn.execute(text("ALTER TABLE users ADD COLUMN last_login_at TIMESTAMP"))
                conn.commit()
                print("Migration completed: users.last_login_at added")
            else:
                print("users.last_login_at already present")

            # Analytics-only tables
            table_names = set(inspector.get_table_names())
            if "analytics_widgets" not in table_names:
                print("Running migration: creating analytics_widgets...")
                AnalyticsWidget.__table__.create(bind=engine, checkfirst=True)
                print("Migration completed: analytics_widgets created")

            if "user_dashboard_preferences" not in table_names:
                print("Running migration: creating user_dashboard_preferences...")
                UserDashboardPreference.__table__.create(bind=engine, checkfirst=True)
                print("Migration completed: user_dashboard_preferences created")

    except Exception as e:
        print(f"Migration warning: {e}")
        # Don't fail startup if migration fails


if __name__ == "__main__":
    run_migrations()
