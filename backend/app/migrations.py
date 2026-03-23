"""
Auto-migration script - runs on startup
"""
from sqlalchemy import inspect, text
from app.database import engine
from app.models import AnalyticsWidget, UserDashboardPreference, Agency, WalletTransaction, AgencyDiscount, EmailTemplate


def run_migrations():
    """Run all pending migrations"""
    try:
        with engine.connect() as conn:
            def get_tables():
                return set(inspect(engine).get_table_names())

            def get_columns(table):
                return [col["name"] for col in inspect(engine).get_columns(table)]

            # Ensure agencies table exists first (other tables depend on it)
            if "agencies" not in get_tables():
                print("Running migration: creating agencies table...")
                Agency.__table__.create(bind=engine, checkfirst=True)
                conn.commit()
                print("Migration completed: agencies table created")

            # Migration: users.last_login_at
            if "last_login_at" not in get_columns("users"):
                print("Running migration: adding users.last_login_at...")
                conn.execute(text("ALTER TABLE users ADD COLUMN last_login_at TIMESTAMP WITH TIME ZONE"))
                conn.commit()
                print("Migration completed: users.last_login_at added")

            # Migration: users.agency_id
            if "agency_id" not in get_columns("users"):
                print("Running migration: adding users.agency_id...")
                conn.execute(text("ALTER TABLE users ADD COLUMN agency_id INTEGER REFERENCES agencies(id)"))
                conn.commit()
                print("Migration completed: users.agency_id added")

            # Migration: users.wallet_balance
            if "wallet_balance" not in get_columns("users"):
                print("Running migration: adding users.wallet_balance...")
                conn.execute(text("ALTER TABLE users ADD COLUMN wallet_balance INTEGER DEFAULT 0"))
                conn.commit()
                print("Migration completed: users.wallet_balance added")

            # wallet_transactions table
            if "wallet_transactions" not in get_tables():
                print("Running migration: creating wallet_transactions table...")
                WalletTransaction.__table__.create(bind=engine, checkfirst=True)
                conn.commit()
                print("Migration completed: wallet_transactions created")

            # Analytics tables
            if "analytics_widgets" not in get_tables():
                print("Running migration: creating analytics_widgets...")
                AnalyticsWidget.__table__.create(bind=engine, checkfirst=True)
                print("Migration completed: analytics_widgets created")

            if "user_dashboard_preferences" not in get_tables():
                print("Running migration: creating user_dashboard_preferences...")
                UserDashboardPreference.__table__.create(bind=engine, checkfirst=True)
                print("Migration completed: user_dashboard_preferences created")

            # agency_discounts table
            if "agency_discounts" not in get_tables():
                print("Running migration: creating agency_discounts table...")
                AgencyDiscount.__table__.create(bind=engine, checkfirst=True)
                conn.commit()
                print("Migration completed: agency_discounts created")

            # email_templates table / columns
            if "email_templates" not in get_tables():
                print("Running migration: creating email_templates table...")
                EmailTemplate.__table__.create(bind=engine, checkfirst=True)
                conn.commit()
                print("Migration completed: email_templates created")
            else:
                email_template_columns = get_columns("email_templates")
                if "agency_id" not in email_template_columns:
                    print("Running migration: adding email_templates.agency_id...")
                    conn.execute(text("ALTER TABLE email_templates ADD COLUMN agency_id UUID"))
                    conn.commit()
                    print("Migration completed: email_templates.agency_id added")
                if "created_by_user_id" not in email_template_columns:
                    print("Running migration: adding email_templates.created_by_user_id...")
                    conn.execute(text("ALTER TABLE email_templates ADD COLUMN created_by_user_id UUID"))
                    conn.commit()
                    print("Migration completed: email_templates.created_by_user_id added")

    except Exception as e:
        print(f"Migration warning: {e}")


if __name__ == "__main__":
    run_migrations()
