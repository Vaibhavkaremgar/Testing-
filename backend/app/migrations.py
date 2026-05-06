"""
Auto-migration script - runs on startup
"""
from sqlalchemy import inspect, text
from app.database import engine
from app.models import (
    Agency,
    AgencyDiscount,
    AnalyticsWidget,
    FeedAccessLog,
    NotificationWorkflowToken,
    Plan,
    PlanLimit,
    JobApplication,
    Subscription,
    UsageLog,
    UsageTracking,
    UserDashboardPreference,
    Wallet,
    WalletTransaction,
)


def run_migrations():
    """Run all pending migrations"""
    try:
        with engine.connect() as conn:
            def get_tables():
                return set(inspect(engine).get_table_names())

            def get_columns(table):
                return [col["name"] for col in inspect(engine).get_columns(table)]

            def get_column(table, column):
                for col in inspect(engine).get_columns(table):
                    if col["name"] == column:
                        return col
                return None

            def get_indexes(table):
                return {idx["name"] for idx in inspect(engine).get_indexes(table)}

            dialect_name = engine.dialect.name

            def add_column_if_missing(table_name, column_name, sqlite_sql, default_sql):
                if column_name in get_columns(table_name):
                    return
                print(f"Running migration: adding {table_name}.{column_name}...")
                statement = sqlite_sql if dialect_name == "sqlite" else default_sql
                conn.execute(text(statement))
                conn.commit()
                print(f"Migration completed: {table_name}.{column_name} added")

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
                conn.execute(text("ALTER TABLE users ADD COLUMN agency_id UUID REFERENCES agencies(id)"))
                conn.commit()
                print("Migration completed: users.agency_id added")
            else:
                agency_id_column = get_column("users", "agency_id")
                agency_id_type = str(agency_id_column["type"]).lower() if agency_id_column else ""
                if "uuid" not in agency_id_type:
                    print("Running migration: normalizing users.agency_id to UUID...")
                    if "legacy_agency_id" not in get_columns("users"):
                        conn.execute(text("ALTER TABLE users RENAME COLUMN agency_id TO legacy_agency_id"))
                        conn.commit()
                    conn.execute(text("ALTER TABLE users ALTER COLUMN legacy_agency_id DROP NOT NULL"))
                    conn.commit()
                    if "agency_id" not in get_columns("users"):
                        conn.execute(text("ALTER TABLE users ADD COLUMN agency_id UUID REFERENCES agencies(id)"))
                        conn.commit()
                    print("Migration completed: users.agency_id normalized to UUID")
                elif "legacy_agency_id" in get_columns("users"):
                    conn.execute(text("ALTER TABLE users ALTER COLUMN legacy_agency_id DROP NOT NULL"))
                    conn.commit()

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

            if "subscriptions" not in get_tables():
                print("Running migration: creating subscriptions table...")
                Subscription.__table__.create(bind=engine, checkfirst=True)
                conn.commit()
                print("Migration completed: subscriptions created")
            else:
                subscription_columns = get_columns("subscriptions")
                subscription_additions = {
                    "agency_id": "ALTER TABLE subscriptions ADD COLUMN agency_id UUID REFERENCES agencies(id)",
                    "user_id": "ALTER TABLE subscriptions ADD COLUMN user_id UUID REFERENCES users(id)",
                    "plan_id": "ALTER TABLE subscriptions ADD COLUMN plan_id UUID REFERENCES plans(id)",
                    "status": "ALTER TABLE subscriptions ADD COLUMN status VARCHAR(50) DEFAULT 'active'",
                    "plan_name": "ALTER TABLE subscriptions ADD COLUMN plan_name VARCHAR(50)",
                    "billing_type": "ALTER TABLE subscriptions ADD COLUMN billing_type VARCHAR(20)",
                    "price_per_user": "ALTER TABLE subscriptions ADD COLUMN price_per_user DOUBLE PRECISION",
                    "total_price": "ALTER TABLE subscriptions ADD COLUMN total_price DOUBLE PRECISION",
                    "interview_credits_total": "ALTER TABLE subscriptions ADD COLUMN interview_credits_total INTEGER",
                    "interview_credits_used": "ALTER TABLE subscriptions ADD COLUMN interview_credits_used INTEGER DEFAULT 0 NOT NULL",
                    "max_job_posts": "ALTER TABLE subscriptions ADD COLUMN max_job_posts INTEGER",
                    "used_job_posts": "ALTER TABLE subscriptions ADD COLUMN used_job_posts INTEGER DEFAULT 0 NOT NULL",
                    "max_users": "ALTER TABLE subscriptions ADD COLUMN max_users INTEGER",
                    "current_users": "ALTER TABLE subscriptions ADD COLUMN current_users INTEGER DEFAULT 0 NOT NULL",
                    "resume_scoring_limit": "ALTER TABLE subscriptions ADD COLUMN resume_scoring_limit INTEGER",
                    "resume_scoring_used": "ALTER TABLE subscriptions ADD COLUMN resume_scoring_used INTEGER DEFAULT 0 NOT NULL",
                    "is_unlimited_resume_scoring": "ALTER TABLE subscriptions ADD COLUMN is_unlimited_resume_scoring BOOLEAN DEFAULT FALSE NOT NULL",
                    "is_unlimited_jobs": "ALTER TABLE subscriptions ADD COLUMN is_unlimited_jobs BOOLEAN DEFAULT FALSE NOT NULL",
                    "expires_at": "ALTER TABLE subscriptions ADD COLUMN expires_at TIMESTAMP WITH TIME ZONE",
                    "cycle_anchor_at": "ALTER TABLE subscriptions ADD COLUMN cycle_anchor_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()",
                    "last_monthly_reset_at": "ALTER TABLE subscriptions ADD COLUMN last_monthly_reset_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()",
                    "created_at": "ALTER TABLE subscriptions ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()",
                    "updated_at": "ALTER TABLE subscriptions ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE",
                }
                for column_name, statement in subscription_additions.items():
                    if column_name not in subscription_columns:
                        print(f"Running migration: adding subscriptions.{column_name}...")
                        conn.execute(text(statement))
                        conn.commit()
                        print(f"Migration completed: subscriptions.{column_name} added")

                subscription_user_id_column = get_column("subscriptions", "user_id")
                subscription_user_id_type = (
                    str(subscription_user_id_column["type"]).lower()
                    if subscription_user_id_column else ""
                )
                if subscription_user_id_column and "uuid" not in subscription_user_id_type:
                    print("Running migration: normalizing subscriptions.user_id to UUID...")
                    if "idx_subscriptions_user_id_created_at" in get_indexes("subscriptions"):
                        conn.execute(text("DROP INDEX IF EXISTS idx_subscriptions_user_id_created_at"))
                        conn.commit()

                    if "legacy_user_id" not in get_columns("subscriptions"):
                        conn.execute(text("ALTER TABLE subscriptions RENAME COLUMN user_id TO legacy_user_id"))
                        conn.commit()
                    conn.execute(text("ALTER TABLE subscriptions ALTER COLUMN legacy_user_id DROP NOT NULL"))
                    conn.commit()

                    if "user_id" not in get_columns("subscriptions"):
                        conn.execute(text("ALTER TABLE subscriptions ADD COLUMN user_id UUID REFERENCES users(id)"))
                        conn.commit()

                    legacy_user_id_column = get_column("subscriptions", "legacy_user_id")
                    legacy_user_id_type = (
                        str(legacy_user_id_column["type"]).lower()
                        if legacy_user_id_column else ""
                    )
                    if any(text_type in legacy_user_id_type for text_type in ("char", "text", "varchar")):
                        conn.execute(
                            text(
                                """
                                UPDATE subscriptions
                                SET user_id = NULLIF(legacy_user_id::text, '')::uuid
                                WHERE user_id IS NULL
                                  AND legacy_user_id IS NOT NULL
                                """
                            )
                        )
                        conn.commit()

                    print("Migration completed: subscriptions.user_id normalized to UUID")
                elif "legacy_user_id" in get_columns("subscriptions"):
                    conn.execute(text("ALTER TABLE subscriptions ALTER COLUMN legacy_user_id DROP NOT NULL"))
                    conn.commit()

            if "plans" not in get_tables():
                print("Running migration: creating plans table...")
                Plan.__table__.create(bind=engine, checkfirst=True)
                conn.commit()
                print("Migration completed: plans created")

            if "plan_limits" not in get_tables():
                print("Running migration: creating plan_limits table...")
                PlanLimit.__table__.create(bind=engine, checkfirst=True)
                conn.commit()
                print("Migration completed: plan_limits created")

            if "wallets" not in get_tables():
                print("Running migration: creating wallets table...")
                Wallet.__table__.create(bind=engine, checkfirst=True)
                conn.commit()
                print("Migration completed: wallets created")

            if "usage_logs" not in get_tables():
                print("Running migration: creating usage_logs table...")
                UsageLog.__table__.create(bind=engine, checkfirst=True)
                conn.commit()
                print("Migration completed: usage_logs created")

            if "usage_tracking" not in get_tables():
                print("Running migration: creating usage_tracking table...")
                UsageTracking.__table__.create(bind=engine, checkfirst=True)
                conn.commit()
                print("Migration completed: usage_tracking created")

            if "job_descriptions" in get_tables():
                add_column_if_missing(
                    "job_descriptions",
                    "city",
                    "ALTER TABLE job_descriptions ADD COLUMN city VARCHAR(120)",
                    "ALTER TABLE job_descriptions ADD COLUMN city VARCHAR(120)",
                )
                add_column_if_missing(
                    "job_descriptions",
                    "state",
                    "ALTER TABLE job_descriptions ADD COLUMN state VARCHAR(120)",
                    "ALTER TABLE job_descriptions ADD COLUMN state VARCHAR(120)",
                )
                add_column_if_missing(
                    "job_descriptions",
                    "country",
                    "ALTER TABLE job_descriptions ADD COLUMN country VARCHAR(120)",
                    "ALTER TABLE job_descriptions ADD COLUMN country VARCHAR(120)",
                )
                add_column_if_missing(
                    "job_descriptions",
                    "category",
                    "ALTER TABLE job_descriptions ADD COLUMN category VARCHAR(150)",
                    "ALTER TABLE job_descriptions ADD COLUMN category VARCHAR(150)",
                )
                add_column_if_missing(
                    "job_descriptions",
                    "remote",
                    "ALTER TABLE job_descriptions ADD COLUMN remote BOOLEAN DEFAULT 0",
                    "ALTER TABLE job_descriptions ADD COLUMN remote BOOLEAN DEFAULT FALSE",
                )

            if "job_applications" not in get_tables():
                print("Running migration: creating job_applications table...")
                JobApplication.__table__.create(bind=engine, checkfirst=True)
                conn.commit()
                print("Migration completed: job_applications created")

            if "feed_access_logs" not in get_tables():
                print("Running migration: creating feed_access_logs table...")
                FeedAccessLog.__table__.create(bind=engine, checkfirst=True)
                conn.commit()
                print("Migration completed: feed_access_logs created")

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
                "idx_job_applications_job_id_created_at": "CREATE INDEX IF NOT EXISTS idx_job_applications_job_id_created_at ON job_applications (job_id, created_at)",
                "idx_job_applications_email": "CREATE INDEX IF NOT EXISTS idx_job_applications_email ON job_applications (email)",
                "idx_feed_access_logs_portal_accessed_at": "CREATE INDEX IF NOT EXISTS idx_feed_access_logs_portal_accessed_at ON feed_access_logs (portal_name, accessed_at)",
                "idx_subscriptions_agency_id_status": "CREATE INDEX IF NOT EXISTS idx_subscriptions_agency_id_status ON subscriptions (agency_id, status)",
                "idx_subscriptions_user_id_created_at": "CREATE INDEX IF NOT EXISTS idx_subscriptions_user_id_created_at ON subscriptions (user_id, created_at)",
                "idx_subscriptions_expires_at": "CREATE INDEX IF NOT EXISTS idx_subscriptions_expires_at ON subscriptions (expires_at)",
                "idx_usage_logs_agency_id_created_at": "CREATE INDEX IF NOT EXISTS idx_usage_logs_agency_id_created_at ON usage_logs (agency_id, created_at)",
                "idx_usage_logs_feature_name_created_at": "CREATE INDEX IF NOT EXISTS idx_usage_logs_feature_name_created_at ON usage_logs (feature_name, created_at)",
            }
            existing_indexes = set()
            for table_name in ("candidates", "interviews", "job_descriptions", "job_applications", "feed_access_logs", "subscriptions", "plans", "plan_limits", "usage_tracking", "usage_logs"):
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
