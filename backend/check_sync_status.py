#!/usr/bin/env python3

import sys
sys.path.append('.')

from app.database import SessionLocal
from app.models import Candidate

def check_sync_status():
    """Check sync status of candidates"""
    db = SessionLocal()
    try:
        candidates = db.query(Candidate).all()
        total = len(candidates)
        synced = sum(1 for c in candidates if c.synced_to_sheets)
        unsynced = total - synced
        
        print(f'Total candidates: {total}')
        print(f'Synced candidates: {synced}')
        print(f'Unsynced candidates: {unsynced}')
        
        if unsynced > 0:
            print("\\nUnsynced candidates:")
            for c in candidates:
                if not c.synced_to_sheets:
                    print(f"- {c.name} (ID: {c.id})")
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_sync_status()