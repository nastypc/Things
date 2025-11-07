#!/usr/bin/env python3
"""
Shift+Hover Tooltip Converter
Displays imperial conversions when holding Shift and hovering over millimeter values
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
from PIL import Image, ImageDraw, ImageTk
import os
import sys

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
        if self.window is None:
            self.window = tk.Toplevel()
            self.window.attributes("-topmost", True)
            self.window.attributes("-alpha", 0.9)
            self.window.overrideredirect(True)  # Remove window decorations

            self.label = ttk.Label(self.window, text=text, background="yellow",
                                 foreground="black", font=("Arial", 10, "bold"),
                                 padding=5)
            self.label.pack()

        else:
            self.label.config(text=text)

        # Position near mouse cursor
        self.window.geometry(f"+{x+15}+{y+15}")
        self.window.deiconify()

    def hide(self):
        """Hide tooltip"""
        if self.window:
            self.window.withdraw()


class ShiftHoverConverter:
    def __init__(self):
        self.tooltip = TooltipWindow()
        self.monitoring = True  # Start with monitoring enabled
        self.shift_pressed = False
        self.icon = None
        self.last_mouse_pos = (0, 0)
        self.last_text = ""

        # OCR configuration
        pytesseract.pytesseract.tesseract_cmd = self.find_tesseract()

    def find_tesseract(self):
        """Find Tesseract OCR executable"""
        # Common installation paths
        paths = [
            r'C:\Program Files\Tesseract-OCR\tesseract.exe',
            r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
            r'C:\Users\edward\AppData\Local\Programs\Tesseract-OCR\tesseract.exe'
        ]

        for path in paths:
            if os.path.exists(path):
                return path

        # Try to find in PATH
        try:
            import subprocess
            result = subprocess.run(['where', 'tesseract'], capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass

        return r'C:\Program Files\Tesseract-OCR\tesseract.exe'  # Default fallback

    def create_tray_icon(self):
        """Create system tray icon"""
        image = Image.new('RGB', (64, 64), color='green')
        draw = ImageDraw.Draw(image)
        draw.rectangle([16, 16, 48, 48], fill='white')
        draw.text((20, 25), "SHIFT", fill='green')

        menu = Menu(
            MenuItem('Toggle Shift+Hover', self.toggle_monitoring, checked=lambda item: self.monitoring),
            MenuItem('Test OCR at Cursor (Ctrl+Alt+T)', self.show_test_instructions),
            MenuItem('Exit', self.quit_app)
        )

        self.icon = Icon("Shift+Hover Converter", image, "Shift+Hover Tooltip Converter", menu)
        self.icon.run_detached()

        # Register hotkey for testing (changed to avoid VS Code conflicts)
        keyboard.add_hotkey('ctrl+alt+t', self.test_ocr_at_cursor)

    def show_test_instructions(self):
        """Show instructions for testing OCR"""
        instructions = "To test OCR:\n1. Position mouse over a number in CDT file\n2. Press Ctrl+Alt+T\n3. Check console output"
        print(instructions)
        self.tooltip.show(instructions, 100, 100)
        self.tooltip.window.after(5000, self.tooltip.hide)

    def toggle_monitoring(self):
        """Toggle Shift+hover monitoring"""
        self.monitoring = not self.monitoring
        if self.monitoring:
            print("Shift+Hover monitoring enabled")
            self.start_monitoring()
        else:
            print("Shift+Hover monitoring disabled")
            self.tooltip.hide()

    def start_monitoring(self):
        """Start monitoring Shift key and mouse"""
        def monitor():
            print("Starting Shift+Hover monitoring...")  # Debug output
            while self.monitoring:
                try:
                    # Check if Shift is pressed
                    shift_pressed = keyboard.is_pressed('shift')

                    if shift_pressed != self.shift_pressed:
                        self.shift_pressed = shift_pressed
                        print(f"Shift {'pressed' if shift_pressed else 'released'}")  # Debug output
                        if not shift_pressed:
                            self.tooltip.hide()

                    if shift_pressed:
                        mouse_x, mouse_y = pyautogui.position()

                        # Only process if mouse moved significantly
                        if abs(mouse_x - self.last_mouse_pos[0]) > 5 or abs(mouse_y - self.last_mouse_pos[1]) > 5:
                            self.last_mouse_pos = (mouse_x, mouse_y)
                            print(f"Mouse moved to ({mouse_x}, {mouse_y}), processing hover...")  # Debug output
                            self.process_hover(mouse_x, mouse_y)

                    time.sleep(0.1)  # Small delay to prevent excessive processing

                except Exception as e:
                    print(f"Monitoring error: {e}")
                    time.sleep(0.5)

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()

    def process_hover(self, x, y):
        """Process hover at given coordinates"""
        print(f"Processing hover at ({x}, {y})")  # Debug output
        try:
            # Check if on secondary monitor (OCR limitation)
            try:
                import screeninfo
                monitors = screeninfo.get_monitors()
                for monitor in monitors:
                    if (monitor.x <= x < monitor.x + monitor.width and
                        monitor.y <= y < monitor.y + monitor.height and
                        monitor.x > 0):  # Secondary monitor
                        print("Warning: Mouse is on secondary monitor. OCR may not work properly. Move to primary monitor.")
                        return  # Skip OCR on secondary monitors
            except ImportError:
                pass

            # Get screen size for region bounds
            screen_width, screen_height = pyautogui.size()

            # Use focused region centered on cursor for better number capture
            region_width = 60  # Good balance for various number sizes
            region_height = 25  # Smaller height
            # Center the region on the cursor position
            left = max(0, x - region_width // 2)
            top = max(0, y - region_height // 2)
            right = min(screen_width, left + region_width)
            bottom = min(screen_height, top + region_height)

            region = (left, top, right - left, bottom - top)

            # Try PIL ImageGrab for better multi-monitor support
            try:
                from PIL import ImageGrab
                screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))
            except ImportError:
                # Fallback to pyautogui if PIL ImageGrab not available
                screenshot = pyautogui.screenshot(region=region)

            # OCR the image with different PSM modes
            text = pytesseract.image_to_string(screenshot, config='--psm 6').strip()  # Try PSM 6 for uniform block of text
            if not text:
                text = pytesseract.image_to_string(screenshot, config='--psm 7').strip()  # Fallback to PSM 7

            print(f"OCR detected: '{text}' at position ({x}, {y})")  # Debug output

            if text != self.last_text:
                self.last_text = text

                # Look for millimeter values (with or without mm suffix)
                match = re.search(r'(\d+\.?\d*)\s*mm', text, re.IGNORECASE)
                if not match:
                    # Try without mm suffix for CDT files - look for numbers that look like measurements
                    match = re.search(r'\b(\d+\.?\d*)\b', text)

                if match:
                    try:
                        mm_value = float(match.group(1))
                        # Only convert values that look like measurements (reasonable mm range)
                        if 10 <= mm_value <= 10000:  # 10mm to 10m range
                            imperial = mm_to_imperial(mm_value)
                            tooltip_text = f"{mm_value} mm = {imperial}"
                            print(f"Found conversion: {tooltip_text}")  # Debug output
                            self.tooltip.show(tooltip_text, x, y)
                            return
                    except ValueError:
                        pass

            # Hide tooltip if no valid mm value found
            self.tooltip.hide()

        except Exception as e:
            print(f"OCR error: {e}")
            self.tooltip.hide()

    def test_ocr_at_cursor(self):
        """Test OCR at current cursor position"""
        try:
            # Get current mouse position (support multi-monitor)
            mouse_x, mouse_y = pyautogui.position()
            x, y = mouse_x, mouse_y  # Don't clamp for multi-monitor support
            
            # Check monitor setup and adjust coordinates if needed
            try:
                import screeninfo
                monitors = screeninfo.get_monitors()
                print(f"Detected {len(monitors)} monitors:")
                for i, monitor in enumerate(monitors):
                    print(f"  Monitor {i}: {monitor.name} at ({monitor.x}, {monitor.y}) size {monitor.width}x{monitor.height}")

                if len(monitors) > 1:
                    # Find which monitor the cursor is on
                    cursor_monitor = None
                    for monitor in monitors:
                        if (monitor.x <= x < monitor.x + monitor.width and
                            monitor.y <= y < monitor.y + monitor.height):
                            cursor_monitor = monitor
                            break

                    if cursor_monitor and cursor_monitor.x > 0:  # Secondary monitor
                        print(f"⚠️  Secondary monitor detected - OCR currently only works on primary monitor")
                        print(f"   Please move your CDT file to the primary monitor for conversions")
                        return
                    else:
                        print(f"Could not determine monitor for cursor at ({x}, {y})")
            except ImportError:
                print("screeninfo not available for monitor detection")

            # Get screen size for region bounds
            screen_width, screen_height = pyautogui.size()

            # Use focused region centered on cursor for better number capture
            region_width = 60  # Good balance for various number sizes
            region_height = 25  # Smaller height
            # Center the region on the cursor position
            left = max(0, x - region_width // 2)
            top = max(0, y - region_height // 2)
            right = min(screen_width, left + region_width)
            bottom = min(screen_height, top + region_height)

            print(f"Debug: mouse=({mouse_x},{mouse_y}), screen=({screen_width},{screen_height})")
            print(f"Debug: region: left={left}, top={top}, right={right}, bottom={bottom}")
            print(f"Debug: size: width={right - left}, height={bottom - top}")

            region = (left, top, right - left, bottom - top)

            # Try PIL ImageGrab for better multi-monitor support
            try:
                from PIL import ImageGrab
                screenshot = ImageGrab.grab(bbox=(left, top, right, bottom))
            except ImportError:
                # Fallback to pyautogui if PIL ImageGrab not available
                screenshot = pyautogui.screenshot(region=region)

            # Save screenshot for debugging
            debug_image_path = r"C:\Users\edward\Downloads\debug_ocr.png"
            screenshot.save(debug_image_path)
            print(f"Debug screenshot saved to: {debug_image_path}")

            # OCR the image with different PSM modes
            text_psm6 = pytesseract.image_to_string(screenshot, config='--psm 6').strip()
            text_psm7 = pytesseract.image_to_string(screenshot, config='--psm 7').strip()
            text_psm8 = pytesseract.image_to_string(screenshot, config='--psm 8').strip()
            text_psm13 = pytesseract.image_to_string(screenshot, config='--psm 13').strip()  # Raw line

            print(f"OCR Test at cursor ({x}, {y}):")
            print(f"  Region: {region}")
            print(f"  PSM 6: '{text_psm6}'")
            print(f"  PSM 7: '{text_psm7}'")
            print(f"  PSM 8: '{text_psm8}'")
            print(f"  PSM 13: '{text_psm13}'")

            # Use the best result
            text = text_psm8 or text_psm13 or text_psm6 or text_psm7

            # Test conversion with detailed regex matching
            print("Testing regex patterns:")

            # Pattern 1: with mm suffix
            match_mm = re.search(r'(\d+\.?\d*)\s*mm', text, re.IGNORECASE)
            print(f"  Pattern 'number mm': {match_mm.group(1) if match_mm else 'No match'}")

            # Pattern 2: standalone numbers
            matches_standalone = re.findall(r'\b(\d+\.?\d*)\b', text)
            print(f"  Pattern 'standalone numbers': {matches_standalone}")

            # Try to convert any found numbers
            converted = False
            for match in matches_standalone:
                try:
                    mm_value = float(match)
                    if 10 <= mm_value <= 10000:
                        imperial = mm_to_imperial(mm_value)
                        print(f"  Converting {mm_value} -> {imperial}")
                        tooltip_text = f"TEST: {mm_value} mm = {imperial}"
                        self.tooltip.show(tooltip_text, x, y)
                        self.tooltip.window.after(5000, self.tooltip.hide)  # Show for 5 seconds
                        converted = True
                        break
                except ValueError:
                    continue

            if not converted:
                print("  No convertible numbers found")
                # Show what we detected anyway
                if text:
                    self.tooltip.show(f"OCR: '{text}'", x, y)
                    self.tooltip.window.after(3000, self.tooltip.hide)

        except Exception as e:
            print(f"OCR test at cursor failed: {e}")
            import traceback
            traceback.print_exc()

    def quit_app(self):
        """Quit the application"""
        self.monitoring = False
        self.tooltip.hide()
        if self.icon:
            self.icon.stop()
        sys.exit(0)

    def run(self):
        """Run the application"""
        print("Shift+Hover Tooltip Converter")
        print("Right-click tray icon and select 'Toggle Shift+Hover' to enable monitoring")
        print("Hold Shift and hover over mm values to see conversions")
        print(f"Monitoring is currently: {'ENABLED' if self.monitoring else 'DISABLED'}")

        self.create_tray_icon()

        # Keep the main thread alive
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("Received keyboard interrupt, shutting down...")
            self.quit_app()
        except SystemExit:
            print("Received system exit, shutting down...")
            self.quit_app()
        except Exception as e:
            print(f"Unexpected error in main loop: {e}")
            self.quit_app()


def main():
    # Check if another instance is already running using a lock file
    lock_file = os.path.join(os.path.dirname(__file__), 'shift_hover_converter.lock')
    
    if os.path.exists(lock_file):
        try:
            with open(lock_file, 'r') as f:
                pid = int(f.read().strip())
            # Check if process is still running (optional)
            try:
                import psutil  # type: ignore
                if psutil.pid_exists(pid):
                    print("Another instance of Shift+Hover Converter is already running.")
                    print("Please close the existing instance first.")
                    sys.exit(1)
                else:
                    # Stale lock file, remove it
                    print("Removing stale lock file...")
                    os.remove(lock_file)
            except ImportError:
                # If psutil not available, check lock file age
                try:
                    lock_age = time.time() - os.path.getmtime(lock_file)
                    if lock_age > 300:  # If lock file is older than 5 minutes, assume stale
                        print("Removing old lock file (older than 5 minutes)...")
                        os.remove(lock_file)
                    else:
                        print("Lock file exists and is recent. If you're sure no other instance is running,")
                        print(f"please delete the file: {lock_file}")
                        print("Or wait 5 minutes for it to be considered stale.")
                        sys.exit(1)
                except OSError:
                    # If we can't get file stats, try to remove it
                    print("Removing problematic lock file...")
                    try:
                        os.remove(lock_file)
                    except:
                        print(f"Could not remove lock file: {lock_file}")
                        print("Please delete it manually and try again.")
                        sys.exit(1)
        except (ValueError, OSError):
            # If we can't read the file, remove it
            print("Removing invalid lock file...")
            try:
                os.remove(lock_file)
            except:
                pass
    
    # Create lock file with current PID
    try:
        with open(lock_file, 'w') as f:
            f.write(str(os.getpid()))
    except:
        print("Warning: Could not create lock file")
    
    try:
        app = ShiftHoverConverter()
        app.run()
    finally:
        # Clean up lock file
        try:
            if os.path.exists(lock_file):
                os.remove(lock_file)
        except:
            pass


if __name__ == "__main__":
    main()