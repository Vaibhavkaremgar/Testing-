@echo off
echo ========================================
echo  TalentAI - Clean Dummy Data
echo ========================================
echo.
echo This script will remove all dummy data:
echo - Database file (talentai.db)
echo - Test resume uploads
echo.
echo WARNING: Make sure backend server is stopped!
echo.
pause

cd backend

echo.
echo [1/2] Removing database file...
if exist talentai.db (
    del talentai.db
    echo ✓ Database removed
) else (
    echo ✓ Database already removed
)

echo.
echo [2/2] Cleaning uploads folder...
if exist uploads (
    del /Q uploads\*.* 2>nul
    echo ✓ Uploads cleaned
) else (
    echo ✓ Uploads folder already clean
)

cd ..

echo.
echo ========================================
echo  ✓ Cleanup Complete!
echo ========================================
echo.
echo Your dashboard is now clean and ready for deployment.
echo.
echo Next steps:
echo 1. Commit changes to git
echo 2. Deploy to Railway
echo 3. Create your first admin user via API
echo.
echo See DEPLOYMENT_PREP.md for detailed instructions.
echo.
pause
