# Add this to backend/.env file:
# GOOGLE_SHEETS_WEBHOOK_URL=https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec

# Alternative simple sync method - add this to candidates.py

@router.post("/sync-to-sheets-webhook")
def sync_candidates_to_sheets_webhook(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Simple webhook-based sync to Google Sheets (no service account needed)"""
    import requests
    import os
    from app.models import JobDescription
    
    webhook_url = os.getenv('GOOGLE_SHEETS_WEBHOOK_URL')
    
    if not webhook_url:
        raise HTTPException(
            status_code=400,
            detail="Google Sheets webhook URL not configured. Add GOOGLE_SHEETS_WEBHOOK_URL to .env file. See SIMPLE_SHEETS_SETUP.md for instructions."
        )
    
    try:
        # Get all candidates (excluding APPLIED stage)
        candidates = db.query(Candidate).filter(Candidate.stage != CandidateStage.APPLIED).all()
        
        if not candidates:
            return {"success": True, "synced_count": 0, "message": "No candidates to sync"}
        
        # Prepare data for Google Sheets
        candidates_data = []
        for c in candidates:
            # Ensure candidate_id exists
            if not c.candidate_id:
                c.candidate_id = f'CAND-{c.id}'
                db.commit()
            
            # Get job details
            job_id_str = ''
            job_title = ''
            job_description = ''
            if c.job_id:
                job = db.query(JobDescription).filter(JobDescription.id == c.job_id).first()
                if job:
                    job_id_str = job.job_id or str(c.job_id)
                    job_title = job.title or ''
                    job_description = (job.description[:1000] + '...') if job.description and len(job.description) > 1000 else (job.description or '')
            
            # Prepare resume text (truncate if too long)
            resume_text = ''
            if c.resume_text:
                resume_text = (c.resume_text[:2000] + '...') if len(c.resume_text) > 2000 else c.resume_text
            
            # Prepare skills (comma-separated)
            skills_str = ', '.join(c.skills) if c.skills else ''
            
            candidates_data.append({
                'candidate_id': c.candidate_id,
                'name': c.name or '',
                'email': c.email or '',
                'phone': c.phone or '',
                'job_id': job_id_str,
                'job_title': job_title,
                'resume_text': resume_text,
                'job_description': job_description,
                'score': str(c.resume_score) if c.resume_score is not None else '',
                'skills': skills_str
            })
        
        # Send to Google Sheets webhook
        print(f"Sending {len(candidates_data)} candidates to Google Sheets webhook...")
        response = requests.post(
            webhook_url,
            json={'candidates': candidates_data},
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            synced_count = result.get('synced_count', 0)
            print(f"✅ Successfully synced {synced_count} new candidates")
            return {
                'success': True,
                'synced_count': synced_count,
                'sheets_synced': synced_count,
                'message': f'Successfully synced {synced_count} new candidates to Google Sheets'
            }
        else:
            error_msg = f'Webhook returned status {response.status_code}: {response.text}'
            print(f"❌ {error_msg}")
            raise HTTPException(status_code=500, detail=error_msg)
            
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail='Google Sheets webhook timeout. Please try again.')
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f'Failed to connect to Google Sheets: {str(e)}')
    except Exception as e:
        print(f"❌ Sync error: {str(e)}")
        raise HTTPException(status_code=500, detail=f'Sync failed: {str(e)}')
