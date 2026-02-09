import json
from typing import List, Dict, Any
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import os

class GoogleSheetsService:
    def __init__(self):
        # Your Google Sheet ID
        self.sheet_id = "18ugwqo2-_A80zPP_JfCRL6sDKNGBCweWkxsFuSmfQmE"
        self.service = None
        self.is_configured = False
        self._initialize_service()
    
    def _initialize_service(self):
        """Initialize Google Sheets service with service account"""
        try:
            # Try environment variable first (for Railway/production)
            google_creds_json = os.getenv('GOOGLE_SHEETS_CREDENTIALS')
            
            if google_creds_json:
                # Load credentials from environment variable
                print("Loading Google Sheets credentials from environment variable")
                creds_dict = json.loads(google_creds_json)
                scopes = ['https://www.googleapis.com/auth/spreadsheets']
                credentials = Credentials.from_service_account_info(creds_dict, scopes=scopes)
                self.service = build('sheets', 'v4', credentials=credentials)
                self.is_configured = True
                print("Google Sheets service initialized successfully from environment")
                return
            
            # Fallback to file (for local development)
            key_file = "hr-dashboard-key.json"
            
            if not os.path.exists(key_file):
                print(f"Google Sheets service account key file not found: {key_file}")
                print("Google Sheets sync will be disabled. To enable:")
                print("Option 1 (Railway/Production):")
                print("  Set GOOGLE_SHEETS_CREDENTIALS environment variable with JSON content")
                print("Option 2 (Local Development):")
                print("  1. Create a Google Cloud service account")
                print("  2. Download the JSON key file")
                print("  3. Place it as 'hr-dashboard-key.json' in the backend directory")
                print("  4. Share your Google Sheet with the service account email")
                self.is_configured = False
                return
            
            # Define the scope
            scopes = ['https://www.googleapis.com/auth/spreadsheets']
            
            # Load credentials from file
            credentials = Credentials.from_service_account_file(key_file, scopes=scopes)
            
            # Build the service
            self.service = build('sheets', 'v4', credentials=credentials)
            self.is_configured = True
            print("Google Sheets service initialized successfully from file")
            
        except Exception as e:
            print(f"Failed to initialize Google Sheets service: {e}")
            self.service = None
            self.is_configured = False
    
    def sync_candidates_to_sheet(self, candidates: List[Any]) -> Dict[str, Any]:
        """Sync candidates data to Google Sheets - full sync (add/update/delete)"""
        try:
            if not self.is_configured or not self.service:
                return {
                    'success': False,
                    'synced_count': 0,
                    'error': 'Google Sheets service not configured. Please add hr-dashboard-key.json file and restart the application.'
                }
            
            print(f"Starting full sync for {len(candidates)} candidates")
            
            # Prepare data for Google Sheets
            sheet_data = []
            
            # Add header row
            headers = [
                'Candidate_ID', 'CandidateName', 'Email', 'Phone', 'Job_ID', 'Job_Title', 'Resume_Text', 'Job_Description', 'Email_ID', 'Mobile_Number'
            ]
            sheet_data.append(headers)
            
            # Add all candidate data
            for candidate in candidates:
                candidate_id = getattr(candidate, 'candidate_id', 'N/A')
                
                # Get job details
                job_id_value = 'N/A'
                job_title = 'N/A'
                job_description = 'N/A'
                
                if hasattr(candidate, 'job') and candidate.job:
                    job_id_value = candidate.job.job_id or 'N/A'
                    job_title = candidate.job.title or 'N/A'
                    job_description = candidate.job.description or 'N/A'
                    if len(job_description) > 1000:
                        job_description = job_description[:1000] + '...'
                
                # Get resume text
                resume_text = getattr(candidate, 'resume_text', '') or 'N/A'
                if len(resume_text) > 2000:
                    resume_text = resume_text[:2000] + '...'
                
                # Get email and phone
                email = getattr(candidate, 'email', '') or 'N/A'
                phone = getattr(candidate, 'phone', '') or 'N/A'
                
                row = [
                    candidate_id,
                    getattr(candidate, 'name', 'N/A'),
                    email,
                    phone,
                    job_id_value,
                    job_title,
                    resume_text,
                    job_description,
                    email,
                    phone
                ]
                sheet_data.append(row)
            
            # Clear existing data and write all data
            range_name = f'Sheet1!A1:J{len(sheet_data)}'
            
            # First, clear the entire sheet
            try:
                self.service.spreadsheets().values().clear(
                    spreadsheetId=self.sheet_id,
                    range='Sheet1!A:Z'
                ).execute()
                print("Cleared existing sheet data")
            except HttpError as e:
                print(f"Error clearing sheet: {e}")
            
            # Write all data
            body = {
                'values': sheet_data
            }
            
            result = self.service.spreadsheets().values().update(
                spreadsheetId=self.sheet_id,
                range=range_name,
                valueInputOption='RAW',
                body=body
            ).execute()
            
            print(f"Synced {len(candidates)} candidates to Google Sheets")
            
            return {
                'success': True,
                'synced_count': len(candidates),
                'message': f'Successfully synced {len(candidates)} candidates to Google Sheets'
            }
            
        except HttpError as e:
            error_msg = f'Google Sheets API error: {e}'
            print(error_msg)
            return {
                'success': False,
                'synced_count': 0,
                'error': error_msg
            }
        except Exception as e:
            error_msg = f'Failed to sync to Google Sheets: {str(e)}'
            print(error_msg)
            return {
                'success': False,
                'synced_count': 0,
                'error': error_msg
            }
    
    def sync_scores_from_sheet(self, db_session) -> Dict[str, Any]:
        """Pull data from Google Sheets and update candidates in database"""
        try:
            if not self.is_configured or not self.service:
                return {
                    'success': False,
                    'updated_count': 0,
                    'error': 'Google Sheets service not configured. Please add hr-dashboard-key.json file and restart the application.'
                }
            
            # Read all data from sheet
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range='Sheet1!A:Z'  # Read all columns
            ).execute()
            
            rows = result.get('values', [])
            if not rows or len(rows) < 2:
                return {
                    'success': False,
                    'updated_count': 0,
                    'error': 'No data found in sheet'
                }
            
            # Find column indices from header row
            headers = rows[0]
            col_indices = {}
            
            for i, header in enumerate(headers):
                col_indices[header.upper()] = i
            
            # Required columns
            if 'CANDIDATE_ID' not in col_indices:
                return {
                    'success': False,
                    'updated_count': 0,
                    'error': 'Candidate_ID column not found in sheet'
                }
            
            # Import here to avoid circular import
            from app.models import Candidate, CandidateStage
            
            updated_count = 0
            deleted_count = 0
            
            # Get all candidate IDs from sheet
            sheet_candidate_ids = set()
            for row in rows[1:]:
                if len(row) > col_indices['CANDIDATE_ID']:
                    candidate_id = row[col_indices['CANDIDATE_ID']]
                    if candidate_id:
                        sheet_candidate_ids.add(candidate_id)
            
            # Delete candidates not in sheet
            all_candidates = db_session.query(Candidate).all()
            for candidate in all_candidates:
                if candidate.candidate_id and candidate.candidate_id not in sheet_candidate_ids:
                    db_session.delete(candidate)
                    deleted_count += 1
            
            # Process each row (skip header)
            for row in rows[1:]:
                if len(row) <= col_indices['CANDIDATE_ID']:
                    continue
                
                candidate_id = row[col_indices['CANDIDATE_ID']]
                if not candidate_id:
                    continue
                
                # Find candidate in database
                candidate = db_session.query(Candidate).filter(
                    Candidate.candidate_id == candidate_id
                ).first()
                
                if candidate:
                    # Update name
                    if 'CANDIDATENAME' in col_indices and len(row) > col_indices['CANDIDATENAME']:
                        new_name = row[col_indices['CANDIDATENAME']]
                        if new_name and new_name != 'N/A':
                            candidate.name = new_name
                    
                    # Update email
                    if 'EMAIL' in col_indices and len(row) > col_indices['EMAIL']:
                        new_email = row[col_indices['EMAIL']]
                        if new_email and new_email != 'N/A':
                            candidate.email = new_email
                    
                    # Update phone
                    if 'PHONE' in col_indices and len(row) > col_indices['PHONE']:
                        new_phone = row[col_indices['PHONE']]
                        if new_phone and new_phone != 'N/A':
                            candidate.phone = new_phone
                    
                    # Update score if present
                    if 'SCORE' in col_indices and len(row) > col_indices['SCORE']:
                        score_value = row[col_indices['SCORE']]
                        if score_value:
                            try:
                                score = float(score_value)
                                candidate.resume_score = score
                                
                                # Update stage based on score and threshold
                                threshold = candidate.score_threshold or 60
                                if score >= threshold:
                                    candidate.stage = CandidateStage.SHORTLISTED
                                else:
                                    candidate.stage = CandidateStage.REJECTED
                            except (ValueError, TypeError):
                                pass
                    
                    updated_count += 1
            
            db_session.commit()
            
            message = f'Updated {updated_count} candidates'
            if deleted_count > 0:
                message += f', deleted {deleted_count} candidates'
            
            return {
                'success': True,
                'updated_count': updated_count,
                'deleted_count': deleted_count,
                'message': message
            }
            
        except Exception as e:
            db_session.rollback()
            return {
                'success': False,
                'updated_count': 0,
                'error': f'Failed to sync from Google Sheets: {str(e)}'
            }

# Create global instance
sheets_service = GoogleSheetsService()