#!/usr/bin/env python3
"""
CDT Measurement Converter - System Tray Tool
Converts millimeter measurements to imperial units for CDT files
"""

import tkinter as tk
from tkinter import ttk, messagebox
import pyperclip
import time
import threading
import re
from pystray import Icon, Menu, MenuItem
from PIL import Image, ImageDraw
import os
import sys


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


class CDTConverterApp:
    def __init__(self):
        self.root = None
        self.icon = None
        self.monitoring = False
        self.last_clipboard = ""

    def create_tray_icon(self):
        """Create system tray icon"""
        # Create a simple icon
        image = Image.new('RGB', (64, 64), color='blue')
        draw = ImageDraw.Draw(image)
        draw.rectangle([16, 16, 48, 48], fill='white')
        draw.text((20, 25), "CDT", fill='blue')

        menu = Menu(
            MenuItem('Show Converter', self.show_window),
            MenuItem('Toggle Clipboard Monitor', self.toggle_monitoring, checked=lambda item: self.monitoring),
            MenuItem('Exit', self.quit_app)
        )

        self.icon = Icon("CDT Converter", image, "CDT Measurement Converter", menu)
        self.icon.run_detached()

    def show_window(self):
        """Show the main converter window"""
        if self.root is None:
            self.create_window()
        else:
            self.root.deiconify()
            self.root.lift()

    def create_window(self):
        """Create the main application window"""
        self.root = tk.Tk()
        self.root.title("CDT Measurement Converter")
        self.root.geometry("400x300")
        self.root.resizable(False, False)

        # Input field
        ttk.Label(self.root, text="Millimeter Value:").pack(pady=10)
        self.input_var = tk.StringVar()
        self.input_entry = ttk.Entry(self.root, textvariable=self.input_var, font=('Arial', 12))
        self.input_entry.pack(pady=5, padx=20, fill='x')
        self.input_entry.bind('<KeyRelease>', self.on_input_change)

        # Result display
        ttk.Label(self.root, text="Imperial Equivalent:").pack(pady=10)
        self.result_var = tk.StringVar()
        self.result_label = ttk.Label(self.root, textvariable=self.result_var,
                                    font=('Arial', 14, 'bold'), foreground='blue')
        self.result_label.pack(pady=5)

        # Buttons
        button_frame = ttk.Frame(self.root)
        button_frame.pack(pady=20)

        ttk.Button(button_frame, text="Convert", command=self.convert_input).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Copy to Clipboard", command=self.copy_result).pack(side='left', padx=5)
        ttk.Button(button_frame, text="Minimize to Tray", command=self.hide_window).pack(side='left', padx=5)

        # Status
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self.root, textvariable=self.status_var, foreground='gray').pack(pady=5)

        # Start clipboard monitoring in background
        self.start_clipboard_monitoring()

    def on_input_change(self, event=None):
        """Auto-convert when input changes"""
        self.convert_input()

    def convert_input(self):
        """Convert the input value"""
        try:
            value = float(self.input_var.get().strip())
            result = mm_to_imperial(value)
            self.result_var.set(result)
            self.status_var.set("Converted successfully")
        except ValueError:
            self.result_var.set("")
            self.status_var.set("Enter a valid number")

    def copy_result(self):
        """Copy result to clipboard"""
        result = self.result_var.get()
        if result:
            pyperclip.copy(result)
            self.status_var.set("Copied to clipboard!")

    def hide_window(self):
        """Hide window to system tray"""
        if self.root:
            self.root.withdraw()

    def toggle_monitoring(self):
        """Toggle clipboard monitoring"""
        self.monitoring = not self.monitoring
        if self.monitoring:
            self.status_var.set("Clipboard monitoring ON")
        else:
            self.status_var.set("Clipboard monitoring OFF")

    def start_clipboard_monitoring(self):
        """Monitor clipboard for numbers to auto-convert"""
        def monitor():
            while True:
                try:
                    current = pyperclip.paste()
                    if current != self.last_clipboard and self.monitoring:
                        # Check if clipboard contains a number
                        match = re.search(r'(\d+\.?\d*)', current.strip())
                        if match:
                            try:
                                num = float(match.group(1))
                                imperial = mm_to_imperial(num)
                                # Could show notification here
                                print(f"Clipboard number detected: {num}mm = {imperial}")
                            except ValueError:
                                pass
                    self.last_clipboard = current
                except:
                    pass
                time.sleep(0.5)

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()

    def quit_app(self):
        """Quit the application"""
        if self.icon:
            self.icon.stop()
        if self.root:
            self.root.quit()
        sys.exit(0)

    def run(self):
        """Run the application"""
        self.create_tray_icon()

        # Create window initially hidden
        self.create_window()
        self.hide_window()

        # Start the GUI main loop
        if self.root:
            self.root.mainloop()


def main():
    app = CDTConverterApp()
    app.run()


if __name__ == "__main__":
    main()