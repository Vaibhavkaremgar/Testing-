"""
Auto-migration script - runs on startup
"""
from sqlalchemy import inspect, text
from app.database import engine
from app.models import AnalyticsWidget, UserDashboardPreference, Agency, WalletTransaction, AgencyDiscount, NotificationWorkflowToken


def run_migrations():
    """Run all pending migrations"""
    try:
        with engine.connect() as conn:
            def get_tables():
                return set(inspect(engine).get_table_names())

            def get_columns(table):
                return [col["name"] for col in inspect(engine).get_columns(table)]

            def get_indexes(table):
                return {idx["name"] for idx in inspect(engine).get_indexes(table)}

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
                conn.commit()
                print("Migration completed: user_dashboard_preferences created")
            else:
                dashboard_pref_columns = get_columns("user_dashboard_preferences")
                dashboard_pref_additions = {
                    "user_id": "ALTER TABLE user_dashboard_preferences ADD COLUMN user_id UUID REFERENCES users(id)",
                    "widget_id": "ALTER TABLE user_dashboard_preferences ADD COLUMN widget_id INTEGER REFERENCES analytics_widgets(id)",
                    "position": "ALTER TABLE user_dashboard_preferences ADD COLUMN position INTEGER",
                    "size": "ALTER TABLE user_dashboard_preferences ADD COLUMN size VARCHAR(50)",
                    "is_enabled": "ALTER TABLE user_dashboard_preferences ADD COLUMN is_enabled BOOLEAN DEFAULT TRUE",
                    "created_at": "ALTER TABLE user_dashboard_preferences ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()",
                }
                for column_name, statement in dashboard_pref_additions.items():
                    if column_name not in dashboard_pref_columns:
                        print(f"Running migration: adding user_dashboard_preferences.{column_name}...")
                        conn.execute(text(statement))
                        conn.commit()
                        print(f"Migration completed: user_dashboard_preferences.{column_name} added")

            # agency_discounts table
            if "agency_discounts" not in get_tables():
                print("Running migration: creating agency_discounts table...")
                AgencyDiscount.__table__.create(bind=engine, checkfirst=True)
                conn.commit()
                print("Migration completed: agency_discounts created")

            # email_templates table/columns
            if "email_templates" not in get_tables():
                print("Running migration: creating email_templates table...")
                from app.models import EmailTemplate
                EmailTemplate.__table__.create(bind=engine, checkfirst=True)
                conn.commit()
                print("Migration completed: email_templates created")
            else:
                email_template_columns = get_columns("email_templates")
                email_template_additions = {
                    "agency_id": "ALTER TABLE email_templates ADD COLUMN agency_id UUID",
                    "created_by_user_id": "ALTER TABLE email_templates ADD COLUMN created_by_user_id UUID",
                    "status": "ALTER TABLE email_templates ADD COLUMN status VARCHAR(100) DEFAULT 'resume_shortlisted'",
                    "description": "ALTER TABLE email_templates ADD COLUMN description TEXT",
                    "is_html": "ALTER TABLE email_templates ADD COLUMN is_html BOOLEAN DEFAULT TRUE",
                    "is_default": "ALTER TABLE email_templates ADD COLUMN is_default BOOLEAN DEFAULT FALSE",
                    "is_selected": "ALTER TABLE email_templates ADD COLUMN is_selected BOOLEAN DEFAULT FALSE",
                }
                for column_name, statement in email_template_additions.items():
                    if column_name not in email_template_columns:
                        print(f"Running migration: adding email_templates.{column_name}...")
                        conn.execute(text(statement))
                        conn.commit()
                        print(f"Migration completed: email_templates.{column_name} added")

            # email_communications table/columns
            if "email_communications" not in get_tables():
                print("Running migration: creating email_communications table...")
                from app.models import EmailCommunication
                EmailCommunication.__table__.create(bind=engine, checkfirst=True)
                conn.commit()
                print("Migration completed: email_communications created")
            else:
                email_communication_columns = get_columns("email_communications")
                email_communication_additions = {
                    "agency_id": "ALTER TABLE email_communications ADD COLUMN agency_id UUID",
                    "template_id": "ALTER TABLE email_communications ADD COLUMN template_id INTEGER",
                    "subject": "ALTER TABLE email_communications ADD COLUMN subject VARCHAR(500)",
                    "body": "ALTER TABLE email_communications ADD COLUMN body TEXT",
                    "placeholder_payload": "ALTER TABLE email_communications ADD COLUMN placeholder_payload JSON",
                    "workflow_token": "ALTER TABLE email_communications ADD COLUMN workflow_token VARCHAR(255)",
                    "provider_message_id": "ALTER TABLE email_communications ADD COLUMN provider_message_id VARCHAR(255)",
                    "error_message": "ALTER TABLE email_communications ADD COLUMN error_message TEXT",
                }
                for column_name, statement in email_communication_additions.items():
                    if column_name not in email_communication_columns:
                        print(f"Running migration: adding email_communications.{column_name}...")
                        conn.execute(text(statement))
                        conn.commit()
                        print(f"Migration completed: email_communications.{column_name} added")

            if "notification_workflow_tokens" not in get_tables():
                print("Running migration: creating notification_workflow_tokens table...")
                NotificationWorkflowToken.__table__.create(bind=engine, checkfirst=True)
                conn.commit()
                print("Migration completed: notification_workflow_tokens created")

            # Performance indexes for dashboard filtering and sorting paths.
            performance_indexes = {
                "idx_candidates_agency_id": "CREATE INDEX IF NOT EXISTS idx_candidates_agency_id ON candidates (agency_id)",
                "idx_candidates_job_id": "CREATE INDEX IF NOT EXISTS idx_candidates_job_id ON candidates (job_id)",
                "idx_candidates_stage": "CREATE INDEX IF NOT EXISTS idx_candidates_stage ON candidates (stage)",
                "idx_candidates_assigned_to_user_id": "CREATE INDEX IF NOT EXISTS idx_candidates_assigned_to_user_id ON candidates (assigned_to_user_id)",
                "idx_candidates_created_at": "CREATE INDEX IF NOT EXISTS idx_candidates_created_at ON candidates (created_at)",
                "idx_candidates_agency_id_job_id": "CREATE INDEX IF NOT EXISTS idx_candidates_agency_id_job_id ON candidates (agency_id, job_id)",
                "idx_candidates_agency_id_stage": "CREATE INDEX IF NOT EXISTS idx_candidates_agency_id_stage ON candidates (agency_id, stage)",
                "idx_interviews_agency_id": "CREATE INDEX IF NOT EXISTS idx_interviews_agency_id ON interviews (agency_id)",
                "idx_interviews_candidate_id": "CREATE INDEX IF NOT EXISTS idx_interviews_candidate_id ON interviews (candidate_id)",
                "idx_interviews_scheduled_at": "CREATE INDEX IF NOT EXISTS idx_interviews_scheduled_at ON interviews (scheduled_at)",
                "idx_interviews_status": "CREATE INDEX IF NOT EXISTS idx_interviews_status ON interviews (status)",
                "idx_interviews_agency_id_status": "CREATE INDEX IF NOT EXISTS idx_interviews_agency_id_status ON interviews (agency_id, status)",
                "idx_interviews_candidate_id_scheduled_at": "CREATE INDEX IF NOT EXISTS idx_interviews_candidate_id_scheduled_at ON interviews (candidate_id, scheduled_at)",
                "idx_job_descriptions_agency_id": "CREATE INDEX IF NOT EXISTS idx_job_descriptions_agency_id ON job_descriptions (agency_id)",
                "idx_job_descriptions_is_active": "CREATE INDEX IF NOT EXISTS idx_job_descriptions_is_active ON job_descriptions (is_active)",
                "idx_job_descriptions_agency_id_is_active": "CREATE INDEX IF NOT EXISTS idx_job_descriptions_agency_id_is_active ON job_descriptions (agency_id, is_active)",
            }
            existing_indexes = set()
            for table_name in ("candidates", "interviews", "job_descriptions"):
                if table_name in get_tables():
                    existing_indexes.update(get_indexes(table_name))

            for index_name, statement in performance_indexes.items():
                if index_name not in existing_indexes:
                    print(f"Running migration: creating index {index_name}...")
                    conn.execute(text(statement))
                    conn.commit()
                    print(f"Migration completed: index {index_name} created")

    except Exception as e:
        print(f"Migration warning: {e}")


if __name__ == "__main__":
    run_migrations()
