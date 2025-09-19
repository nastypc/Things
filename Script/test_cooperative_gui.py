#!/usr/bin/env python3
"""
Test script to verify cooperative GUI behavior
"""

import tkinter as tk
from tkinter import ttk
import sys
import os

# Add the current directory to the path
sys.path.append(os.path.dirname(__file__))

from ehx_search_widget import EHXSearchWidget

class TestApp:
    """Test application to verify cooperative GUI behavior"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Cooperative GUI Test")
        self.root.geometry("1000x700")

        self.setup_ui()
        self.setup_test_elements()

    def setup_ui(self):
        """Setup the main UI"""
        # Main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Title
        title_label = ttk.Label(main_frame, text="Main Application GUI", font=("Arial", 16, "bold"))
        title_label.pack(pady=(0, 10))

        # Control buttons frame
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(control_frame, text="Expand Section 1", command=self.toggle_section_1).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(control_frame, text="Expand Section 2", command=self.toggle_section_2).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(control_frame, text="Toggle Search Focus", command=self.toggle_search_focus).pack(side=tk.LEFT, padx=(0, 5))

        # Status label
        self.status_var = tk.StringVar(value="Ready - Test cooperative GUI behavior")
        status_label = ttk.Label(main_frame, textvariable=self.status_var)
        status_label.pack(pady=(0, 10))

        # Content frame
        content_frame = ttk.Frame(main_frame)
        content_frame.pack(fill=tk.BOTH, expand=True)

        # Left panel - Main content
        left_panel = ttk.LabelFrame(content_frame, text="Main Content", padding=10)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        # Section 1
        self.section1_frame = ttk.LabelFrame(left_panel, text="Section 1 (Expandable)", padding=5)
        self.section1_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(self.section1_frame, text="This is section 1 content.\nClick the button above to expand/collapse.").pack()

        # Section 2
        self.section2_frame = ttk.LabelFrame(left_panel, text="Section 2 (Expandable)", padding=5)
        self.section2_frame.pack(fill=tk.X, pady=(0, 5))
        ttk.Label(self.section2_frame, text="This is section 2 content.\nClick the button above to expand/collapse.").pack()

        # Right panel - Search widget
        right_panel = ttk.LabelFrame(content_frame, text="Search Widget", padding=10)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Create search widget
        self.search_widget = EHXSearchWidget(right_panel)
        self.search_widget.pack(fill=tk.BOTH, expand=True)

        # Enable cooperative mode
        self.search_widget.set_cooperative_mode(True)

    def setup_test_elements(self):
        """Setup test elements to verify cooperative behavior"""
        self.section1_expanded = True
        self.section2_expanded = True

    def toggle_section_1(self):
        """Toggle section 1 visibility"""
        if self.section1_expanded:
            # Hide section 1
            for child in self.section1_frame.winfo_children():
                child.pack_forget()
            self.section1_frame.configure(text="Section 1 (Collapsed)")
            self.section1_expanded = False
            self.status_var.set("Section 1 collapsed - Main GUI still responsive!")
        else:
            # Show section 1
            ttk.Label(self.section1_frame, text="This is section 1 content.\nClick the button above to expand/collapse.").pack()
            self.section1_frame.configure(text="Section 1 (Expanded)")
            self.section1_expanded = True
            self.status_var.set("Section 1 expanded - Main GUI working!")

    def toggle_section_2(self):
        """Toggle section 2 visibility"""
        if self.section2_expanded:
            # Hide section 2
            for child in self.section2_frame.winfo_children():
                child.pack_forget()
            self.section2_frame.configure(text="Section 2 (Collapsed)")
            self.section2_expanded = False
            self.status_var.set("Section 2 collapsed - Main GUI still responsive!")
        else:
            # Show section 2
            ttk.Label(self.section2_frame, text="This is section 2 content.\nClick the button above to expand/collapse.").pack()
            self.section2_frame.configure(text="Section 2 (Expanded)")
            self.section2_expanded = True
            self.status_var.set("Section 2 expanded - Main GUI working!")

    def toggle_search_focus(self):
        """Toggle focus between main GUI and search widget"""
        current_focus = self.root.focus_get()
        search_entry = self.search_widget.search_entry

        if current_focus == search_entry:
            # Search widget has focus, give it back to main GUI
            self.search_widget.release_focus()
            self.status_var.set("Focus released from search widget - Main GUI active")
        else:
            # Give focus to search widget
            self.search_widget.request_focus()
            self.status_var.set("Focus given to search widget - Try typing a search")

    def run(self):
        """Run the test application"""
        self.root.mainloop()

if __name__ == "__main__":
    app = TestApp()
    app.run()
