from sqlalchemy.orm import Session

from app.models import JobPortal


DEFAULT_PORTALS = (
    ("jooble", "/feeds/jooble.xml"),
    ("talent", "/feeds/talent.xml"),
    ("jora", "/feeds/jora.xml"),
)


def ensure_default_job_portals(db: Session) -> None:
    existing_portals = {
        portal.portal_name: portal
        for portal in db.query(JobPortal).all()
    }

    created = False
    for portal_name, feed_url in DEFAULT_PORTALS:
        if portal_name in existing_portals:
            continue

        db.add(
            JobPortal(
                portal_name=portal_name,
                feed_url=feed_url,
                is_enabled=True,
            )
        )
        created = True

    if created:
        db.commit()
