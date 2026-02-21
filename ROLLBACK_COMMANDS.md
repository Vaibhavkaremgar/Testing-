# Git Rollback Quick Reference

## 1. Rollback Last Commit (Keep Changes)
git reset --soft HEAD~1

## 2. Rollback Last Commit (Discard Changes)
git reset --hard HEAD~1

## 3. Rollback Specific File
git checkout HEAD -- backend/app/routes/candidates.py

## 4. Rollback to Specific Commit
git log --oneline -10
git reset --hard <commit-hash>

## 5. Undo Uncommitted Changes
git checkout -- .

## 6. View What Will Be Rolled Back
git diff HEAD~1

## 7. Create Backup Before Rollback
git branch backup-$(date +%Y%m%d-%H%M%S)

## 8. Rollback and Create New Branch
git checkout -b rollback-branch HEAD~1

## 9. Rollback Multiple Commits
git reset --hard HEAD~3

## 10. Rollback and Push (Force)
git reset --hard HEAD~1
git push origin main --force

## Emergency: Recover After Bad Rollback
git reflog
git reset --hard <commit-hash-from-reflog>
