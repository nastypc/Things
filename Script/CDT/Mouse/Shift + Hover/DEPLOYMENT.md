# Quick Deployment Guide

## Option 1: Build Locally (Recommended for Testing)

1. **Run the build script:**
   ```powershell
   .\build_and_deploy.bat
   ```

2. **Test the executable:**
   - Rename `dist\ShiftHoverConverter.old` to `ShiftHoverConverter.exe`
   - Run it to test

3. **Push to GitHub:**
   ```powershell
   git add .
   git commit -m "Add Shift+Hover Converter with executable"
   git push origin master
   ```

## Option 2: Build on GitHub (Recommended for Distribution)

1. **Push code to GitHub:**
   ```powershell
   git add .
   git commit -m "Add Shift+Hover Converter source code"
   git push origin master
   ```

2. **GitHub will automatically build:**
   - Go to your repository on GitHub
   - Click "Actions" tab
   - Watch the build complete
   - Download the artifact from the build

3. **Create a release (optional):**
   ```powershell
   git tag v1.0.0
   git push origin v1.0.0
   ```
   - This creates a GitHub release with the executable attached

## File Safety Notes

### Why .old extension?
- Some antivirus software flags newly compiled executables
- The `.old` extension prevents automatic quarantine during development
- Users rename `.old` to `.exe` before running
- This is a common practice for distributing unsigned executables

### Antivirus False Positives
- PyInstaller executables often trigger Windows Defender
- This is normal for bundled Python applications
- Solutions:
  1. Add exclusion in Windows Security
  2. Code sign the executable (requires certificate)
  3. Build on GitHub Actions (trusted CI/CD)

## Distribution Checklist

- [ ] README.md updated with current features
- [ ] Tesseract OCR requirement documented
- [ ] Test executable on clean Windows machine
- [ ] Add code signing (optional, for enterprise use)
- [ ] Create GitHub release with version tag
- [ ] Update CHANGELOG.md with version notes

## GitHub Release Template

```markdown
## Shift+Hover MM to Imperial Converter v1.0.0

### Features
- Ctrl+Shift+Hover to convert mm to imperial
- Auto-dismiss tooltips (2 second display)
- Conversion history window with sorting
- Unique imperial filtering (no duplicates)
- System tray controls

### Installation
1. Download `ShiftHoverConverter.exe`
2. Install Tesseract OCR:
   ```
   winget install UB-Mannheim.TesseractOCR
   ```
3. Run the executable

### Files
- `ShiftHoverConverter.exe` - Main executable
- `ShiftHoverConverter.old` - Safe testing version (rename to .exe)
- `README.md` - Full documentation

### Requirements
- Windows 10/11
- Tesseract OCR installed at default path
```

## Troubleshooting Build Issues

**PyInstaller not found:**
```powershell
pip install pyinstaller
```

**Import errors:**
```powershell
pip install -r requirements.txt
```

**Large executable size:**
- Normal for PyInstaller (includes Python runtime)
- Typical size: 15-30 MB
- Use UPX compression (optional): `pyinstaller --upx-dir=path\to\upx ...`

**Git push rejected:**
```powershell
git pull --rebase origin master
git push origin master
```
