#!/usr/bin/env python3
"""
WORKING Ctrl+Shift+Hover Converter with direct Windows notifications
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
import ctypes

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


class WorkingConverter:
    def __init__(self):
        print("WORKING: Starting Working Ctrl+Shift+Hover Converter...")
        
        self.monitoring = True
        self.active = False
        self.last_position = (0, 0)
        self.last_conversion = ""
        self.notification_active = False
        
        # Create system tray
        self.create_tray_icon()
        self.start_monitoring()
        
        # Manual test hotkey
        keyboard.add_hotkey('ctrl+alt+t', self.manual_test)

    def create_tray_icon(self):
        """Create system tray icon"""
        try:
            # Yellow icon for working version
            image = Image.new('RGBA', (64, 64), color=(255, 255, 0, 255))
            draw = ImageDraw.Draw(image)
            draw.ellipse([8, 8, 56, 56], fill=(255, 255, 255, 255))
            draw.text((22, 25), "WK", fill=(0, 0, 0, 255))

            menu = Menu(
                MenuItem('Toggle', self.toggle_monitoring, checked=lambda item: self.monitoring),
                MenuItem('Test (Ctrl+Alt+T)', self.manual_test),
                MenuItem('Quit', self.quit_app)
            )

            self.icon = Icon("Working Converter", image, "Working Converter", menu)
            print("WORKING: System tray created")
        except Exception as e:
            print(f"WORKING: Tray error: {e}")

    def toggle_monitoring(self, icon=None, item=None):
        """Toggle monitoring"""
        self.monitoring = not self.monitoring
        print(f"WORKING: Monitoring {'ON' if self.monitoring else 'OFF'}")

    def show_notification(self, text):
        """Show Windows MessageBox in non-blocking way - ALWAYS ON TOP"""
        def show_box():
            try:
                self.notification_active = True
                # Get the foreground window to return focus later
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                
                # Create MessageBox with TOPMOST flag
                # MB_OK (0x0) | MB_TOPMOST (0x40000) | MB_SETFOREGROUND (0x10000) | MB_SYSTEMMODAL (0x1000)
                result = ctypes.windll.user32.MessageBoxW(
                    0,
                    text,
                    "Conversion",
                    0x00000000 | 0x00040000 | 0x00010000 | 0x00001000
                )
                print(f"WORKING: MessageBox shown ON TOP and dismissed: '{text}'")
                
                # Return focus to original window
                if hwnd:
                    ctypes.windll.user32.SetForegroundWindow(hwnd)
                
                self.notification_active = False
            except Exception as e:
                print(f"WORKING: MessageBox error: {e}")
                self.notification_active = False
        
        # Show in thread so it doesn't block
        if not self.notification_active:
            thread = threading.Thread(target=show_box, daemon=True)
            thread.start()

    def start_monitoring(self):
        """Start key and mouse monitoring"""
        def monitor():
            print("WORKING: Monitor started - Press Ctrl+Shift and hover over numbers")
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
                        print(f"WORKING: Ctrl+Shift {'ACTIVATED' if ctrl_shift_active else 'DEACTIVATED'}")
                    
                    # Process while active
                    if ctrl_shift_active:
                        mouse_x, mouse_y = pyautogui.position()
                        
                        # Check if mouse moved significantly
                        if abs(mouse_x - self.last_position[0]) > 20 or abs(mouse_y - self.last_position[1]) > 20:
                            self.last_position = (mouse_x, mouse_y)
                            print(f"WORKING: Processing at ({mouse_x}, {mouse_y})")
                            self.process_location(mouse_x, mouse_y)
                    
                    time.sleep(0.1)
                    
                except Exception as e:
                    print(f"WORKING: Monitor error: {e}")
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
            
            print(f"WORKING: Capturing 70x25 region ({left},{top}) to ({right},{bottom})")
            
            # Capture screenshot
            screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))
            screenshot.save("working_capture.png")
            
            # Enhance image
            enhanced = screenshot.convert('L')
            enhancer = ImageEnhance.Contrast(enhanced)
            enhanced = enhancer.enhance(3.0)
            enhanced.save("working_enhanced.png")
            
            # Try OCR with cleaner number extraction
            configs = ['--psm 6', '--psm 7', '--psm 8']
            
            for config in configs:
                try:
                    text = pytesseract.image_to_string(enhanced, config=config).strip()
                    if text:
                        print(f"WORKING: OCR result: '{text}'")
                        
                        # Remove colons and extract only digits
                        clean_text = re.sub(r'[^\d\s\.]', '', text)
                        numbers = re.findall(r'\b(\d{1,5}\.?\d*)\b', clean_text)
                        
                        print(f"WORKING: Cleaned: '{clean_text}', Numbers: {numbers}")
                        
                        for num_str in numbers:
                            try:
                                num = float(num_str)
                                if 5 <= num <= 50000:  # Reasonable measurement range
                                    imperial = mm_to_imperial(num)
                                    conversion = f"{num} mm = {imperial}"
                                    
                                    # Only show if different from last conversion
                                    if conversion != self.last_conversion:
                                        self.last_conversion = conversion
                                        print(f"WORKING: *** SHOWING: {conversion} ***")
                                        self.show_notification(conversion)
                                        return
                                    
                            except ValueError:
                                continue
                                
                except Exception as e:
                    continue
            
            print("WORKING: No valid measurements found")
            
        except Exception as e:
            print(f"WORKING: Process error: {e}")

    def manual_test(self):
        """Manual test at cursor position"""
        try:
            x, y = pyautogui.position()
            print(f"WORKING: Manual test at ({x}, {y})")
            self.process_location(x, y)
        except Exception as e:
            print(f"WORKING: Manual test error: {e}")

    def quit_app(self, icon=None, item=None):
        """Quit application"""
        print("WORKING: Quitting...")
        self.monitoring = False
        if hasattr(self, 'icon'):
            self.icon.stop()
        os._exit(0)

    def run(self):
        """Run the application"""
        try:
            self.icon.run()
        except Exception as e:
            print(f"WORKING: Run error: {e}")


if __name__ == "__main__":
    print("=== WORKING CTRL+SHIFT+HOVER CONVERTER ===")
    print("Uses MessageBox popups for display")
    print("Instructions:")
    print("1. Hold Ctrl+Shift and hover over '6096:' in test file")
    print("2. A popup will appear with the conversion")
    print("3. Click OK to dismiss")
    print("4. Press Ctrl+Alt+T for manual test")
    print("5. Look for yellow 'WK' icon in system tray")
    print("=" * 45)
    
    app = WorkingConverter()
    app.run()
