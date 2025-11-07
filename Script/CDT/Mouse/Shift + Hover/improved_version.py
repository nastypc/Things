#!/usr/bin/env python3
"""
IMPROVED Shift+Hover Tooltip Converter - Better text file handling
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
from PIL import Image, ImageDraw, ImageTk, ImageGrab, ImageEnhance, ImageFilter
import os
import sys
import traceback

# Set tesseract path for Windows
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


class ImprovedTooltipWindow:
    def __init__(self):
        self.window = None
        self.label = None
        self.last_text = ""
        self.hide_timer = None

    def show(self, text, x, y):
        """Show tooltip with improved visibility"""
        try:
            if self.window is None:
                self.window = tk.Toplevel()
                self.window.wm_overrideredirect(True)
                self.window.configure(bg='black', relief='solid', borderwidth=2)
                
                # Larger, more visible tooltip
                self.label = tk.Label(self.window, text=text, 
                                    bg='yellow', fg='black',
                                    font=('Arial', 12, 'bold'), 
                                    padx=10, pady=5,
                                    relief='raised', borderwidth=2)
                self.label.pack()
            else:
                self.label.config(text=text)

            # Position tooltip to avoid cursor
            self.window.geometry(f"+{x+20}+{y-50}")
            self.window.lift()
            self.window.attributes('-topmost', True)
            self.window.attributes('-alpha', 0.95)  # Slight transparency
            
            self.last_text = text
            print(f"IMPROVED: Tooltip shown: '{text}' at ({x+20}, {y-50})")
            
            # Cancel any existing hide timer
            if self.hide_timer:
                self.hide_timer.cancel()
            
        except Exception as e:
            print(f"IMPROVED: Tooltip show error: {e}")

    def hide_delayed(self, delay=1.0):
        """Hide tooltip after delay"""
        if self.hide_timer:
            self.hide_timer.cancel()
        
        self.hide_timer = threading.Timer(delay, self.hide)
        self.hide_timer.start()

    def hide(self):
        """Hide tooltip immediately"""
        try:
            if self.window is not None:
                self.window.withdraw()
                print("IMPROVED: Tooltip hidden")
        except Exception as e:
            print(f"IMPROVED: Tooltip hide error: {e}")


class ImprovedShiftHoverConverter:
    def __init__(self):
        print("IMPROVED: Initializing ImprovedShiftHoverConverter...")
        
        # Create tkinter root for tooltips
        self.root = tk.Tk()
        self.root.withdraw()  # Hide main window
        
        self.tooltip = ImprovedTooltipWindow()
        self.monitoring = True  # Start enabled
        self.shift_pressed = False
        self.last_mouse_pos = (0, 0)
        self.last_conversion = ""
        self.consecutive_failures = 0
        
        print("IMPROVED: Creating system tray icon...")
        self.create_tray_icon()
        
        print("IMPROVED: Starting monitoring...")
        self.start_monitoring()
        
        # Add test hotkey
        print("IMPROVED: Adding test hotkey (Ctrl+Alt+T)...")
        keyboard.add_hotkey('ctrl+alt+t', self.test_ocr_at_cursor)

    def create_tray_icon(self):
        """Create system tray icon"""
        try:
            # Create a green icon for improved version
            image = Image.new('RGBA', (64, 64), color=(0, 255, 0, 255))
            draw = ImageDraw.Draw(image)
            draw.ellipse([8, 8, 56, 56], fill=(255, 255, 255, 255))
            draw.text((20, 25), "SH", fill=(0, 0, 0, 255), font_size=16)

            menu = Menu(
                MenuItem('Toggle Monitoring', self.toggle_monitoring, checked=lambda item: self.monitoring),
                MenuItem('Test OCR (Ctrl+Alt+T)', self.test_ocr_at_cursor),
                MenuItem('Quit', self.quit_app)
            )

            self.icon = Icon("Improved Ctrl+Shift+Hover", image, "Improved Ctrl+Shift+Hover Converter", menu)
            print("IMPROVED: System tray icon created successfully")
        except Exception as e:
            print(f"IMPROVED: Tray icon creation error: {e}")
            traceback.print_exc()

    def toggle_monitoring(self, icon=None, item=None):
        """Toggle monitoring"""
        self.monitoring = not self.monitoring
        print(f"IMPROVED: Monitoring toggled to: {'ON' if self.monitoring else 'OFF'}")
        
        if self.monitoring:
            self.start_monitoring()
        else:
            self.tooltip.hide()

    def start_monitoring(self):
        """Start monitoring thread"""
        if hasattr(self, '_monitor_thread') and self._monitor_thread.is_alive():
            print("IMPROVED: Monitor thread already running")
            return
            
        def monitor():
            print("IMPROVED: Monitor thread started")
            while self.monitoring:
                try:
                    # Check ctrl+shift combination (safe, won't type characters)
                    ctrl_shift_pressed = keyboard.is_pressed('ctrl') and keyboard.is_pressed('shift')
                    
                    if ctrl_shift_pressed != self.shift_pressed:
                        self.shift_pressed = ctrl_shift_pressed
                        print(f"IMPROVED: Ctrl+Shift {'PRESSED' if ctrl_shift_pressed else 'RELEASED'}")
                        if not ctrl_shift_pressed:
                            self.tooltip.hide_delayed(0.5)  # Delayed hide when ctrl+shift released

                    if ctrl_shift_pressed:
                        mouse_x, mouse_y = pyautogui.position()
                        
                        # Process every mouse position while shift is held
                        if (mouse_x, mouse_y) != self.last_mouse_pos:
                            self.last_mouse_pos = (mouse_x, mouse_y)
                            print(f"IMPROVED: Processing mouse at ({mouse_x}, {mouse_y}) with Ctrl+Shift held")
                            self.process_hover(mouse_x, mouse_y)

                    time.sleep(0.08)  # Faster polling for better responsiveness
                    
                except Exception as e:
                    print(f"IMPROVED: Monitor loop error: {e}")
                    traceback.print_exc()
                    time.sleep(1)
            
            print("IMPROVED: Monitor thread ended")

        self._monitor_thread = threading.Thread(target=monitor, daemon=True)
        self._monitor_thread.start()

    def enhance_image_for_ocr(self, image):
        """Enhance image for better OCR in text editors"""
        try:
            # Convert to grayscale for better text recognition
            if image.mode != 'L':
                image = image.convert('L')
            
            # Increase contrast
            enhancer = ImageEnhance.Contrast(image)
            image = enhancer.enhance(2.0)
            
            # Increase sharpness
            enhancer = ImageEnhance.Sharpness(image)
            image = enhancer.enhance(2.0)
            
            # Scale up image for better OCR
            width, height = image.size
            image = image.resize((width * 3, height * 3), Image.Resampling.LANCZOS)
            
            return image
        except Exception as e:
            print(f"IMPROVED: Image enhancement error: {e}")
            return image

    def process_hover(self, x, y):
        """Enhanced hover processing for text files"""
        print(f"IMPROVED: === Processing hover at ({x}, {y}) ===")
        
        try:
            # Larger OCR region for text files
            region_width = 200
            region_height = 60
            
            # Get screen bounds
            screen_width, screen_height = pyautogui.size()
            print(f"IMPROVED: Screen size: {screen_width}x{screen_height}")
            
            # Calculate region bounds
            left = max(0, x - region_width // 2)
            top = max(0, y - region_height // 2)
            right = min(screen_width, left + region_width)
            bottom = min(screen_height, top + region_height)
            
            print(f"IMPROVED: OCR region: ({left}, {top}, {right}, {bottom}) - size: {right-left}x{bottom-top}")
            
            # Take screenshot
            try:
                screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))
                print("IMPROVED: Screenshot captured successfully")
                
                # Enhance for OCR
                enhanced_screenshot = self.enhance_image_for_ocr(screenshot)
                
                # Save both for debugging
                screenshot.save("improved_original.png")
                enhanced_screenshot.save("improved_enhanced.png")
                print("IMPROVED: Screenshots saved")
                
            except Exception as e:
                print(f"IMPROVED: Screenshot error: {e}")
                return

            # Comprehensive OCR attempts optimized for text files
            ocr_configs = [
                # Optimized for text files with numbers
                '--psm 6 --oem 3 -c tessedit_char_whitelist=0123456789.mm ',
                '--psm 7 --oem 3 -c tessedit_char_whitelist=0123456789.mm ',
                '--psm 8 --oem 3 -c tessedit_char_whitelist=0123456789. ',
                '--psm 13 --oem 3 -c tessedit_char_whitelist=0123456789.mm ',  # Raw line
                # Fallback configs
                '--psm 6 --oem 3',
                '--psm 7 --oem 3',
                '--psm 8 --oem 3',
                '--psm 13 --oem 3',
            ]
            
            best_conversion = None
            
            for i, config in enumerate(ocr_configs):
                try:
                    # Try both original and enhanced images
                    for img_type, img in [("enhanced", enhanced_screenshot), ("original", screenshot)]:
                        text = pytesseract.image_to_string(img, config=config).strip()
                        print(f"IMPROVED: OCR attempt {i+1}-{img_type} (config: {config}): '{text}'")
                        
                        if text:
                            # Multiple number extraction patterns
                            patterns = [
                                r'(\d+\.?\d*)\s*mm',  # With mm
                                r'\b(\d{2,4}\.?\d*)\b',  # 2-4 digit numbers (likely measurements)
                                r'\b(\d+\.\d+)\b',  # Decimal numbers
                                r'\b(\d{1,3})\b',  # 1-3 digit whole numbers
                            ]
                            
                            for pattern in patterns:
                                numbers = re.findall(pattern, text, re.IGNORECASE)
                                print(f"IMPROVED: Pattern '{pattern}' found: {numbers}")
                                
                                for number_str in numbers:
                                    try:
                                        number = float(number_str)
                                        if 5 <= number <= 10000:  # Reasonable measurement range
                                            imperial = mm_to_imperial(number)
                                            conversion = f"{number} mm = {imperial}"
                                            print(f"IMPROVED: *** CONVERSION FOUND: {conversion} ***")
                                            
                                            # Show immediately and remember
                                            self.tooltip.show(conversion, x, y)
                                            self.last_conversion = conversion
                                            self.consecutive_failures = 0
                                            return
                                        else:
                                            print(f"IMPROVED: Number {number} outside reasonable range")
                                    except ValueError:
                                        print(f"IMPROVED: Could not convert '{number_str}' to float")
                        
                        # Break early if we found something useful
                        if text and len(text) > 2:
                            break
                            
                except Exception as e:
                    print(f"IMPROVED: OCR config {i+1} error: {e}")
                    continue
            
            # No conversion found
            self.consecutive_failures += 1
            print(f"IMPROVED: No valid conversions found (failures: {self.consecutive_failures})")
            
            # Only hide tooltip after several failures to reduce flicker
            if self.consecutive_failures > 3:
                self.tooltip.hide_delayed(0.3)
            
        except Exception as e:
            print(f"IMPROVED: Process hover error: {e}")
            traceback.print_exc()

    def test_ocr_at_cursor(self):
        """Manual test at cursor position"""
        try:
            mouse_x, mouse_y = pyautogui.position()
            print(f"\nIMPROVED: === MANUAL TEST AT ({mouse_x}, {mouse_y}) ===")
            self.process_hover(mouse_x, mouse_y)
        except Exception as e:
            print(f"IMPROVED: Manual test error: {e}")
            traceback.print_exc()

    def quit_app(self, icon=None, item=None):
        """Quit application safely"""
        print("IMPROVED: Quitting application...")
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
            print("IMPROVED: Starting tray icon...")
            threading.Thread(target=self.icon.run, daemon=True).start()
            
            print("IMPROVED: Starting tkinter mainloop...")
            self.root.mainloop()
            
        except Exception as e:
            print(f"IMPROVED: Run error: {e}")
            traceback.print_exc()


if __name__ == "__main__":
    print("IMPROVED: Starting Improved Ctrl+Shift+Hover Converter...")
    print("IMPROVED: Better text file support, enhanced OCR, persistent tooltips")
    print("IMPROVED: Hold Ctrl+Shift and hover over numbers to test OCR")
    print("IMPROVED: Press Ctrl+Alt+T for manual OCR test at cursor")
    print("IMPROVED: Look for improved_original.png and improved_enhanced.png files")
    
    app = ImprovedShiftHoverConverter()
    app.run()