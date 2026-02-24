# Quick Deployment Guide - Stage Duration Tracking

## 🚀 Deploy in 3 Steps

### Step 1: Commit and Push
```bash
git add .
git commit -m "Add stage duration tracking to Pipeline Kanban board"
git push origin main
```

### Step 2: Run Migration (After Backend Deploys)
**Only needed if you have existing data in the database**

SSH into your server or use Railway CLI:
```bash
cd backend
python migrate_stage_duration.py
```

Expected output:
```
Using database: recruitment.db
Adding stage_entered_at column...
stage_entered_at column added
Adding applied_at column...
applied_at column added

Migration completed successfully!
```

### Step 3: Verify
1. Open your deployed app
2. Go to Pipeline tab
3. Check candidate cards show:
   - "Waiting: X days" badge
   - "Total: X days (Applied → Shortlisted)" on Shortlisted cards

## 🎯 What Changed

### User-Visible Features
- ⏱️ **Timer Badge**: Shows how long candidate has been in current stage
- 📊 **Total Days**: Shows time from application to shortlisted (Shortlisted stage only)
- 🚫 **No Badges on Rejected**: Clean UI for rejected candidates

### Technical Changes
- 2 new database columns: `stage_entered_at`, `applied_at`
- Updated API responses with timestamps
- Enhanced Pipeline UI with duration calculations

## 🔍 Testing

After deployment, test these scenarios:

1. **New Upload**: Upload a resume → should show "Waiting: few hours"
2. **Stage Change**: Move candidate to different stage → timer resets
3. **Shortlisted View**: Check Shortlisted cards → should show total days
4. **Rejected Stage**: Move to Rejected → badges disappear

## ⚠️ Important Notes

- Migration is **safe** - only adds columns, doesn't delete data
- Existing candidates get timestamps from `created_at` and `stage_updated_at`
- New candidates automatically get proper timestamps
- No downtime required

## 📝 Rollback (if needed)

If you need to rollback:
```bash
git revert HEAD
git push origin main
```

Database columns will remain but won't cause issues.

## ✅ Success Criteria

- [ ] Backend deploys without errors
- [ ] Migration runs successfully
- [ ] Pipeline shows duration badges
- [ ] Shortlisted cards show total days
- [ ] Rejected cards have no badges
- [ ] Timer updates correctly when moving stages

---

**Ready to deploy!** Run the commands above and you're done. 🎉
