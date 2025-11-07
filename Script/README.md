# Vold - EHX Analysis Tool

Windows desktop application for analyzing EHX (Engineering Heat Exchange) data files.

## Features
- Tkinter-based GUI
- XML file parsing and analysis
- Data visualization and querying
- State persistence via JSON files

## Download

The latest Windows executable is automatically built via GitHub Actions:

1. Go to the [Actions tab](../../actions)
2. Click on the latest "Build Vold Windows Executable" workflow run
3. Download the `vold-windows` artifact
4. Extract and run `Vold.exe`

## Building Locally

### Requirements
- Python 3.11 or higher
- PyInstaller

### Build Steps

```bash
cd Script
pip install pyinstaller
pyinstaller Vold.spec
```

The executable will be in `dist/Vold.exe`

## Technical Details

- **Language**: Python 3.11
- **GUI Framework**: Tkinter (built into Python)
- **Build Tool**: PyInstaller
- **Platform**: Windows (no console window)
- **Size**: ~11 MB

## Configuration Files

The application uses these JSON files for state persistence:
- `gui_zones_state.json` - GUI state and preferences
- `gui_zones_last_folder.json` - Last accessed folder
- `gui_zones_log.json` - Application log data

These files are created automatically on first run.
