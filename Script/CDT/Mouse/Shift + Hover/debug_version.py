#!/usr/bin/env python3
"""
Debug version of Shift+Hover Tooltip Converter with enhanced logging
"""

import tkinter as tk
from tkinter import ttk
import pyautogui
import pytesseract
import keyboard
import threading
import time
import re
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw, ImageTk, ImageGrab
import os
import sys
import traceback

# Set tesseract path for Windows
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Set tesseract path explicitly for Windows
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'


def mm_to_imperial(mm_value):
    """Convert millimeters to feet-inches-sixteenths format."""
    inches = mm_value / 25.4
    feet = int(inches // 12)
    remaining_inches = inches % 12
    sixteenths = round(remaining_inches * 16)

    inches_whole = sixteenths // 16
    sixteenths_remainder = sixteenths % 16

    if sixteenths_remainder == 0:
        if inches_whole == 0:
            return f"{feet}'" if feet > 0 else "0'"
        else:
            return f"{feet}'{inches_whole}\"" if feet > 0 or inches_whole > 0 else "0'"
    else:
        fractions = {2: "1/8", 4: "1/4", 6: "3/8", 8: "1/2", 10: "5/8", 12: "3/4", 14: "7/8"}
        fraction = fractions.get(sixteenths_remainder, f"{sixteenths_remainder}/16")
        if inches_whole == 0:
            return f"{feet}'{fraction}\"" if feet > 0 else f"0'-{fraction}\""
        else:
            return f"{feet}'{inches_whole} {fraction}\"" if feet > 0 or inches_whole > 0 else f"0'-{fraction}\""


class TooltipWindow:
    def __init__(self):
        self.window = None
        self.label = None

    def show(self, text, x, y):
        """Show tooltip at specified position"""
        try:
            if self.window is None:
                self.window = tk.Toplevel()
                self.window.wm_overrideredirect(True)
                self.window.configure(bg='lightyellow', relief='solid', borderwidth=1)
                
                self.label = tk.Label(self.window, text=text, bg='lightyellow', fg='black',
                                    font=('Arial', 10, 'bold'), padx=5, pady=3)
                self.label.pack()
            else:
                self.label.config(text=text)

            # Position tooltip slightly offset from cursor
            self.window.geometry(f"+{x+15}+{y-30}")
            self.window.lift()
            self.window.attributes('-topmost', True)
            print(f"DEBUG: Tooltip shown: '{text}' at ({x+15}, {y-30})")
            
        except Exception as e:
            print(f"DEBUG: Tooltip show error: {e}")

    def hide(self):
        """Hide tooltip"""
        try:
            if self.window is not None:
                self.window.withdraw()
                print("DEBUG: Tooltip hidden")
        except Exception as e:
            print(f"DEBUG: Tooltip hide error: {e}")


class DebugShiftHoverConverter:
    def __init__(self):
        print("DEBUG: Initializing DebugShiftHoverConverter...")
        
        # Create tkinter root for tooltips
        self.root = tk.Tk()
        self.root.withdraw()  # Hide main window
        
        self.tooltip = TooltipWindow()
        self.monitoring = True  # Start enabled for debugging
        self.shift_pressed = False
        self.last_mouse_pos = (0, 0)
        self.last_text = ""
        
        print("DEBUG: Creating system tray icon...")
        self.create_tray_icon()
        
        print("DEBUG: Starting monitoring...")
        self.start_monitoring()
        
        # Add test hotkey
        print("DEBUG: Adding test hotkey (Ctrl+Alt+T)...")
        keyboard.add_hotkey('ctrl+alt+t', self.test_ocr_at_cursor)

    def create_tray_icon(self):
        """Create system tray icon"""
        try:
            # Create a simple icon
            image = Image.new('RGBA', (64, 64), color=(255, 0, 0, 255))
            draw = ImageDraw.Draw(image)
            draw.ellipse([16, 16, 48, 48], fill=(255, 255, 255, 255))
            draw.text((28, 28), "SH", fill=(0, 0, 0, 255))

            menu = Menu(
                MenuItem('Toggle Monitoring', self.toggle_monitoring, checked=lambda item: self.monitoring),
                MenuItem('Test OCR (Ctrl+Alt+T)', self.test_ocr_at_cursor),
                MenuItem('Quit', self.quit_app)
            )

            self.icon = Icon("Debug Shift+Hover", image, "Debug Shift+Hover Converter", menu)
            print("DEBUG: System tray icon created successfully")
        except Exception as e:
            print(f"DEBUG: Tray icon creation error: {e}")
            traceback.print_exc()

    def toggle_monitoring(self, icon=None, item=None):
        """Toggle monitoring"""
        self.monitoring = not self.monitoring
        print(f"DEBUG: Monitoring toggled to: {'ON' if self.monitoring else 'OFF'}")
        
        if self.monitoring:
            self.start_monitoring()
        else:
            self.tooltip.hide()

    def start_monitoring(self):
        """Start monitoring thread"""
        if hasattr(self, '_monitor_thread') and self._monitor_thread.is_alive():
            print("DEBUG: Monitor thread already running")
            return
            
        def monitor():
            print("DEBUG: Monitor thread started")
            while self.monitoring:
                try:
                    # Check shift key
                    shift_pressed = keyboard.is_pressed('shift')
                    
                    if shift_pressed != self.shift_pressed:
                        self.shift_pressed = shift_pressed
                        print(f"DEBUG: Shift key {'PRESSED' if shift_pressed else 'RELEASED'}")
                        if not shift_pressed:
                            self.tooltip.hide()

                    if shift_pressed:
                        mouse_x, mouse_y = pyautogui.position()
                        
                        # Process every mouse position while shift is held
                        if (mouse_x, mouse_y) != self.last_mouse_pos:
                            self.last_mouse_pos = (mouse_x, mouse_y)
                            print(f"DEBUG: Processing mouse at ({mouse_x}, {mouse_y}) with Shift held")
                            self.process_hover(mouse_x, mouse_y)

                    time.sleep(0.05)  # Faster polling for debugging
                    
                except Exception as e:
                    print(f"DEBUG: Monitor loop error: {e}")
                    traceback.print_exc()
                    time.sleep(1)
            
            print("DEBUG: Monitor thread ended")

        self._monitor_thread = threading.Thread(target=monitor, daemon=True)
        self._monitor_thread.start()

    def process_hover(self, x, y):
        """Process hover with detailed debugging"""
        print(f"DEBUG: === Processing hover at ({x}, {y}) ===")
        
        try:
            # Larger OCR region for better capture
            region_width = 120
            region_height = 40
            
            # Get screen bounds
            screen_width, screen_height = pyautogui.size()
            print(f"DEBUG: Screen size: {screen_width}x{screen_height}")
            
            # Calculate region bounds
            left = max(0, x - region_width // 2)
            top = max(0, y - region_height // 2)
            right = min(screen_width, left + region_width)
            bottom = min(screen_height, top + region_height)
            
            print(f"DEBUG: OCR region: ({left}, {top}, {right}, {bottom}) - size: {right-left}x{bottom-top}")
            
            # Take screenshot
            try:
                screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))
                print("DEBUG: Screenshot captured successfully")
                
                # Save screenshot for debugging
                debug_path = "debug_screenshot.png"
                screenshot.save(debug_path)
                print(f"DEBUG: Screenshot saved to {debug_path}")
                
            except Exception as e:
                print(f"DEBUG: Screenshot error: {e}")
                return

            # Multiple OCR attempts with different configs
            ocr_configs = [
                '--psm 6 -c tessedit_char_whitelist=0123456789.mm ',
                '--psm 7 -c tessedit_char_whitelist=0123456789.mm ',
                '--psm 8 -c tessedit_char_whitelist=0123456789.mm ',
                '--psm 6',
                '--psm 7',
                '--psm 8'
            ]
            
            for i, config in enumerate(ocr_configs):
                try:
                    text = pytesseract.image_to_string(screenshot, config=config).strip()
                    print(f"DEBUG: OCR attempt {i+1} (config: {config}): '{text}'")
                    
                    if text:
                        # Try to find numbers
                        numbers = re.findall(r'\d+\.?\d*', text)
                        print(f"DEBUG: Numbers found: {numbers}")
                        
                        for number_str in numbers:
                            try:
                                number = float(number_str)
                                if 1 <= number <= 10000:  # Reasonable range
                                    imperial = mm_to_imperial(number)
                                    tooltip_text = f"{number} mm = {imperial}"
                                    print(f"DEBUG: *** CONVERSION FOUND: {tooltip_text} ***")
                                    self.tooltip.show(tooltip_text, x, y)
                                    return
                                else:
                                    print(f"DEBUG: Number {number} outside reasonable range")
                            except ValueError:
                                print(f"DEBUG: Could not convert '{number_str}' to float")
                        
                        # If we found text but no valid numbers, try one more time
                        if not numbers and i < 3:  # Only for first 3 configs
                            continue
                        else:
                            break
                            
                except Exception as e:
                    print(f"DEBUG: OCR config {i+1} error: {e}")
                    continue
            
            # No valid conversion found
            print("DEBUG: No valid millimeter values found, hiding tooltip")
            self.tooltip.hide()
            
        except Exception as e:
            print(f"DEBUG: Process hover error: {e}")
            traceback.print_exc()
            self.tooltip.hide()

    def test_ocr_at_cursor(self):
        """Manual test at cursor position"""
        try:
            mouse_x, mouse_y = pyautogui.position()
            print(f"\nDEBUG: === MANUAL TEST AT ({mouse_x}, {mouse_y}) ===")
            self.process_hover(mouse_x, mouse_y)
        except Exception as e:
            print(f"DEBUG: Manual test error: {e}")
            traceback.print_exc()

    def quit_app(self, icon=None, item=None):
        """Quit application safely"""
        print("DEBUG: Quitting application...")
        self.monitoring = False
        if self.tooltip:
            self.tooltip.hide()
        if hasattr(self, 'icon'):
            self.icon.stop()
        self.root.quit()
        os._exit(0)

    def run(self):
        """Run the application"""
        try:
            print("DEBUG: Starting tray icon...")
            threading.Thread(target=self.icon.run, daemon=True).start()
            
            print("DEBUG: Starting tkinter mainloop...")
            self.root.mainloop()
            
        except Exception as e:
            print(f"DEBUG: Run error: {e}")
            traceback.print_exc()


if __name__ == "__main__":
    print("DEBUG: Starting Debug Shift+Hover Converter...")
    print("DEBUG: Hold Shift and hover over numbers to test OCR")
    print("DEBUG: Press Ctrl+Alt+T for manual OCR test at cursor")
    print("DEBUG: Check for debug_screenshot.png file after each test")
    
    app = DebugShiftHoverConverter()
    app.run()