# Standalone Build & Run Guide

Use these steps to create a portable build of the CDT Sheathing Adjuster so it can run on a Windows machine that does **not** have Python installed.

## 1. Prerequisites on the build machine

1. **Python 3.11+ (64-bit)** installed with `pip` and the "tcl/tk" option (picked by default in the official installer).
2. **PowerShell** (already available on Windows 10/11).
3. Internet access to install PyInstaller the first time.

> The target/test machine does *not* need Python. Only the build machine requires it to package the app.

## 2. Install PyInstaller (one time)

```powershell
python -m pip install --upgrade pip
python -m pip install pyinstaller
```

## 3. Build the portable executable

From the repository root (`c:\Users\edward\Downloads\ET\Sheathing` in this workspace):

```powershell
cd c:\Users\edward\Downloads\ET\Sheathing
pyinstaller --noconfirm --windowed --name CDTAdjuster ^
  --add-data "src/config.json;src" ^
  --collect-all tkinter ^
  src/ED.py
```

### Notes

- `--windowed` keeps the console hidden (GUI-only). Remove it if you want console output.
- `--add-data` ensures the default `config.json` ships with the build. Add more `--add-data` entries if you rely on other resource files.
- `--collect-all tkinter` bundles the Tcl/Tk assets so the GUI works on machines without Python.

PyInstaller creates:

- `build/` – intermediate files (can delete after packaging).
- `dist/CDTAdjuster/` – the self-contained app folder.
- `CDTAdjuster.spec` – build spec (check into source control if you want repeatable builds).

## 4. Deploy to machines without Python

1. Copy the entire `dist/CDTAdjuster` folder to the other machine (USB, network share, etc.).
2. On the target machine, run `CDTAdjuster.exe` to launch the GUI.
3. Optional: create a shortcut to `CDTAdjuster.exe` for convenience.

Everything the program needs (Python interpreter, Tcl/Tk, stdlib, your script, `config.json`) lives inside that folder, so no system-wide installation is required.

## 5. Command-line usage

The packaged exe also supports the CLI mode:

```powershell
CDTAdjuster.exe path\to\wall.cdt
```

If a file path is supplied, it runs the same `process_cdt_file` workflow and prints the summary to stdout; otherwise it launches the GUI.

## 6. Updating the build

Whenever you modify source files:

1. Delete any old `dist`/`build` folders (optional but keeps things tidy).
2. Re-run the PyInstaller command above.
3. Copy the refreshed `dist/CDTAdjuster` folder to your target machines (overwrite existing files or version them as you prefer).

## 7. Troubleshooting

- **Missing DLL/Tk errors**: Ensure you kept the entire `dist/CDTAdjuster` folder together; don’t move just the exe.
- **Windows SmartScreen warning**: Because the exe is unsigned, Windows may warn on first run. Choose *More info → Run anyway* or sign the binary with your organization’s certificate.
- **Antivirus false positives**: Some AV suites flag unsigned PyInstaller bundles. Adding the folder to AV exceptions usually resolves it.

That’s it—once the `dist/CDTAdjuster` folder is copied, any Windows 10/11 machine can run the tool without installing Python.
