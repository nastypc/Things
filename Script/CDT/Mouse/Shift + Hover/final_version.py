#!/usr/bin/env python3
"""
FINAL Reliable Ctrl+Shift+Hover Converter - Simplified and robust
"""

import tkinter as tk
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


class ReliableTooltip:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.tooltip = None
        self.is_visible = False
        
    def show(self, text, x, y):
        """Show tooltip - always recreate for reliability"""
        try:
            # Always destroy and recreate for maximum reliability
            if self.tooltip:
                try:
                    self.tooltip.destroy()
                except:
                    pass
            
            # Create new tooltip window
            self.tooltip = tk.Toplevel(self.root)
            self.tooltip.wm_overrideredirect(True)
            self.tooltip.configure(bg='black', relief='solid', borderwidth=3)
            
            # Large, highly visible tooltip
            label = tk.Label(self.tooltip, text=text,
                           bg='yellow', fg='black',
                           font=('Arial', 14, 'bold'),
                           padx=15, pady=8,
                           relief='raised', borderwidth=2)
            label.pack()
            
            # Position away from cursor
            self.tooltip.geometry(f"+{x+25}+{y-60}")
            self.tooltip.lift()
            self.tooltip.attributes('-topmost', True)
            self.tooltip.attributes('-alpha', 0.95)
            
            self.is_visible = True
            print(f"FINAL: Tooltip displayed: '{text}' at ({x+25}, {y-60})")
            
        except Exception as e:
            print(f"FINAL: Tooltip show error: {e}")
    
    def hide(self):
        """Hide tooltip"""
        try:
            if self.tooltip:
                self.tooltip.destroy()
                self.tooltip = None
            self.is_visible = False
            print("FINAL: Tooltip hidden")
        except Exception as e:
            print(f"FINAL: Tooltip hide error: {e}")


class FinalShiftHoverConverter:
    def __init__(self):
        print("FINAL: Starting Reliable Ctrl+Shift+Hover Converter...")
        
        self.tooltip = ReliableTooltip()
        self.monitoring = True
        self.active = False  # Track if keys are pressed
        self.last_position = (0, 0)
        
        # Create system tray
        self.create_tray_icon()
        self.start_monitoring()
        
        # Manual test hotkey
        keyboard.add_hotkey('ctrl+alt+t', self.manual_test)

    def create_tray_icon(self):
        """Create system tray icon"""
        try:
            # Blue icon for final version
            image = Image.new('RGBA', (64, 64), color=(0, 0, 255, 255))
            draw = ImageDraw.Draw(image)
            draw.ellipse([8, 8, 56, 56], fill=(255, 255, 255, 255))
            draw.text((20, 25), "CS", fill=(0, 0, 0, 255))

            menu = Menu(
                MenuItem('Toggle', self.toggle_monitoring, checked=lambda item: self.monitoring),
                MenuItem('Test (Ctrl+Alt+T)', self.manual_test),
                MenuItem('Quit', self.quit_app)
            )

            self.icon = Icon("Final Ctrl+Shift Hover", image, "Final Ctrl+Shift Hover", menu)
            print("FINAL: System tray created")
        except Exception as e:
            print(f"FINAL: Tray error: {e}")

    def toggle_monitoring(self, icon=None, item=None):
        """Toggle monitoring"""
        self.monitoring = not self.monitoring
        print(f"FINAL: Monitoring {'ON' if self.monitoring else 'OFF'}")
        if not self.monitoring:
            self.tooltip.hide()

    def start_monitoring(self):
        """Start key and mouse monitoring"""
        def monitor():
            print("FINAL: Monitor started")
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
                        print(f"FINAL: Ctrl+Shift {'ACTIVATED' if ctrl_shift_active else 'DEACTIVATED'}")
                        
                        if not ctrl_shift_active:
                            self.tooltip.hide()
                    
                    # Process while active
                    if ctrl_shift_active:
                        mouse_x, mouse_y = pyautogui.position()
                        
                        # Check if mouse moved significantly
                        if abs(mouse_x - self.last_position[0]) > 10 or abs(mouse_y - self.last_position[1]) > 10:
                            self.last_position = (mouse_x, mouse_y)
                            print(f"FINAL: Processing at ({mouse_x}, {mouse_y})")
                            self.process_location(mouse_x, mouse_y)
                    
                    time.sleep(0.05)  # 20 FPS polling
                    
                except Exception as e:
                    print(f"FINAL: Monitor error: {e}")
                    time.sleep(1)

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()

    def process_location(self, x, y):
        """Process OCR at location"""
        try:
            # Precise small capture region - 70x25 centered on mouse
            region_width = 70
            region_height = 25
            left = max(0, x - region_width // 2)
            top = max(0, y - region_height // 2) 
            right = min(1920, left + region_width)  # Assume 1920 width
            bottom = min(1080, top + region_height)  # Assume 1080 height
            
            print(f"FINAL: Capturing 70x25 region ({left},{top}) to ({right},{bottom}) centered on mouse")
            
            # Capture screenshot
            screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))
            
            # Save for debugging
            screenshot.save("final_capture.png")
            
            # Enhance image
            enhanced = screenshot.convert('L')  # Grayscale
            enhancer = ImageEnhance.Contrast(enhanced)
            enhanced = enhancer.enhance(2.5)
            enhanced.save("final_enhanced.png")
            
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
                        print(f"FINAL: OCR result: '{text}'")
                        
                        # Extract numbers
                        numbers = re.findall(r'\b(\d{1,5}\.?\d*)\b', text)
                        
                        for num_str in numbers:
                            try:
                                num = float(num_str)
                                if 10 <= num <= 5000:  # Reasonable measurement range
                                    imperial = mm_to_imperial(num)
                                    conversion = f"{num} mm = {imperial}"
                                    print(f"FINAL: *** SHOWING: {conversion} ***")
                                    self.tooltip.show(conversion, x, y)
                                    return  # Show first valid conversion
                                    
                            except ValueError:
                                continue
                                
                except Exception as e:
                    continue
            
            print("FINAL: No valid measurements found")
            
        except Exception as e:
            print(f"FINAL: Process error: {e}")

    def manual_test(self):
        """Manual test at cursor position"""
        try:
            x, y = pyautogui.position()
            print(f"FINAL: Manual test at ({x}, {y})")
            self.process_location(x, y)
        except Exception as e:
            print(f"FINAL: Manual test error: {e}")

    def quit_app(self, icon=None, item=None):
        """Quit application"""
        print("FINAL: Quitting...")
        self.monitoring = False
        self.tooltip.hide()
        if hasattr(self, 'icon'):
            self.icon.stop()
        os._exit(0)

    def run(self):
        """Run the application"""
        try:
            threading.Thread(target=self.icon.run, daemon=True).start()
            self.tooltip.root.mainloop()
        except Exception as e:
            print(f"FINAL: Run error: {e}")


if __name__ == "__main__":
    print("=== FINAL RELIABLE CTRL+SHIFT+HOVER CONVERTER ===")
    print("Instructions:")
    print("1. Hold Ctrl+Shift and hover over numbers")
    print("2. Press Ctrl+Alt+T for manual test")
    print("3. Look for blue 'CS' icon in system tray")
    print("4. Check final_capture.png and final_enhanced.png files")
    print("=" * 50)
    
    app = FinalShiftHoverConverter()
    app.run()