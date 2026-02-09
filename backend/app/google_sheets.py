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
        """Sync candidates data to Google Sheets - append only new candidates"""
        try:
            if not self.is_configured or not self.service:
                return {
                    'success': False,
                    'synced_count': 0,
                    'error': 'Google Sheets service not configured. Please add hr-dashboard-key.json file and restart the application.'
                }
            
            print(f"Starting sync for {len(candidates)} candidates")
            
            # Read existing data to check what's already synced
            try:
                result = self.service.spreadsheets().values().get(
                    spreadsheetId=self.sheet_id,
                    range='Sheet1!A:A'
                ).execute()
                existing_ids = set()
                rows = result.get('values', [])
                if rows:
                    # Skip header row
                    for row in rows[1:]:
                        if row and row[0]:
                            existing_ids.add(row[0])
                print(f"Found {len(existing_ids)} existing candidates in sheet")
            except:
                existing_ids = set()
                print("No existing data found, will create new sheet")
            
            # Prepare data for new candidates only
            new_candidates = [c for c in candidates if c.candidate_id not in existing_ids]
            
            if not new_candidates:
                print("No new candidates to sync")
                return {
                    'success': True,
                    'synced_count': 0,
                    'message': 'No new candidates to sync'
                }
            
            print(f"Syncing {len(new_candidates)} new candidates")
            
            sheet_data = []
            
            # Add header row only if sheet is empty
            if not existing_ids:
                headers = [
                    'Candidate_ID', 'CandidateName', 'Email', 'Phone', 'Job_ID', 'Job_Title', 
                    'Resume_Text', 'Job_Description', 'Score', 'Skills', 'Resume_Evaluated', 'Summary'
                ]
                sheet_data.append(headers)
            
            # Add new candidate data
            for candidate in new_candidates:
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
                
                # Leave Score, Skills, Resume_Evaluated, Summary empty for N8N to fill
                row = [
                    candidate_id,
                    getattr(candidate, 'name', 'N/A'),
                    email,
                    phone,
                    job_id_value,
                    job_title,
                    resume_text,
                    job_description,
                    '',  # Score - to be filled by N8N
                    '',  # Skills - to be filled by N8N
                    '',  # Resume_Evaluated - to be filled by N8N
                    ''   # Summary - to be filled by N8N
                ]
                sheet_data.append(row)
            
            # Append data to sheet
            if sheet_data:
                if not existing_ids:
                    # First time - write with header
                    range_name = 'Sheet1!A1'
                else:
                    # Append to existing data
                    range_name = 'Sheet1!A:L'
                
                body = {
                    'values': sheet_data
                }
                
                if not existing_ids:
                    # Use update for first time
                    self.service.spreadsheets().values().update(
                        spreadsheetId=self.sheet_id,
                        range=range_name,
                        valueInputOption='RAW',
                        body=body
                    ).execute()
                else:
                    # Use append for subsequent syncs
                    self.service.spreadsheets().values().append(
                        spreadsheetId=self.sheet_id,
                        range=range_name,
                        valueInputOption='RAW',
                        insertDataOption='INSERT_ROWS',
                        body=body
                    ).execute()
                
                print(f"Synced {len(new_candidates)} new candidates to Google Sheets")
            
            return {
                'success': True,
                'synced_count': len(new_candidates),
                'message': f'Successfully synced {len(new_candidates)} new candidates to Google Sheets'
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
                        if score_value and score_value != '':
                            try:
                                score = float(score_value)
                                candidate.resume_score = score
                                
                                # Check if candidate has received any emails (primary method)
                                from app.models import EmailCommunication
                                email_sent = db_session.query(EmailCommunication).filter(
                                    EmailCommunication.candidate_id == candidate.id,
                                    EmailCommunication.status == "sent"
                                ).first()
                                
                                # Only update stage based on score if NO email has been sent (fallback)
                                if not email_sent:
                                    threshold = candidate.score_threshold or 60
                                    if score >= threshold:
                                        candidate.stage = CandidateStage.SHORTLISTED
                                    else:
                                        candidate.stage = CandidateStage.REJECTED
                            except (ValueError, TypeError):
                                pass
                    
                    # Update skills if present
                    if 'SKILLS' in col_indices and len(row) > col_indices['SKILLS']:
                        skills_value = row[col_indices['SKILLS']]
                        if skills_value and skills_value != '':
                            # Convert comma-separated string to list
                            skills_list = [s.strip() for s in skills_value.split(',') if s.strip()]
                            if skills_list:
                                candidate.skills = skills_list
                    
                    # Update summary if present
                    if 'SUMMARY' in col_indices and len(row) > col_indices['SUMMARY']:
                        summary_value = row[col_indices['SUMMARY']]
                        if summary_value and summary_value != '':
                            candidate.summary = summary_value
                    
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
    
    def delete_candidate_from_sheet(self, candidate_id: str) -> Dict[str, Any]:
        """Delete a candidate row from Google Sheets by Candidate_ID"""
        try:
            if not self.is_configured or not self.service:
                return {'success': False, 'error': 'Google Sheets service not configured'}
            
            # Read all data to find the row
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range='Sheet1!A:A'
            ).execute()
            
            rows = result.get('values', [])
            if not rows:
                return {'success': False, 'error': 'No data in sheet'}
            
            # Find row index (skip header)
            row_index = None
            for i, row in enumerate(rows[1:], start=2):  # Start from row 2 (after header)
                if row and row[0] == candidate_id:
                    row_index = i
                    break
            
            if not row_index:
                return {'success': True, 'message': 'Candidate not found in sheet'}
            
            # Delete the row
            request = {
                'deleteDimension': {
                    'range': {
                        'sheetId': 0,
                        'dimension': 'ROWS',
                        'startIndex': row_index - 1,
                        'endIndex': row_index
                    }
                }
            }
            
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.sheet_id,
                body={'requests': [request]}
            ).execute()
            
            return {'success': True, 'message': f'Deleted candidate {candidate_id} from sheet'}
            
        except Exception as e:
            print(f"Error deleting from sheet: {e}")
            return {'success': False, 'error': str(e)}

# Create global instance
sheets_service = GoogleSheetsService()