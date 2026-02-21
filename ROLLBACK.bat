@echo off
echo ========================================
echo Git Rollback System
echo ========================================
echo.

echo Current branch:
git branch

echo.
echo Recent commits:
git log --oneline -10

echo.
echo ========================================
echo Rollback Options:
echo ========================================
echo 1. Rollback to previous commit (undo last commit, keep changes)
echo 2. Hard reset to previous commit (discard all changes)
echo 3. Rollback specific file
echo 4. View changes before rollback
echo 5. Cancel
echo.

set /p choice="Enter your choice (1-5): "

if "%choice%"=="1" goto soft_reset
if "%choice%"=="2" goto hard_reset
if "%choice%"=="3" goto file_reset
if "%choice%"=="4" goto view_changes
if "%choice%"=="5" goto end

:soft_reset
echo.
echo Performing soft reset (keeps your changes)...
git reset --soft HEAD~1
echo Done! Your changes are preserved but last commit is undone.
goto end

:hard_reset
echo.
echo WARNING: This will discard ALL uncommitted changes!
set /p confirm="Are you sure? (yes/no): "
if not "%confirm%"=="yes" goto end
git reset --hard HEAD~1
echo Done! Rolled back to previous commit.
goto end

:file_reset
echo.
set /p filepath="Enter file path to rollback (e.g., backend/app/routes/candidates.py): "
git checkout HEAD -- %filepath%
echo Done! File rolled back.
goto end

:view_changes
echo.
echo Uncommitted changes:
git status
echo.
echo Detailed diff:
git diff
goto end

:end
echo.
pause
