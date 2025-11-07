@echo off
REM Build and Deploy Script for Shift+Hover Converter
REM Creates executable and prepares for GitHub deployment

echo ========================================
echo Building Shift+Hover Converter
echo ========================================
echo.

REM Step 1: Install PyInstaller if not already installed
echo [1/5] Checking PyInstaller...
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
) else (
    echo PyInstaller already installed
)
echo.

REM Step 2: Clean previous builds
echo [2/5] Cleaning previous builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist *.spec del /q *.spec
echo.

REM Step 3: Build the executable
echo [3/5] Building executable...
echo This may take a few minutes...
pyinstaller --onefile --windowed ^
    --name "ShiftHoverConverter" ^
    --icon=NONE ^
    --add-data "auto_version.py;." ^
    auto_version.py

if errorlevel 1 (
    echo ERROR: Build failed!
    pause
    exit /b 1
)
echo.

REM Step 4: Rename to .old to avoid antivirus false positives during testing
echo [4/5] Renaming executable...
if exist "dist\ShiftHoverConverter.exe" (
    copy "dist\ShiftHoverConverter.exe" "dist\ShiftHoverConverter.old"
    echo Created: dist\ShiftHoverConverter.old
    echo Note: Rename .old to .exe before running
) else (
    echo ERROR: Executable not found!
    pause
    exit /b 1
)
echo.

REM Step 5: Prepare deployment files
echo [5/5] Preparing deployment...
if not exist deploy mkdir deploy
copy "dist\ShiftHoverConverter.old" "deploy\" >nul
copy "README.md" "deploy\" >nul
copy "requirements.txt" "deploy\" >nul
echo.

echo ========================================
echo Build Complete!
echo ========================================
echo.
echo Files created:
echo   - dist\ShiftHoverConverter.exe (full executable)
echo   - dist\ShiftHoverConverter.old (safe for testing)
echo   - deploy\ folder (ready for deployment)
echo.
echo Next steps:
echo   1. Test: Rename .old to .exe and run it
echo   2. Deploy: Copy deploy\ folder contents to GitHub
echo   3. Commit: git add . ^&^& git commit -m "Add executable"
echo   4. Push: git push origin master
echo.
pause
