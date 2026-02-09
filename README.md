# TalentAI - AI Recruitment System Dashboard

A modern, full-stack SaaS web dashboard for an AI-powered recruitment system. Built with React, Tailwind CSS, ShadCN UI components on the frontend, and Python FastAPI on the backend.

## 🚀 FREE AI-Powered Resume Analysis

**Get intelligent resume scoring with ZERO cost!**

✅ **100% FREE** - Uses Groq's free API (no credit card needed)
✅ **Real AI understanding** - Not just keyword matching  
✅ **Context-aware evaluation** - Understands experience quality
✅ **Unique scores** - Each resume gets 25-95 score based on content
✅ **Fast** - 0.5-1 second per resume

👉 **[Quick Setup: GROQ_SETUP.md](./GROQ_SETUP.md)** (2 minutes)

### How to Enable:

1. Get free API key: https://console.groq.com
2. Add to `backend/.env`:
   ```env
   GROQ_API_KEY=gsk_your_key_here
   LLM_PROVIDER=groq
   ```
3. Restart backend
4. Upload resumes and get AI-powered scores!

## Features

### Dashboard Overview
- KPI cards showing total resumes, shortlisted, rejected, interviews, and selected candidates
- Resume score trend charts
- Interview score breakdown charts
- Hiring funnel visualization

### Resume Management
- Single and bulk resume upload with drag-and-drop
- Job description attachment
- AI-powered resume parsing simulation
- Resume score display
- Searchable and filterable data table

### Candidate Pipeline
- Kanban board with 7 stages: Uploaded, Screening, Shortlisted, Interview Scheduled, Interviewed, Selected, Rejected
- Drag-and-drop functionality to move candidates between stages
- Real-time stage updates

### Interview Section
- Interview list with status indicators
- Video player placeholder
- Transcript viewer
- AI-generated summary and scores
- Technical, Communication, and Culture Fit score breakdown
- Send Offer / Reject action buttons

### Analytics
- Time to hire trends
- Skill heatmap visualization
- Score distribution charts
- Hiring by department charts

### Additional Features
- Job Description management (CRUD)
- Email templates management
- User settings with theme toggle (light/dark mode)
- Role-based access (Admin, Recruiter, Hiring Manager, Viewer)
- JWT authentication

## Tech Stack

### Frontend
- React 18 with Vite
- Tailwind CSS
- ShadCN UI components (Radix UI primitives)
- React Router for navigation
- Recharts for data visualization
- DnD Kit for Kanban drag-and-drop
- Lucide React for icons

### Backend
- Python 3.11+ with FastAPI
- SQLAlchemy ORM with SQLite
- Pydantic for data validation
- python-jose for JWT authentication
- Uvicorn ASGI server

## Project Structure

```
ai-recruitment-dashboard/
├── backend/
│   ├── app/
│   │   ├── routes/          # API endpoints
│   │   ├── models.py        # Database models
│   │   ├── schemas.py       # Pydantic schemas
│   │   ├── auth.py          # Authentication utilities
│   │   ├── database.py      # Database connection
│   │   ├── config.py        # Configuration
│   │   ├── seed.py          # Demo data seeder
│   │   └── main.py          # FastAPI application
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/      # UI and layout components
│   │   ├── pages/           # Page components
│   │   ├── context/         # React context providers
│   │   ├── lib/             # Utilities and API client
│   │   └── App.jsx          # Main app with routing
│   ├── package.json
│   └── vite.config.js
└── README.md
```

## Getting Started

### Prerequisites
- Node.js 18+
- Python 3.11+
- pip

### Backend Setup

1. Navigate to the backend directory:
```bash
cd ai-recruitment-dashboard/backend
```

2. Create a virtual environment:
```bash
python -m venv venv
```

3. Activate the virtual environment:
```bash
# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Run the backend server:
```bash
uvicorn app.main:app --reload --port 8000
```

The API will be available at `http://localhost:8000`
- API Docs: `http://localhost:8000/api/docs`
- ReDoc: `http://localhost:8000/api/redoc`

### Frontend Setup

1. Navigate to the frontend directory:
```bash
cd ai-recruitment-dashboard/frontend
```

2. Install dependencies:
```bash
npm install
```

3. Run the development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:5173`

## 🚀 Production Ready - Clean Installation

**No dummy data included!** The application starts with a clean database.

### First Time Setup

1. **Create your first admin user** via API:
```bash
POST /api/auth/register
{
  "email": "admin@yourcompany.com",
  "password": "your-secure-password",
  "full_name": "Admin User",
  "role": "admin"
}
```

2. **Login** with your credentials
3. **Start adding** job descriptions and candidates

### Development Mode (Optional)

To enable demo data for local testing, uncomment `seed_database()` in `backend/app/main.py`

## API Endpoints

### Authentication
- `POST /api/auth/register` - Register new user
- `POST /api/auth/login` - Login (OAuth2 form)
- `GET /api/auth/me` - Get current user

### Candidates
- `GET /api/candidates` - List candidates (with filters)
- `POST /api/candidates` - Create candidate
- `POST /api/candidates/upload` - Upload single resume
- `POST /api/candidates/bulk-upload` - Upload multiple resumes
- `GET /api/candidates/pipeline/stages` - Get Kanban board data
- `PATCH /api/candidates/{id}/stage` - Update candidate stage

### Jobs
- `GET /api/jobs` - List jobs
- `POST /api/jobs` - Create job
- `PUT /api/jobs/{id}` - Update job
- `DELETE /api/jobs/{id}` - Delete job

### Interviews
- `GET /api/interviews` - List interviews
- `POST /api/interviews` - Schedule interview
- `POST /api/interviews/{id}/complete` - Mark interview as complete

### Analytics
- `GET /api/analytics/dashboard-stats` - Dashboard KPIs
- `GET /api/analytics/hiring-funnel` - Funnel data
- `GET /api/analytics/skill-heatmap` - Skills analysis
- `GET /api/analytics/score-distribution` - Score ranges

### Email Templates
- `GET /api/email-templates` - List templates
- `POST /api/email-templates` - Create template
- `PUT /api/email-templates/{id}` - Update template
- `DELETE /api/email-templates/{id}` - Delete template

## Design Guidelines

- **Rounded cards** with border-radius: 12px
- **Soft shadows** for depth
- **Clean tables** with hover states
- **Modern typography** using Inter font
- **Professional color palette** with blue primary
- **Consistent 8px spacing grid**
- **Dark/Light mode support**

## License

MIT
