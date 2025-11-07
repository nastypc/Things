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
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw, ImageGrab, ImageEnhance
import os
import tkinter as tk
from tkinter import ttk

# Set tesseract path for Windows
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


def mm_to_imperial(mm_value):
    """Convert millimeters to imperial format: 19'-2-7/8" or 7/8" or 20' or 9-1/2" or 8\" """
    inches = mm_value / 25.4
    feet = int(inches // 12)
    remaining_inches = inches % 12
    sixteenths = round(remaining_inches * 16)

    inches_whole = sixteenths // 16
    sixteenths_remainder = sixteenths % 16

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
                MenuItem('Show History (Ctrl+Alt+H)', self.toggle_history_window),
                MenuItem('Test (Ctrl+Alt+T)', self.manual_test),
                MenuItem('Quit', self.quit_app)
            )

            self.icon = Icon("Auto Dismiss", image, "Auto Dismiss Converter", menu)
            print("AUTO: System tray created")
        except Exception as e:
            print(f"AUTO: Tray error: {e}")

    def toggle_monitoring(self, icon=None, item=None):
        """Toggle monitoring"""
        self.monitoring = not self.monitoring
        print(f"AUTO: Monitoring {'ON' if self.monitoring else 'OFF'}")

    def toggle_history_window(self):
        """Toggle the history window visibility"""
        def create_in_thread():
            try:
                if self.history_window is None:
                    self.create_history_window()
                else:
                    # Close if already open
                    try:
                        self.history_window.destroy()
                        self.history_window = None
                        self.history_text_widget = None
                    except:
                        self.history_window = None
                        self.history_text_widget = None
            except Exception as e:
                print(f"AUTO: Toggle error: {e}")
        
        # Run in separate thread
        thread = threading.Thread(target=create_in_thread, daemon=True)
        thread.start()

    def create_history_window(self):
        """Create floating history window"""
        try:
            # Create new Tk window (not Toplevel)
            self.history_window = tk.Tk()
            self.history_window.title("Conversion History")
            self.history_window.geometry("350x400+100+100")
            self.history_window.attributes('-topmost', True)
            self.history_window.protocol("WM_DELETE_WINDOW", self.close_history_window)
            
            # Header
            header = tk.Label(
                self.history_window,
                text="📋 Conversion History",
                font=('Segoe UI', 12, 'bold'),
                bg='#2d2d2d',
                fg='#00ff00',
                pady=10
            )
            header.pack(fill='x')
            
            # Scrollable text area
            frame = tk.Frame(self.history_window)
            frame.pack(fill='both', expand=True, padx=5, pady=5)
            
            scrollbar = tk.Scrollbar(frame)
            scrollbar.pack(side='right', fill='y')
            
            self.history_text_widget = tk.Text(
                frame,
                font=('Consolas', 10),
                bg='#1e1e1e',
                fg='#00ff00',
                yscrollcommand=scrollbar.set,
                wrap='word',
                padx=10,
                pady=10
            )
            self.history_text_widget.pack(side='left', fill='both', expand=True)
            scrollbar.config(command=self.history_text_widget.yview)
            
            # Buttons
            button_frame = tk.Frame(self.history_window)
            button_frame.pack(fill='x', padx=5, pady=5)
            
            clear_btn = tk.Button(
                button_frame,
                text="Clear All",
                command=self.clear_history,
                bg='#d32f2f',
                fg='white',
                font=('Segoe UI', 9, 'bold')
            )
            clear_btn.pack(side='left', padx=5)
            
            copy_btn = tk.Button(
                button_frame,
                text="Copy All",
                command=self.copy_history,
                bg='#1976d2',
                fg='white',
                font=('Segoe UI', 9, 'bold')
            )
            copy_btn.pack(side='left', padx=5)
            
            close_btn = tk.Button(
                button_frame,
                text="Close",
                command=self.close_history_window,
                bg='#616161',
                fg='white',
                font=('Segoe UI', 9, 'bold')
            )
            close_btn.pack(side='right', padx=5)
            
            # Populate with existing history
            self.update_history_display()
            
            print("AUTO: History window opened")
            
            # Start its own event loop
            self.history_window.mainloop()
            
        except Exception as e:
            print(f"AUTO: Error creating history window: {e}")

    def update_history_display(self):
        """Update the history window with current conversions (sorted by mm value, smallest to largest)"""
        if self.history_text_widget:
            try:
                self.history_text_widget.config(state='normal')
                self.history_text_widget.delete('1.0', 'end')
                
                if not self.conversion_history:
                    self.history_text_widget.insert('1.0', "No conversions yet.\n\nHold Ctrl+Shift and hover over numbers to start.")
                else:
                    # Sort by mm value (extract the number before " mm")
                    sorted_conversions = sorted(
                        self.conversion_history,
                        key=lambda x: float(x.split(' mm')[0]) if ' mm' in x else 0
                    )
                    
                    for i, conversion in enumerate(sorted_conversions, 1):
                        self.history_text_widget.insert('end', f"{i}. {conversion}\n")
                
                self.history_text_widget.config(state='disabled')
                # Auto-scroll to bottom
                self.history_text_widget.see('end')
            except Exception as e:
                print(f"AUTO: Error updating history display: {e}")

    def add_to_history(self, conversion, imperial_value):
        """Add conversion to history if imperial result not already present"""
        if imperial_value not in self.imperial_values_seen:
            self.imperial_values_seen.add(imperial_value)
            self.conversion_history.append(conversion)
            print(f"AUTO: Added to history: {conversion}")
            self.update_history_display()
            return True
        else:
            print(f"AUTO: Skipped duplicate imperial: {conversion} (already have {imperial_value})")
            return False

    def clear_history(self):
        """Clear all conversion history"""
        self.conversion_history.clear()
        self.imperial_values_seen.clear()
        self.update_history_display()
        print("AUTO: History cleared")

    def copy_history(self):
        """Copy all conversions to clipboard"""
        try:
            if self.conversion_history:
                clipboard_text = "\n".join(f"{i}. {conv}" for i, conv in enumerate(self.conversion_history, 1))
                self.history_window.clipboard_clear()
                self.history_window.clipboard_append(clipboard_text)
                print(f"AUTO: Copied {len(self.conversion_history)} conversions to clipboard")
            else:
                print("AUTO: No conversions to copy")
        except Exception as e:
            print(f"AUTO: Error copying to clipboard: {e}")

    def close_history_window(self):
        """Close the history window"""
        if self.history_window:
            try:
                self.history_window.destroy()
                self.history_window = None
                self.history_text_widget = None
                print("AUTO: History window closed")
            except:
                pass

    def show_tooltip(self, text, x, y):
        """Show auto-dismissing tooltip overlay"""
        def create_and_show():
            try:
                # Close existing tooltip
                if self.tooltip:
                    try:
                        self.tooltip.destroy()
                    except:
                        pass
                
                # Cancel existing timer
                if self.tooltip_timer:
                    try:
                        self.tooltip_timer.cancel()
                    except:
                        pass
                
                # Create new tooltip window
                self.tooltip = tk.Tk()
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
                            self.tooltip.destroy()
                            self.tooltip = None
                            print("AUTO: Tooltip auto-dismissed")
                    except:
                        pass
                
                self.tooltip_timer = threading.Timer(2.0, dismiss)
                self.tooltip_timer.start()
                
                self.tooltip.mainloop()
                
            except Exception as e:
                print(f"AUTO: Tooltip error: {e}")
        
        # Run in separate thread
        thread = threading.Thread(target=create_and_show, daemon=True)
        thread.start()

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
                        
                        # Remove colons and extract only digits
                        clean_text = re.sub(r'[^\d\s\.]', '', text)
                        numbers = re.findall(r'\b(\d{1,5}\.?\d*)\b', clean_text)
                        
                        print(f"AUTO: Cleaned: '{clean_text}', Numbers: {numbers}")
                        
                        for num_str in numbers:
                            try:
                                num = float(num_str)
                                if 5 <= num <= 50000:  # Reasonable measurement range
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
                                    
                            except ValueError:
                                continue
                                
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
        """Quit application"""
        print("AUTO: Quitting...")
        self.monitoring = False
        
        # Close tooltip
        if self.tooltip:
            try:
                self.tooltip.destroy()
            except:
                pass
        
        # Close history window
        self.close_history_window()
        
        if hasattr(self, 'icon'):
            self.icon.stop()
        os._exit(0)

    def run(self):
        """Run the application"""
        try:
            self.icon.run()
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
