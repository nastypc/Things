#!/usr/bin/env python3
"""
BULLETPROOF Ctrl+Shift+Hover Converter - Uses Windows native tooltips
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
import sys
import ctypes
from ctypes import wintypes

# Set tesseract path for Windows
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# Windows API for native tooltips
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

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


class WindowsNativeTooltip:
    """Ultra-reliable tooltip using Windows API"""
    
    def __init__(self):
        self.hwnd = None
        self.current_text = ""
        self.message_thread = None
        
    def show(self, text, x, y):
        """Show tooltip using Windows MessageBox in separate thread"""
        try:
            # Only show if text changed to avoid spam
            if text != self.current_text:
                self.current_text = text
                
                # Close any existing message box first
                self.hide()
                
                # Show MessageBox in separate thread so it doesn't block
                def show_message():
                    try:
                        # Use Windows MessageBox for guaranteed visibility
                        # MB_OK | MB_TOPMOST | MB_SETFOREGROUND
                        result = ctypes.windll.user32.MessageBoxW(
                            0, 
                            text, 
                            "Measurement Conversion", 
                            0x40000 | 0x1000 | 0x0001
                        )
                        print(f"BULLETPROOF: MessageBox closed: '{text}'")
                    except Exception as e:
                        print(f"BULLETPROOF: MessageBox error: {e}")
                
                self.message_thread = threading.Thread(target=show_message, daemon=True)
                self.message_thread.start()
                print(f"BULLETPROOF: MessageBox shown: '{text}'")
                
        except Exception as e:
            print(f"BULLETPROOF: Tooltip error: {e}")
    
    def hide(self):
        """Hide current tooltip by finding and closing MessageBox"""
        try:
            # Find and close any open MessageBox windows
            def enum_windows_proc(hwnd, lParam):
                window_text = ctypes.create_unicode_buffer(256)
                ctypes.windll.user32.GetWindowTextW(hwnd, window_text, 256)
                if "Measurement Conversion" in window_text.value:
                    # Send WM_CLOSE to close the MessageBox
                    ctypes.windll.user32.SendMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
                    print("BULLETPROOF: MessageBox closed via Ctrl+Shift release")
                return True
            
            # Enumerate all windows to find our MessageBox
            enum_windows_proc_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
            enum_proc = enum_windows_proc_type(enum_windows_proc)
            ctypes.windll.user32.EnumWindows(enum_proc, 0)
            
            self.current_text = ""
            
        except Exception as e:
            print(f"BULLETPROOF: Hide error: {e}")


class BulletproofConverter:
    def __init__(self):
        print("BULLETPROOF: Starting Ultra-Reliable Ctrl+Shift+Hover Converter...")
        
        self.tooltip = WindowsNativeTooltip()
        self.monitoring = True
        self.active = False
        self.last_position = (0, 0)
        
        # Create system tray
        self.create_tray_icon()
        self.start_monitoring()
        
        # Manual test hotkey
        keyboard.add_hotkey('ctrl+alt+t', self.manual_test)

    def create_tray_icon(self):
        """Create system tray icon"""
        try:
            # Purple icon for bulletproof version
            image = Image.new('RGBA', (64, 64), color=(128, 0, 128, 255))
            draw = ImageDraw.Draw(image)
            draw.ellipse([8, 8, 56, 56], fill=(255, 255, 255, 255))
            draw.text((18, 25), "BP", fill=(0, 0, 0, 255))

            menu = Menu(
                MenuItem('Toggle', self.toggle_monitoring, checked=lambda item: self.monitoring),
                MenuItem('Test (Ctrl+Alt+T)', self.manual_test),
                MenuItem('Quit', self.quit_app)
            )

            self.icon = Icon("Bulletproof Converter", image, "Bulletproof Ctrl+Shift Hover", menu)
            print("BULLETPROOF: System tray created")
        except Exception as e:
            print(f"BULLETPROOF: Tray error: {e}")

    def toggle_monitoring(self, icon=None, item=None):
        """Toggle monitoring"""
        self.monitoring = not self.monitoring
        print(f"BULLETPROOF: Monitoring {'ON' if self.monitoring else 'OFF'}")

    def start_monitoring(self):
        """Start key and mouse monitoring"""
        def monitor():
            print("BULLETPROOF: Monitor started")
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
                        print(f"BULLETPROOF: Ctrl+Shift {'ACTIVATED' if ctrl_shift_active else 'DEACTIVATED'}")
                        
                        if not ctrl_shift_active:
                            self.tooltip.hide()
                    
                    # Process while active
                    if ctrl_shift_active:
                        mouse_x, mouse_y = pyautogui.position()
                        
                        # Check if mouse moved significantly
                        if abs(mouse_x - self.last_position[0]) > 15 or abs(mouse_y - self.last_position[1]) > 15:
                            self.last_position = (mouse_x, mouse_y)
                            print(f"BULLETPROOF: Processing at ({mouse_x}, {mouse_y})")
                            self.process_location(mouse_x, mouse_y)
                    
                    time.sleep(0.1)  # 10 FPS polling
                    
                except Exception as e:
                    print(f"BULLETPROOF: Monitor error: {e}")
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
            
            print(f"BULLETPROOF: Capturing 70x25 region ({left},{top}) to ({right},{bottom})")
            
            # Capture screenshot
            screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))
            screenshot.save("bulletproof_capture.png")
            
            # Enhance image
            enhanced = screenshot.convert('L')  # Grayscale
            enhancer = ImageEnhance.Contrast(enhanced)
            enhanced = enhancer.enhance(2.5)
            enhanced.save("bulletproof_enhanced.png")
            
            # Try multiple OCR configurations
            configs = [
                '--psm 6',
                '--psm 7', 
                '--psm 8',
                '--psm 13'
            ]
            
            for config in configs:
                try:
                    text = pytesseract.image_to_string(enhanced, config=config).strip()
                    if text:
                        print(f"BULLETPROOF: OCR result: '{text}'")
                        
                        # Extract numbers
                        numbers = re.findall(r'\b(\d{1,5}\.?\d*)\b', text)
                        
                        for num_str in numbers:
                            try:
                                num = float(num_str)
                                if 10 <= num <= 5000:  # Reasonable measurement range
                                    imperial = mm_to_imperial(num)
                                    conversion = f"{num} mm = {imperial}"
                                    print(f"BULLETPROOF: *** SHOWING CONVERSION: {conversion} ***")
                                    self.tooltip.show(conversion, x, y)
                                    return  # Show first valid conversion
                                    
                            except ValueError:
                                continue
                                
                except Exception as e:
                    continue
            
            print("BULLETPROOF: No valid measurements found")
            
        except Exception as e:
            print(f"BULLETPROOF: Process error: {e}")

    def manual_test(self):
        """Manual test at cursor position"""
        try:
            x, y = pyautogui.position()
            print(f"BULLETPROOF: Manual test at ({x}, {y})")
            self.process_location(x, y)
        except Exception as e:
            print(f"BULLETPROOF: Manual test error: {e}")

    def quit_app(self, icon=None, item=None):
        """Quit application"""
        print("BULLETPROOF: Quitting...")
        self.monitoring = False
        if hasattr(self, 'icon'):
            self.icon.stop()
        os._exit(0)

    def run(self):
        """Run the application"""
        try:
            self.icon.run()
        except Exception as e:
            print(f"BULLETPROOF: Run error: {e}")


if __name__ == "__main__":
    print("=== BULLETPROOF CTRL+SHIFT+HOVER CONVERTER ===")
    print("Uses Windows native MessageBox for 100% reliable tooltips")
    print("Instructions:")
    print("1. Hold Ctrl+Shift and hover over numbers")
    print("2. Release Ctrl+Shift to dismiss popup automatically")
    print("3. Press Ctrl+Alt+T for manual test")
    print("4. Look for purple 'BP' icon in system tray")
    print("=" * 55)
    
    app = BulletproofConverter()
    app.run()