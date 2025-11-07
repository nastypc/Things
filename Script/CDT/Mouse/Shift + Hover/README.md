# Ctrl+Shift+Hover MM to Imperial Converter

A Windows system tray application that displays imperial conversions for millimeter measurements when you hold Ctrl+Shift and hover over values in any document or application.

## Features

- **Ctrl+Shift+Hover Detection** - Hold Ctrl+Shift keys while hovering over millimeter values
- **OCR Text Recognition** - Automatically reads text under mouse cursor using Tesseract OCR
- **Imperial Conversions** - Converts mm to feet-inches-sixteenths format (e.g., `19'-2-7/8"`, `9-1/2"`, `7/8"`)
- **Auto-Dismiss Tooltips** - Floating tooltips appear for 2 seconds then auto-dismiss
- **Conversion History** - Track all unique conversions in a movable sticky note window
- **Smart Duplicate Filtering** - Only shows unique imperial results (prevents near-identical mm values from duplicating)
- **Auto-Sorted History** - Conversions sorted by mm value (smallest to largest)
- **System Tray Control** - Enable/disable functionality, view history, test OCR
- **No Installation** - Standalone executable with all dependencies bundled

## How It Works

1. **Run the Application** - Execute `auto_version.py` (or the compiled `.exe`)
2. **Look for Cyan Tray Icon** - "AU" icon appears in system tray
3. **Hover Over Numbers** - Hold Ctrl+Shift and move mouse over millimeter values
4. **View Conversion** - Green tooltip appears showing imperial conversion
5. **Check History** - Press Ctrl+Alt+H to see all conversions

## Requirements

- **Windows 10/11**
- **Tesseract OCR** - Must be installed at `C:\Program Files\Tesseract-OCR\tesseract.exe`
- **Python 3.8+** (if running from source)

## Installation

### Option 1: Install Tesseract OCR
```powershell
winget install UB-Mannheim.TesseractOCR
```

### Option 2: Run from Source
```bash
# Install Python dependencies
pip install -r requirements.txt

# Run the application
python auto_version.py
```

## Usage Examples

When hovering over text containing millimeter values:

| Original Value | Tooltip Display | Imperial Format |
|----------------|-----------------|-----------------|
| `6096:` | `6096.0 mm = 20'` | Feet only |
| `2470.15` | `2470.15 mm = 8'-1-1/4"` | Feet-inches-fraction |
| `241.3 mm` | `241.3 mm = 9-1/2"` | Inches-fraction |
| `14.29` | `14.29 mm = 9/16"` | Fraction only |
| `203.2 mm` | `203.2 mm = 8"` | Inches only |

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| **Ctrl+Shift** + Hover | Activate conversion tooltip |
| **Ctrl+Alt+H** | Show/hide conversion history window |
| **Ctrl+Alt+T** | Manual test at current cursor position |

## System Tray Controls

**Cyan "AU" Icon** in system tray

**Right-click menu:**
- **Toggle** - Enable/disable monitoring (checkbox)
- **Show History (Ctrl+Alt+H)** - Open conversion history window
- **Test (Ctrl+Alt+T)** - Test OCR at current mouse position
- **Quit** - Close the application

## Conversion History Window

Press **Ctrl+Alt+H** to open the floating history window:

**Features:**
- **Auto-sorted** - Conversions listed from smallest to largest mm value
- **No duplicates** - Only unique imperial results (e.g., `57.15 mm` and `57.45 mm` both convert to `2-1/4"`, only shown once)
- **Movable** - Drag window anywhere on screen
- **Always on top** - Stays visible over other windows
- **Dark theme** - Green text on dark background for easy reading

**Buttons:**
- **Clear All** - Delete all conversions and close history
- **Copy All** - Copy all conversions to clipboard for pasting
- **Close** - Hide window (conversions remain in memory)

**Example History Display:**
```
📋 Conversion History

1. 14.29 mm = 9/16"
2. 57.15 mm = 2-1/4"
3. 63.5 mm = 2-1/2"
4. 2470.15 mm = 8'-1-1/4"
5. 6096.0 mm = 20'

[Clear All] [Copy All]                [Close]
```

## Imperial Format Details

The converter displays measurements in standard architectural format:

**Fraction Simplification:**
- Even sixteenths simplified: `2/16" → 1/8"`, `4/16" → 1/4"`, `8/16" → 1/2"`
- Odd sixteenths preserved: `1/16"`, `3/16"`, `5/16"`, `7/16"`, etc.

**Format Examples:**
- `20'` - Feet only (no inches)
- `19'-2-7/8"` - Feet, inches, and fraction
- `19'-7/8"` - Feet and fraction (no whole inches)
- `9-1/2"` - Inches and fraction (no feet)
- `8"` - Inches only (no feet or fraction)
- `7/8"` - Fraction only (less than one inch)

## Technical Details

- **OCR Engine**: Tesseract 5.x with PSM modes 6, 7, and 8 for optimal text recognition
- **Screen Capture**: 70x25 pixel region centered on mouse cursor
- **Image Enhancement**: 3x contrast enhancement for better OCR accuracy
- **Text Cleaning**: Removes colons and non-numeric characters (handles "6096:" correctly)
- **Number Detection**: Regex pattern `\b(\d{1,5}\.?\d*)\b` for numbers 5-50000 mm
- **Tooltip Display**: Tkinter windows, 2-second auto-dismiss timer
- **Movement Threshold**: 20 pixels to trigger new OCR scan
- **Performance**: 100ms polling interval, threaded OCR processing

## Building Executable

```bash
# Install PyInstaller
pip install pyinstaller

# Create standalone EXE (will be in dist/ folder)
pyinstaller --onefile --windowed --name "ShiftHoverConverter" auto_version.py

# Note: Add Tesseract OCR path to system PATH or bundle it separately
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| **No tooltips appear** | Check that Ctrl+Shift+Hover monitoring is enabled (tray menu checkbox) |
| **OCR not working** | Verify Tesseract installed at `C:\Program Files\Tesseract-OCR\tesseract.exe` |
| **Wrong numbers detected** | OCR works best on clear, high-contrast text (black on white) |
| **History window won't open** | Press Ctrl+Alt+H again to toggle, check for errors in terminal |
| **Conversions incorrect** | Ensure input is in millimeters, range 5-50000 mm |

## Known Limitations

- **Text clarity**: Works best with clear, high-contrast, unrotated text
- **Font size**: Minimum recommended font size is 10pt
- **Screen region**: 70x25 pixel capture area, position cursor over number
- **Background apps**: May not work with certain full-screen games or protected applications
- **Tesseract required**: Must be installed separately, not bundled in EXE

## File Structure

```
Shift + Hover/
├── auto_version.py          # Main application (latest version)
├── requirements.txt         # Python dependencies
├── README.md               # This file
├── test_numbers.txt        # Test file with sample measurements
├── auto_capture.png        # Debug: last OCR screenshot
├── auto_enhanced.png       # Debug: enhanced OCR image
└── .github/
    └── copilot-instructions.md  # Development notes
```

## Version History

- **auto_version.py** - Latest: Auto-dismiss tooltips, conversion history, sorted display, unique imperial filtering
- **working_version.py** - MessageBox popups (requires clicking OK)
- **simple_version.py** - Windows notification balloons
- **bulletproof_version.py** - System modal MessageBox
- **final_version.py** - Precise 70x25 capture region
- **improved_version.py** - Enhanced OCR with image processing
- **debug_version.py** - Original version with extensive logging

## License

This tool is provided as-is for personal and professional use in construction, engineering, and manufacturing workflows.

## Credits

- **OCR**: Tesseract OCR by Google
- **Python Libraries**: pyautogui, pytesseract, keyboard, pystray, Pillow
- **Development**: Created for CDT measurement conversion workflows