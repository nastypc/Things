# CDT Measurement Converter

A Windows desktop application that provides quick imperial conversions for CDT file measurements.

## Features

- **System Tray Icon** - Runs in background with easy access
- **Manual Converter** - GUI window for entering millimeter values
- **Clipboard Monitoring** - Automatically detects numbers in clipboard
- **Imperial Conversions** - Converts mm to feet-inches-sixteenths format
- **Standalone EXE** - No installation required, single executable file

## Usage

1. Run `cdt_converter_app.exe`
2. The app minimizes to system tray (blue square icon)
3. Right-click tray icon for options:
   - **Show Converter** - Open the conversion window
   - **Toggle Clipboard Monitor** - Auto-detect numbers in clipboard
   - **Exit** - Close the application

### Manual Conversion
- Enter millimeter value in the input field
- Imperial equivalent appears automatically
- Click "Copy to Clipboard" to copy the result

### Clipboard Monitoring
- When enabled, automatically detects numeric values copied to clipboard
- Useful when working with CDT files in text editors

## Requirements

- Windows 10/11
- No additional dependencies (all included in EXE)

## Building from Source

```bash
pip install -r requirements.txt
pyinstaller --onefile --windowed cdt_converter_app.py
```

The executable will be in the `dist/` folder.

## Imperial Conversion Format

Converts millimeters to standard construction format:
- `6096 mm` → `20'` (exactly 20 feet)
- `2470.15 mm` → `8'1 1/4"` (8 feet 1 1/4 inches)
- `241.3 mm` → `0'9 1/2"` (9 1/2 inches)