# Vold.py - EHX Reader and Panel Takeoff Tool

## Overview

Vold.py is a comprehensive GUI application built with Python and Tkinter for processing EHX (Engineering/Construction) files. It provides an interactive interface for analyzing structural panels, performing material takeoffs, and generating detailed reports for construction projects.

## Purpose

The application serves as an EHX file reader and analysis tool that:
- Parses EHX XML files containing structural panel and material data
- Provides a multi-zone GUI for browsing and analyzing panels
- Performs material takeoff calculations
- Generates export reports
- Maintains persistent state and user preferences

## Architecture

### Core Components

#### 1. GUI Framework
- **Tkinter-based interface** with professional styling
- **Three-zone layout**:
  - **Left Zone (White)**: File list and navigation
  - **Middle Zone (Yellow)**: Panel details and specifications
  - **Right Zone (Pink)**: Material breakdown and analysis

#### 2. File Processing System
- **EHX Parser**: XML-based file processing with fallback mechanisms
- **Panel Analysis**: Extracts panel geometry, materials, and specifications
- **Material Mapping**: Links materials to panels and subassemblies

#### 3. State Management
- **JSON-based persistence** for GUI layout and preferences
- **Automatic state recovery** on application startup
- **Dynamic zone sizing** with user-configurable layouts

### Key Classes and Functions

#### Main GUI Functions

##### `make_gui()`
**Purpose**: Creates the main application window and all GUI components
**Key Features**:
- Initializes Tkinter root window with professional styling
- Creates three-zone layout with scrollable canvases
- Sets up event bindings and tooltips
- Loads saved state from JSON files

##### `process_selected_ehx(evt=None)`
**Purpose**: Handles EHX file selection and initiates processing
**Process**:
1. Validates file selection
2. Shows loading status message
3. Launches background thread for file processing
4. Updates GUI with processed data

##### `complete_file_processing(panels, materials_map, full_path, folder_path)`
**Purpose**: Finalizes file processing on the main thread
**Operations**:
- Updates panel and material data structures
- Generates expected.log and materials.log files
- Updates level filtering and bundle display
- Clears loading status

#### Panel Display Functions

##### `display_panel(name, panel_obj, materials, yellow_data=None, pink_data=None, export_data=None)`
**Purpose**: Renders panel information in the GUI zones
**Zones Updated**:
- Yellow zone: Panel specifications, dimensions, beam pockets, critical studs
- Pink zone: Material breakdown with quantities and descriptions

##### `rebuild_bundles(count: int)`
**Purpose**: Manages the green zone button grid for panel navigation
**Features**:
- Dynamic button creation based on panel count
- Pagination support for large numbers of panels
- Font scaling based on available space
- Button highlighting for selected panels

#### Material Analysis Functions

##### `analyze_subassemblies_for_panel(ehx_path, panel_name, materials_param)`
**Purpose**: Analyzes subassembly relationships within panels
**Returns**: Dictionary mapping SubAssembly GUIDs to material lists

##### `create_takeoff_standalone_output(...)`
**Purpose**: Generates comprehensive takeoff reports
**Includes**: Panel specs, materials, beam pockets, critical studs, subassemblies

#### Utility Functions

##### `load_state(...)` / `save_state(...)`
**Purpose**: Manages GUI state persistence
**Files Created**:
- `gui_zones_state.json`: GUI layout dimensions
- `gui_zones_log.json`: Operation logs
- `gui_zones_last_folder.json`: Last browsed directory

##### `parse_dimension_to_feet(dim_str)` / `format_feet_to_dimension(feet)`
**Purpose**: Handles dimension conversions between various formats
**Supports**: Feet-inches-sixteenths, decimal feet, fractional inches

## Data Flow

### EHX File Processing Pipeline

1. **File Selection**: User double-clicks EHX file in left zone
2. **Background Processing**: Threaded file parsing to prevent GUI freezing
3. **XML Parsing**: Extracts panels, materials, levels, and bundles
4. **Data Structuring**: Organizes data into dictionaries and mappings
5. **Log Generation**: Creates expected.log and materials.log files
6. **GUI Update**: Populates zones with processed data
7. **State Persistence**: Saves current state to JSON files

### Panel Analysis Flow

1. **Panel Selection**: User clicks panel button in green zone
2. **Data Retrieval**: Fetches panel object and associated materials
3. **Detail Rendering**: Populates yellow zone with specifications
4. **Material Calculation**: Processes pink zone with material breakdown
5. **Export Preparation**: Formats data for export functionality

## Configuration and State Files

### JSON State Files

#### `gui_zones_state.json`
```json
{
  "left_w": 184,
  "details_w": 500,
  "breakdown_w": 940,
  "green_h": 264,
  "debug_enabled": true
}
```

#### `gui_zones_last_folder.json`
```json
{
  "last_folder": "C:\\Path\\To\\EHX\\Files"
}
```

### Log Files

#### `gui_zones_log.json`
Contains timestamped operation logs for debugging and state changes.

#### `expected.log` / `materials.log`
Generated next to processed EHX files containing panel and material data.

## Build and Deployment

### PyInstaller Build Process

#### Vold.spec Configuration
```python
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['Vold.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('README.txt', '.'),
    ],
    hiddenimports=[
        'xml.etree.ElementTree',
        'tkinter',
        'tkinter.ttk',
        'json',
        'os',
        'sys',
        'threading',
        'tkinter.font',
        'tkinter.messagebox',
        'tkinter.filedialog'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
```

#### Build Commands
```bash
# Using spec file (recommended)
pyinstaller Vold.spec

# Alternative direct build
pyinstaller --onefile --add-data "README.txt;." Vold.py
```

### Distribution Package
The built executable creates a `dist` folder containing:
- `Vold.exe`: Main executable
- Supporting DLLs and libraries
- `README.txt`: User documentation

## Recovery Procedures

### Source Code Recovery from Executable

While Python-to-exe tools are designed as one-way conversions, PyInstaller executables can sometimes be partially recovered:

#### Method 1: PyInstaller Extraction
```bash
# Install pyinstxtractor
pip install pyinstxtractor

# Extract executable contents
python pyinstxtractor.py Vold.exe
```

#### Method 2: Bytecode Decompilation
```bash
# Install decompiler
pip install uncompyle6

# Decompile extracted .pyc files
uncompyle6 -o output_dir extracted_file.pyc
```

**Note**: Decompiled code may not be identical to original source and may require manual reconstruction.

### State File Recovery

If JSON state files are corrupted or lost:
1. Delete existing `.json` files
2. Restart application - new defaults will be created
3. Reconfigure GUI layout preferences

### Log File Analysis

Check `gui_zones_log.json` for:
- Recent operations and errors
- State change history
- File processing attempts

## Key Features

### GUI Features
- **Responsive Design**: Zones resize dynamically
- **Threaded Processing**: Background file operations prevent freezing
- **State Persistence**: Remembers user preferences and layout
- **Tooltip Support**: Contextual help for UI elements
- **Keyboard Shortcuts**: Lock/reset view functionality

### Processing Features
- **Multi-format Support**: Handles various EHX file structures
- **Level Filtering**: Filter panels by building level
- **Material Analysis**: Comprehensive material breakdown
- **Export Functionality**: Generate detailed reports
- **Debug Mode**: Extensive logging and error reporting

### Material Analysis
- **Family Member Mapping**: Intelligent material categorization
- **Dimension Processing**: Multiple format support for measurements
- **Board Foot Calculations**: Accurate material quantity calculations
- **Subassembly Tracking**: Links materials to structural components

## Dependencies

### Required Python Packages
- `tkinter` (built-in)
- `xml.etree.ElementTree` (built-in)
- `json` (built-in)
- `os`, `sys`, `threading` (built-in)

### Build Dependencies
- `PyInstaller >= 6.0.0`
- Python 3.8+ (tested with 3.13.2)

## Troubleshooting

### Common Issues

#### GUI Won't Start
- Check Python version compatibility
- Verify all imports are available
- Check for missing state files (delete and restart)

#### EHX Files Won't Load
- Verify file is valid XML
- Check EHX version compatibility
- Review debug logs for parsing errors

#### State Files Corrupted
- Delete `.json` files in script directory
- Application will recreate with defaults

#### Build Fails
- Update PyInstaller: `pip install --upgrade pyinstaller`
- Check Vold.spec for correct paths
- Ensure all data files exist

### Debug Mode
Enable debug mode via GUI checkbox or modify `DEBUG_ENABLED = True` in source.

## File Structure Reference

```
Project Root/
├── Vold.py                 # Main application script
├── Vold.spec              # PyInstaller configuration
├── README.md              # This documentation
├── gui_zones_state.json   # GUI layout preferences
├── gui_zones_log.json     # Operation logs
├── gui_zones_last_folder.json  # Last directory
├── expected.log           # Generated panel data
├── materials.log          # Generated material data
└── dist/                  # Built executable folder
    ├── Vold.exe
    └── README.txt
```

## Version History

### Current Version Features
- Threaded file processing for responsive GUI
- Dynamic zone sizing with state persistence
- Comprehensive material analysis and takeoff
- Multi-level building support
- Export functionality
- Professional UI styling

## Future Enhancements

### Potential Improvements
- Additional EHX version support
- Enhanced export formats (PDF, Excel)
- Material database integration
- Cloud backup for state files
- Plugin architecture for custom analysis

---

**Note**: This documentation serves as both a reference guide and recovery resource. Keep backups of the original Python source files, as executable conversion is primarily intended for distribution rather than source code protection.