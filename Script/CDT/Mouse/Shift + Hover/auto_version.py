#!/usr/bin/env python3
"""
AUTO-DISMISS Ctrl+Shift+Hover Converter with floating overlay
"""

import pyautogui
import pytesseract
import keyboard
import threading
import time
import re
import queue
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw, ImageGrab, ImageEnhance
import os
import sys
import tkinter as tk
from tkinter import ttk

# Set tesseract path - try bundled first, then fallback to system install
if getattr(sys, 'frozen', False):
    # Running as compiled exe - use bundled Tesseract
    bundle_dir = os.path.dirname(sys.executable)
    tesseract_path = os.path.join(bundle_dir, 'Tesseract-OCR', 'tesseract.exe')
else:
    # Running as script - use system install
    tesseract_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Verify Tesseract exists
if os.path.exists(tesseract_path):
    pytesseract.pytesseract.tesseract_cmd = tesseract_path
    print(f"AUTO: Tesseract found at {tesseract_path}")
else:
    print(f"AUTO: WARNING - Tesseract not found at {tesseract_path}")
    print("AUTO: OCR will not work. Please install Tesseract or ensure bundled version exists.")


def mm_to_imperial(mm_value):
    """Convert millimeters to imperial format: 19'-2-7/8" or 7/8" or 20' or 9-1/2" or 8\" """
    inches = mm_value / 25.4
    feet = int(inches // 12)
    remaining_inches = inches % 12
    sixteenths = round(remaining_inches * 16)

    inches_whole = sixteenths // 16
    sixteenths_remainder = sixteenths % 16
    
    # Handle rollover: if inches_whole >= 12, add to feet
    if inches_whole >= 12:
        feet += inches_whole // 12
        inches_whole = inches_whole % 12

    # Simplify fractions
    fractions = {2: "1/8", 4: "1/4", 6: "3/8", 8: "1/2", 10: "5/8", 12: "3/4", 14: "7/8"}
    fraction = fractions.get(sixteenths_remainder, f"{sixteenths_remainder}/16")

    # Format output
    if feet > 0:
        if inches_whole > 0:
            if sixteenths_remainder > 0:
                return f"{feet}'-{inches_whole}-{fraction}\""  # 19'-2-7/8"
            else:
                return f"{feet}'-{inches_whole}\""  # 19'-2"
        else:
            if sixteenths_remainder > 0:
                return f"{feet}'-{fraction}\""  # 19'-7/8"
            else:
                return f"{feet}'"  # 20'
    else:
        if inches_whole > 0:
            if sixteenths_remainder > 0:
                return f"{inches_whole}-{fraction}\""  # 9-1/2"
            else:
                return f"{inches_whole}\""  # 8"
        else:
            if sixteenths_remainder > 0:
                return f"{fraction}\""  # 7/8"
            else:
                return "0\""


class AutoDismissConverter:
    def __init__(self):
        print("AUTO: Starting Auto-Dismiss Ctrl+Shift+Hover Converter...")
        
        self.monitoring = True
        self.active = False
        self.last_position = (0, 0)
        self.last_conversion = ""
        self.tooltip = None
        self.tooltip_timer = None
        
        # History tracking
        self.conversion_history = []  # List of unique conversions
        self.imperial_values_seen = set()  # Track imperial results to prevent duplicates
        self.history_window = None
        self.history_text_widget = None
        
        # Track original values for color coding and revert
        self.original_values = {}  # {mm_value: original_mm_value}
        self.value_colors = {}  # {mm_value: 'green' or 'red'}
        self.active_cdt_file = None  # Path to currently active CDT file
        
        # Create hidden root window for Toplevel windows
        self.root = tk.Tk()
        self.root.withdraw()  # Hide it
        
        # Create system tray
        self.create_tray_icon()
        
        # Start keyboard/mouse monitoring
        self.start_monitoring()
        
        # Manual test hotkey
        keyboard.add_hotkey('ctrl+alt+t', self.manual_test)
        
        # Show/hide history hotkey
        keyboard.add_hotkey('ctrl+alt+h', self.toggle_history_window)

    def create_tray_icon(self):
        """Create system tray icon"""
        try:
            # Cyan icon for auto version
            image = Image.new('RGBA', (64, 64), color=(0, 255, 255, 255))
            draw = ImageDraw.Draw(image)
            draw.ellipse([8, 8, 56, 56], fill=(255, 255, 255, 255))
            draw.text((22, 25), "AU", fill=(0, 0, 0, 255))

            menu = Menu(
                MenuItem('Toggle', self.toggle_monitoring, checked=lambda item: self.monitoring),
                MenuItem('Show History (Ctrl+Alt+H)', self.toggle_history_window, checked=lambda item: self.is_history_visible()),
                MenuItem('Test (Ctrl+Alt+T)', self.manual_test),
                MenuItem('Quit', self.quit_app)
            )

            self.icon = Icon("Auto Dismiss", image, "Auto Dismiss Converter", menu)
            print("AUTO: System tray created")
        except Exception as e:
            print(f"AUTO: Tray error: {e}")
    
    def is_history_visible(self):
        """Check if history window is visible"""
        try:
            return self.history_window is not None and self.history_window.winfo_viewable()
        except:
            return False

    def toggle_monitoring(self, icon=None, item=None):
        """Toggle monitoring"""
        self.monitoring = not self.monitoring
        print(f"AUTO: Monitoring {'ON' if self.monitoring else 'OFF'}")

    def toggle_history_window(self):
        """Toggle the history sticky note visibility"""
        try:
            if self.history_window is None:
                # Create sticky note window (simple, no separate thread)
                print("AUTO: Creating history sticky note")
                self.create_history_sticky_note()
            else:
                # Hide/Show toggle
                if self.history_window.winfo_viewable():
                    print("AUTO: Hiding history sticky note")
                    self.history_window.withdraw()
                else:
                    print("AUTO: Showing history sticky note")
                    self.history_window.deiconify()
        except Exception as e:
            print(f"AUTO: Toggle error: {e}")
            self.history_window = None
            self.history_text_widget = None
    
    def create_history_sticky_note(self):
        """Create a simple sticky note window (uses main event loop - no threading!)"""
        try:
            # Create toplevel window (not Tk - uses system tray's event loop)
            self.history_window = tk.Toplevel()
            self.history_window.title("📋 Conversions")
            self.history_window.geometry("320x450+50+50")
            self.history_window.attributes('-topmost', True)
            self.history_window.configure(bg='#2d2d2d')
            
            # Prevent closing, just hide instead
            self.history_window.protocol("WM_DELETE_WINDOW", lambda: self.history_window.withdraw())
            
            # Header with buttons
            header_frame = tk.Frame(self.history_window, bg='#2d2d2d')
            header_frame.pack(fill='x', padx=5, pady=5)
            
            title = tk.Label(
                header_frame,
                text="📋 Conversion History",
                font=('Segoe UI', 11, 'bold'),
                bg='#2d2d2d',
                fg='#00ff00'
            )
            title.pack(side='left')
            
            # Mini buttons in header
            btn_frame = tk.Frame(header_frame, bg='#2d2d2d')
            btn_frame.pack(side='right')
            
            clear_btn = tk.Button(
                btn_frame,
                text="Clear",
                command=self.clear_history,
                bg='#d32f2f',
                fg='white',
                font=('Segoe UI', 8),
                width=6,
                relief='raised',
                cursor='hand2',
                activebackground='#b71c1c',
                activeforeground='white'
            )
            clear_btn.pack(side='left', padx=2)
            
            copy_btn = tk.Button(
                btn_frame,
                text="Copy",
                command=self.copy_history,
                bg='#1976d2',
                fg='white',
                font=('Segoe UI', 8),
                width=6,
                relief='raised',
                cursor='hand2',
                activebackground='#1565c0',
                activeforeground='white'
            )
            copy_btn.pack(side='left', padx=2)
            
            # Scrollable text area
            text_frame = tk.Frame(self.history_window)
            text_frame.pack(fill='both', expand=True, padx=5, pady=(0, 5))
            
            scrollbar = tk.Scrollbar(text_frame)
            scrollbar.pack(side='right', fill='y')
            
            self.history_text_widget = tk.Text(
                text_frame,
                font=('Consolas', 9),
                bg='#1e1e1e',
                fg='#00ff00',
                yscrollcommand=scrollbar.set,
                wrap='word',
                padx=8,
                pady=8,
                relief='flat',
                cursor='hand2'  # Show it's clickable
            )
            self.history_text_widget.pack(side='left', fill='both', expand=True)
            scrollbar.config(command=self.history_text_widget.yview)
            
            # Make text widget read-only by blocking keyboard input
            def block_input(event):
                # Allow Ctrl+C for copy but block other keys
                if event.keysym == 'c' and (event.state & 0x4):  # Ctrl is pressed
                    return
                return "break"
            
            self.history_text_widget.bind('<Key>', block_input)
            
            # Debug: Add single-click handler to test if ANY clicks work
            def on_single_click(event):
                print(f"AUTO: *** SINGLE CLICK at ({event.x}, {event.y}) ***")
                return
            
            self.history_text_widget.bind('<Button-1>', on_single_click)
            
            # Bind double-click to replace value
            self.history_text_widget.bind('<Double-Button-1>', self.on_history_double_click)
            
            # Bind right-click for context menu
            self.history_text_widget.bind('<Button-3>', self.on_history_right_click)
            
            # Populate with existing history
            self.update_history_display()
            
            print("AUTO: History sticky note created")
            
        except Exception as e:
            print(f"AUTO: Error creating sticky note: {e}")

    def update_history_display(self):
        """Update the sticky note with current conversions - with color coding"""
        if not self.history_text_widget or not self.history_window:
            return
        
        # Schedule in main thread if called from another thread
        def do_update():
            try:
                if not self.history_text_widget or not self.history_window:
                    return
                    
                self.history_text_widget.config(state='normal')
                self.history_text_widget.delete('1.0', 'end')
                
                # Configure color tags
                self.history_text_widget.tag_config('green', foreground='#00ff00')
                self.history_text_widget.tag_config('red', foreground='#ff6b6b')
                
                if not self.conversion_history:
                    self.history_text_widget.insert('1.0', "No conversions yet.\n\nHold Ctrl+Shift\nand hover over\nmillimeter values.")
                else:
                    # Sort by mm value (smallest to largest)
                    sorted_conversions = sorted(
                        self.conversion_history,
                        key=lambda x: float(x.split(' mm')[0]) if ' mm' in x else 0
                    )
                    
                    for i, conversion in enumerate(sorted_conversions, 1):
                        # Extract mm value to check color
                        try:
                            mm_value = float(conversion.split(' mm')[0])
                            color_tag = self.value_colors.get(mm_value, 'green')
                        except:
                            color_tag = 'green'
                        
                        line_text = f"{i}. {conversion}\n"
                        self.history_text_widget.insert('end', line_text, color_tag)
                
                # Keep in 'normal' state so mouse events work (keyboard blocked separately)
                self.history_text_widget.see('end')
                print(f"AUTO: Sticky note updated ({len(self.conversion_history)} items)")
            except Exception as e:
                print(f"AUTO: Update error: {e}")
        
        try:
            # Schedule in Tkinter's main thread
            self.root.after(0, do_update)
        except Exception as e:
            print(f"AUTO: Schedule error: {e}")

    def add_to_history(self, conversion, imperial_value):
        """Add conversion to history if imperial result not already present"""
        try:
            # Extract mm value for tracking
            mm_value = float(conversion.split(' mm')[0])
            
            if imperial_value not in self.imperial_values_seen:
                self.imperial_values_seen.add(imperial_value)
                self.conversion_history.append(conversion)
                
                # Track original value if not already tracked
                if mm_value not in self.original_values:
                    self.original_values[mm_value] = mm_value
                    self.value_colors[mm_value] = 'green'  # Original = green
                
                print(f"AUTO: Added to history: {conversion}")
                # Update sticky note if it exists
                if self.history_text_widget and self.history_window:
                    self.update_history_display()
                return True
            else:
                print(f"AUTO: Skipped duplicate: {conversion}")
                return False
        except Exception as e:
            print(f"AUTO: Error adding to history: {e}")
            return False

    def clear_history(self):
        """Clear all conversion history"""
        try:
            print("AUTO: *** CLEAR BUTTON CLICKED ***")
            self.conversion_history.clear()
            self.imperial_values_seen.clear()
            self.original_values.clear()
            self.value_colors.clear()
            if self.history_text_widget and self.history_window:
                self.update_history_display()
            print("AUTO: History cleared (all values reset)")
        except Exception as e:
            print(f"AUTO: Error clearing history: {e}")
            import traceback
            traceback.print_exc()

    def copy_history(self):
        """Copy all conversions to clipboard"""
        try:
            print("AUTO: *** COPY BUTTON CLICKED ***")
            if self.conversion_history:
                clipboard_text = "\n".join(f"{i}. {conv}" for i, conv in enumerate(self.conversion_history, 1))
                # Use pyperclip-style clipboard (simpler)
                import subprocess
                subprocess.run(['clip'], input=clipboard_text.encode('utf-16'), check=True)
                print(f"AUTO: Copied {len(self.conversion_history)} conversions")
            else:
                print("AUTO: No conversions to copy")
        except Exception as e:
            print(f"AUTO: Copy error: {e}")
            import traceback
            traceback.print_exc()

    def on_history_double_click(self, event):
        """Handle double-click on history entry to replace value"""
        try:
            print(f"AUTO: *** DOUBLE-CLICK DETECTED at ({event.x}, {event.y}) ***")
            
            # Get the line that was double-clicked
            index = self.history_text_widget.index("@%s,%s" % (event.x, event.y))
            print(f"AUTO: Text widget index: {index}")
            
            line_num = int(index.split('.')[0])
            line_text = self.history_text_widget.get(f"{line_num}.0", f"{line_num}.end")
            
            print(f"AUTO: Double-clicked line {line_num}: '{line_text}'")
            
            # Extract mm value from line (format: "1. 5400.0 mm = 17'-8-1/4"")
            match = re.search(r'(\d+(?:\.\d+)?)\s*mm', line_text)
            if match:
                old_value = match.group(1)
                print(f"AUTO: Extracted mm value: {old_value}")
                print(f"AUTO: Calling show_replace_dialog...")
                
                # Show input dialog for new value
                self.show_replace_dialog(old_value)
                print(f"AUTO: Dialog should be visible now")
            else:
                print(f"AUTO: No mm value found in clicked line: '{line_text}'")
                
        except Exception as e:
            print(f"AUTO: Double-click error: {e}")
            import traceback
            traceback.print_exc()
    
    def on_history_right_click(self, event):
        """Handle right-click on history entry - show context menu"""
        try:
            # Get the line that was right-clicked
            index = self.history_text_widget.index("@%s,%s" % (event.x, event.y))
            line_num = int(index.split('.')[0])
            line_text = self.history_text_widget.get(f"{line_num}.0", f"{line_num}.end")
            
            print(f"AUTO: Right-clicked line {line_num}: '{line_text}'")
            
            # Extract mm value
            match = re.search(r'(\d+(?:\.\d+)?)\s*mm', line_text)
            if not match:
                print("AUTO: No mm value found in clicked line")
                return
            
            mm_value = float(match.group(1))
            
            # Check if this value was modified (red)
            is_modified = mm_value in self.value_colors and self.value_colors[mm_value] == 'red'
            original_value = self.original_values.get(mm_value)
            
            # Create context menu
            menu = tk.Menu(self.history_window, tearoff=0, bg='#2d2d2d', fg='#ffffff')
            
            # Always show "Replace with..." option
            menu.add_command(
                label=f"Replace {match.group(1)}...",
                command=lambda: self.show_replace_dialog(match.group(1))
            )
            
            # If modified, show "Restore Original" option
            if is_modified and original_value is not None:
                menu.add_separator()
                menu.add_command(
                    label=f"🔄 Restore Original ({original_value})",
                    command=lambda: self.restore_original_value(match.group(1), original_value)
                )
            
            # Show menu at cursor position
            menu.post(event.x_root, event.y_root)
            
        except Exception as e:
            print(f"AUTO: Right-click error: {e}")
    
    def restore_original_value(self, current_value, original_value):
        """Restore a modified value back to its original"""
        try:
            print(f"AUTO: Restoring {current_value} → {original_value}")
            self.replace_in_active_window(current_value, str(original_value))
        except Exception as e:
            print(f"AUTO: Restore error: {e}")

    def show_replace_dialog(self, old_value):
        """Show dialog to enter new value for replacement"""
        try:
            print(f"AUTO: *** show_replace_dialog called with old_value='{old_value}' ***")
            
            # Check if this value was modified - show original if available
            old_num = float(old_value)
            original_value = self.original_values.get(old_num)
            is_modified = old_num in self.value_colors and self.value_colors[old_num] == 'red'
            
            print(f"AUTO: old_num={old_num}, original={original_value}, is_modified={is_modified}")
            
            # Create dialog window
            dialog = tk.Toplevel(self.root)
            dialog.title("Replace Value")
            dialog.geometry("400x240" if is_modified else "400x180")
            dialog.attributes('-topmost', True)
            dialog.configure(bg='#2d2d2d')
            dialog.resizable(False, False)
            
            print(f"AUTO: Dialog window created")
            
            # DON'T make it modal to parent - just make it topmost
            # The parent is hidden anyway, so transient/grab_set causes issues
            dialog.focus_force()  # Force focus to dialog
            
            print(f"AUTO: Dialog focus forced")
            
            # Center on screen
            dialog.update_idletasks()
            x = (dialog.winfo_screenwidth() // 2) - (400 // 2)
            y = (dialog.winfo_screenheight() // 2) - ((240 if is_modified else 180) // 2)
            dialog.geometry(f"+{x}+{y}")
            
            # Show original value if this was modified
            if is_modified and original_value is not None:
                orig_frame = tk.Frame(dialog, bg='#2d2d2d')
                orig_frame.pack(pady=(10, 5))
                
                orig_label = tk.Label(
                    orig_frame,
                    text="Original value:",
                    font=('Segoe UI', 9),
                    bg='#2d2d2d',
                    fg='#888888'
                )
                orig_label.pack(side='left', padx=5)
                
                orig_value_label = tk.Label(
                    orig_frame,
                    text=str(original_value),
                    font=('Consolas', 10, 'bold'),
                    bg='#2d2d2d',
                    fg='#00ff00'
                )
                orig_value_label.pack(side='left', padx=5)
            
            # Title label
            title_label = tk.Label(
                dialog,
                text=f"Replace all instances of:",
                font=('Segoe UI', 11, 'bold'),
                bg='#2d2d2d',
                fg='#ffffff'
            )
            title_label.pack(pady=(15 if not is_modified else 5, 5))
            
            # Old value display (red if modified, yellow if original)
            old_label = tk.Label(
                dialog,
                text=old_value,
                font=('Consolas', 14, 'bold'),
                bg='#1e1e1e',
                fg='#ff6b6b' if is_modified else '#ffeb3b',
                padx=10,
                pady=5
            )
            old_label.pack(pady=5)
            
            # "With new value:" label
            with_label = tk.Label(
                dialog,
                text="With new value:",
                font=('Segoe UI', 10),
                bg='#2d2d2d',
                fg='#ffffff'
            )
            with_label.pack(pady=(10, 5))
            
            # Entry for new value
            entry_var = tk.StringVar(value=old_value)
            entry = tk.Entry(
                dialog,
                textvariable=entry_var,
                font=('Consolas', 14),
                width=20,
                bg='#1e1e1e',
                fg='#00ff00',
                insertbackground='#00ff00',
                relief='solid',
                borderwidth=1
            )
            entry.pack(pady=5)
            entry.select_range(0, 'end')
            entry.focus_set()
            
            # Button frame
            btn_frame = tk.Frame(dialog, bg='#2d2d2d')
            btn_frame.pack(pady=15)
            
            def on_ok():
                new_value = entry_var.get().strip()
                if new_value and new_value != old_value:
                    print(f"AUTO: Replacing '{old_value}' with '{new_value}'")
                    self.replace_in_active_window(old_value, new_value)
                    dialog.destroy()
                else:
                    print("AUTO: No replacement - same value or empty")
                    dialog.destroy()
            
            def on_cancel():
                print("AUTO: Replacement cancelled")
                dialog.destroy()
            
            # OK button
            ok_btn = tk.Button(
                btn_frame,
                text="Replace All",
                command=on_ok,
                bg='#4caf50',
                fg='white',
                font=('Segoe UI', 10, 'bold'),
                width=12,
                relief='raised',
                cursor='hand2',
                activebackground='#45a049',
                activeforeground='white',
                borderwidth=2
            )
            ok_btn.pack(side='left', padx=5)
            
            # Cancel button
            cancel_btn = tk.Button(
                btn_frame,
                text="Cancel",
                command=on_cancel,
                bg='#757575',
                fg='white',
                font=('Segoe UI', 10),
                width=12,
                relief='raised',
                cursor='hand2',
                activebackground='#616161',
                activeforeground='white',
                borderwidth=2
            )
            cancel_btn.pack(side='left', padx=5)
            
            # Bind Enter and Escape keys
            entry.bind('<Return>', lambda e: on_ok())
            entry.bind('<KP_Enter>', lambda e: on_ok())
            dialog.bind('<Escape>', lambda e: on_cancel())
            
            print(f"AUTO: Replace dialog shown for value: {old_value}")
            
        except Exception as e:
            print(f"AUTO: Dialog error: {e}")

    def replace_in_active_window(self, old_value, new_value):
        """Replace all instances of old_value with new_value directly in CDT file"""
        try:
            print(f"AUTO: Starting direct file replacement: '{old_value}' → '{new_value}'")
            
            # Find CDT file to edit
            cdt_file = self.find_cdt_file()
            if not cdt_file:
                print("AUTO: No CDT file found!")
                return
            
            print(f"AUTO: Editing file: {cdt_file}")
            
            # Read entire file (handle BOM if present)
            with open(cdt_file, 'r', encoding='utf-8-sig') as f:
                content = f.read()
            
            # Normalize values - remove .0 suffix if present to match CDT format
            # CDT files store integers without decimals (6096 not 6096.0)
            old_search = old_value.rstrip('0').rstrip('.') if '.' in old_value else old_value
            new_search = new_value.rstrip('0').rstrip('.') if '.' in new_value else new_value
            
            print(f"AUTO: Normalized search: '{old_search}' → '{new_search}'")
            
            # Count replacements - need to match whole numbers, not partial
            # Use regex to match the number with word boundaries
            import re
            pattern = r'\b' + re.escape(old_search) + r'\b'
            matches = re.findall(pattern, content)
            count = len(matches)
            
            print(f"AUTO: Found {count} instances of '{old_search}'")
            
            if count == 0:
                print("AUTO: No instances found to replace")
                print(f"AUTO: File preview (first 500 chars): {content[:500]}")
                return
            
            # Replace all instances using regex for whole number matching
            new_content = re.sub(pattern, new_search, content)
            
            # Write back to file
            with open(cdt_file, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            print(f"AUTO: Replaced {count} instances and saved file!")
            
            # Update tracking: mark as modified
            try:
                old_num = float(old_value)
                new_num = float(new_value)
                
                # If reverting to original, mark green
                if old_num in self.original_values and new_num == self.original_values[old_num]:
                    self.value_colors[new_num] = 'green'
                else:
                    # Modified value, mark red
                    if new_num not in self.original_values:
                        self.original_values[new_num] = old_num
                    self.value_colors[new_num] = 'red'
                
                # Update history with new conversion
                imperial = mm_to_imperial(new_num)
                new_conversion = f"{new_num} mm = {imperial}"
                
                # Remove old conversion from history
                old_conversion_start = f"{old_num} mm"
                self.conversion_history = [c for c in self.conversion_history if not c.startswith(old_conversion_start)]
                
                # Add new conversion
                self.imperial_values_seen.discard(imperial)
                self.add_to_history(new_conversion, imperial)
                
                print(f"AUTO: History updated: {new_conversion} (color: {self.value_colors.get(new_num, 'unknown')})")
            except ValueError:
                print(f"AUTO: Could not update history - invalid number")
            
        except Exception as e:
            print(f"AUTO: Replacement error: {e}")
            import traceback
            traceback.print_exc()
    
    def find_cdt_file(self):
        """Find active CDT file - tries multiple methods"""
        # Method 1: Check if P2.CDT exists in workspace (most commonly used)
        workspace_cdt = r"C:\Users\edward\Downloads\EHX\Script\CDT\Mouse\Shift + Hover\P2.CDT"
        print(f"AUTO: Checking for CDT at: {workspace_cdt}")
        if os.path.exists(workspace_cdt):
            print(f"AUTO: Found P2.CDT file!")
            return workspace_cdt
        
        # Method 1b: Fallback to P1.CDT
        workspace_cdt = r"C:\Users\edward\Downloads\EHX\Script\CDT\Mouse\Shift + Hover\P1.CDT"
        print(f"AUTO: Checking for CDT at: {workspace_cdt}")
        if os.path.exists(workspace_cdt):
            print(f"AUTO: Found P1.CDT file!")
            return workspace_cdt
        
        # Method 2: Look for any .CDT file in workspace
        workspace_dir = os.path.dirname(__file__) if not getattr(sys, 'frozen', False) else os.path.dirname(sys.executable)
        print(f"AUTO: Searching workspace dir: {workspace_dir}")
        try:
            for file in os.listdir(workspace_dir):
                if file.upper().endswith('.CDT'):
                    cdt_path = os.path.join(workspace_dir, file)
                    print(f"AUTO: Found CDT file: {cdt_path}")
                    return cdt_path
        except Exception as e:
            print(f"AUTO: Error searching workspace: {e}")
        
        print("AUTO: No CDT file found - please select file manually")
        
        # Method 3: File picker as fallback
        from tkinter import filedialog
        cdt_path = filedialog.askopenfilename(
            title="Select CDT file to edit",
            filetypes=[("CDT files", "*.CDT"), ("All files", "*.*")],
            initialdir=r"C:\Users\edward\Downloads\EHX\Script\CDT\Mouse\Shift + Hover"
        )
        
        if cdt_path:
            print(f"AUTO: User selected: {cdt_path}")
            return cdt_path
        
        print("AUTO: No file selected")
        return None

    def show_tooltip(self, text, x, y):
        """Show auto-dismissing tooltip overlay - uses Toplevel instead of Tk"""
        def create_and_show():
            try:
                # Close existing tooltip properly
                if self.tooltip:
                    try:
                        self.root.after(0, self.tooltip.destroy)
                    except:
                        pass
                    self.tooltip = None
                
                # Cancel existing timer
                if self.tooltip_timer:
                    try:
                        self.tooltip_timer.cancel()
                    except:
                        pass
                    self.tooltip_timer = None
                
                # Create tooltip using root.after to run in main thread
                def make_tooltip():
                    try:
                        # Create new tooltip window as Toplevel
                        self.tooltip = tk.Toplevel(self.root)
                        self.tooltip.withdraw()
                        self.tooltip.overrideredirect(True)
                        self.tooltip.attributes('-topmost', True)
                        self.tooltip.attributes('-alpha', 0.95)
                        
                        # Create styled label
                        label = tk.Label(
                            self.tooltip,
                            text=text,
                            font=('Segoe UI', 14, 'bold'),
                            background='#2d2d2d',
                            foreground='#00ff00',
                            padx=20,
                            pady=10,
                            relief='solid',
                            borderwidth=2
                        )
                        label.pack()
                        
                        # Position near mouse but offset so not blocking
                        screen_width = self.tooltip.winfo_screenwidth()
                        screen_height = self.tooltip.winfo_screenheight()
                        
                        self.tooltip.update_idletasks()
                        tooltip_width = self.tooltip.winfo_width()
                        tooltip_height = self.tooltip.winfo_height()
                        
                        # Position to the right and below mouse
                        pos_x = min(x + 20, screen_width - tooltip_width - 10)
                        pos_y = min(y + 20, screen_height - tooltip_height - 10)
                        
                        self.tooltip.geometry(f"+{pos_x}+{pos_y}")
                        self.tooltip.deiconify()
                        
                        print(f"AUTO: Tooltip shown at ({pos_x}, {pos_y}): '{text}'")
                        
                        # Auto-dismiss after 2 seconds
                        def dismiss():
                            try:
                                if self.tooltip:
                                    self.root.after(0, self._destroy_tooltip)
                            except Exception as e:
                                print(f"AUTO: Tooltip dismiss error: {e}")
                        
                        self.tooltip_timer = threading.Timer(2.0, dismiss)
                        self.tooltip_timer.daemon = True
                        self.tooltip_timer.start()
                        
                    except Exception as e:
                        print(f"AUTO: Tooltip create error: {e}")
                
                # Schedule in main thread
                self.root.after(0, make_tooltip)
                
            except Exception as e:
                print(f"AUTO: Tooltip error: {e}")
        
        # Run in separate thread
        thread = threading.Thread(target=create_and_show, daemon=True)
        thread.start()
    
    def _destroy_tooltip(self):
        """Helper to properly destroy tooltip"""
        try:
            if self.tooltip:
                self.tooltip.destroy()
                self.tooltip = None
                print("AUTO: Tooltip destroyed")
        except Exception as e:
            print(f"AUTO: Destroy error: {e}")

    def start_monitoring(self):
        """Start key and mouse monitoring"""
        def monitor():
            print("AUTO: Monitor started - Press Ctrl+Shift and hover over numbers")
            while True:
                try:
                    if not self.monitoring:
                        time.sleep(0.1)
                        continue
                    
                    # Check Ctrl+Shift combination
                    ctrl_shift_active = keyboard.is_pressed('ctrl') and keyboard.is_pressed('shift')
                    
                    # State change detection
                    if ctrl_shift_active != self.active:
                        self.active = ctrl_shift_active
                        print(f"AUTO: Ctrl+Shift {'ACTIVATED' if ctrl_shift_active else 'DEACTIVATED'}")
                    
                    # Process while active
                    if ctrl_shift_active:
                        mouse_x, mouse_y = pyautogui.position()
                        
                        # Check if mouse moved significantly
                        if abs(mouse_x - self.last_position[0]) > 20 or abs(mouse_y - self.last_position[1]) > 20:
                            self.last_position = (mouse_x, mouse_y)
                            print(f"AUTO: Processing at ({mouse_x}, {mouse_y})")
                            self.process_location(mouse_x, mouse_y)
                    
                    time.sleep(0.1)
                    
                except Exception as e:
                    print(f"AUTO: Monitor error: {e}")
                    time.sleep(1)

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()

    def process_location(self, x, y):
        """Process OCR at location"""
        try:
            # Precise 70x25 capture region centered on mouse
            region_width = 70
            region_height = 25
            left = max(0, x - region_width // 2)
            top = max(0, y - region_height // 2) 
            right = min(1920, left + region_width)
            bottom = min(1080, top + region_height)
            
            print(f"AUTO: Capturing 70x25 region ({left},{top}) to ({right},{bottom})")
            
            # Capture screenshot
            screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))
            screenshot.save("auto_capture.png")
            
            # Enhance image
            enhanced = screenshot.convert('L')
            enhancer = ImageEnhance.Contrast(enhanced)
            enhanced = enhancer.enhance(3.0)
            enhanced.save("auto_enhanced.png")
            
            # Try OCR with cleaner number extraction
            configs = ['--psm 6', '--psm 7', '--psm 8']
            
            for config in configs:
                try:
                    text = pytesseract.image_to_string(enhanced, config=config).strip()
                    if text:
                        print(f"AUTO: OCR result: '{text}'")
                        
                        # Split by lines and spaces to separate numbers properly
                        # This prevents "57\n0" from becoming "570"
                        text_parts = re.split(r'[\s\n\r]+', text)
                        
                        # Process each part separately and extract numbers
                        valid_numbers = []
                        for part in text_parts:
                            # Remove all non-digit characters except decimal points
                            clean_part = re.sub(r'[^\d\.]', '', part)
                            if clean_part:
                                try:
                                    num = float(clean_part)
                                    if 5 <= num <= 50000:  # Only valid range
                                        valid_numbers.append(num)
                                except ValueError:
                                    continue
                        
                        print(f"AUTO: Text parts: {text_parts}, Valid numbers: {valid_numbers}")
                        
                        # Use the LARGEST number found (main measurement is usually bigger)
                        if valid_numbers:
                            num = max(valid_numbers)
                            imperial = mm_to_imperial(num)
                            conversion = f"{num} mm = {imperial}"
                            
                            # Only show if different from last conversion
                            if conversion != self.last_conversion:
                                self.last_conversion = conversion
                                print(f"AUTO: *** SHOWING: {conversion} ***")
                                
                                # Add to history (only if imperial value is unique)
                                self.add_to_history(conversion, imperial)
                                
                                # Show tooltip
                                self.show_tooltip(conversion, x, y)
                                return
                                
                except Exception as e:
                    continue
            
            print("AUTO: No valid measurements found")
            
        except Exception as e:
            print(f"AUTO: Process error: {e}")

    def manual_test(self):
        """Manual test at cursor position"""
        try:
            x, y = pyautogui.position()
            print(f"AUTO: Manual test at ({x}, {y})")
            self.process_location(x, y)
        except Exception as e:
            print(f"AUTO: Manual test error: {e}")

    def quit_app(self, icon=None, item=None):
        """Quit application - ensures complete termination"""
        print("AUTO: Quitting...")
        self.monitoring = False
        
        # Cancel tooltip timer
        if self.tooltip_timer:
            try:
                self.tooltip_timer.cancel()
            except:
                pass
        
        # Close tooltip
        if self.tooltip:
            try:
                self.tooltip.destroy()
            except:
                pass
        
        # Destroy sticky note if exists
        if self.history_window:
            try:
                self.history_window.destroy()
            except:
                pass
        
        # Destroy root window
        if self.root:
            try:
                self.root.quit()
                self.root.destroy()
            except:
                pass
        
        # Stop system tray icon
        if hasattr(self, 'icon'):
            self.icon.stop()
        
        # Force immediate termination (kills all threads)
        os._exit(0)

    def run(self):
        """Run the application"""
        try:
            # Run system tray in background thread (not Tkinter!)
            def run_tray():
                self.icon.run()
            
            tray_thread = threading.Thread(target=run_tray, daemon=True)
            tray_thread.start()
            
            # Give tray time to initialize
            time.sleep(0.5)
            
            # Auto-show history window on startup
            print("AUTO: Auto-showing history window")
            self.toggle_history_window()
            
            # Run Tkinter in MAIN thread (required!)
            self.root.mainloop()
        except Exception as e:
            print(f"AUTO: Run error: {e}")


if __name__ == "__main__":
    print("=== AUTO-DISMISS CTRL+SHIFT+HOVER CONVERTER ===")
    print("Shows floating tooltip that auto-dismisses in 2 seconds")
    print("Instructions:")
    print("1. Hold Ctrl+Shift and move mouse over numbers")
    print("2. A floating tooltip will appear (auto-dismisses)")
    print("3. Press Ctrl+Alt+H to show/hide conversion history")
    print("4. Press Ctrl+Alt+T for manual test")
    print("5. Look for cyan 'AU' icon in system tray")
    print("6. History window: Clear All = delete all conversions")
    print("=" * 60)
    
    app = AutoDismissConverter()
    app.run()
