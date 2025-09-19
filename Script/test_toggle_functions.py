#!/usr/bin/env python3
"""
Simple test script to verify toggle functions work correctly
"""

import tkinter as tk

def toggle_technical_specs(button, content_frame):
    """Test toggle function for technical specifications"""
    try:
        if content_frame.winfo_ismapped():
            # Currently visible, hide it
            content_frame.pack_forget()
            button.config(text='▶')
            print("Technical Specifications: Hidden")
        else:
            # Currently hidden, show it
            content_frame.pack(fill='x', padx=8, pady=2)
            button.config(text='▼')
            print("Technical Specifications: Shown")
    except Exception as e:
        print(f"Error in toggle_technical_specs: {e}")

def toggle_subassembly_details(button, content_frame):
    """Test toggle function for subassembly details"""
    try:
        if content_frame.winfo_ismapped():
            # Currently visible, hide it
            content_frame.pack_forget()
            button.config(text='▶')
            print("SubAssembly Details: Hidden")
        else:
            # Currently hidden, show it
            content_frame.pack(fill='x', padx=8, pady=2)
            button.config(text='▼')
            print("SubAssembly Details: Shown")
    except Exception as e:
        print(f"Error in toggle_subassembly_details: {e}")

def toggle_beam_pocket_details(button, content_frame):
    """Test toggle function for beam pocket details"""
    try:
        if content_frame.winfo_ismapped():
            # Currently visible, hide it
            content_frame.pack_forget()
            button.config(text='▶')
            print("Beam Pocket Details: Hidden")
        else:
            # Currently hidden, show it
            content_frame.pack(fill='x', padx=8, pady=2)
            button.config(text='▼')
            print("Beam Pocket Details: Shown")
    except Exception as e:
        print(f"Error in toggle_beam_pocket_details: {e}")

def test_toggle_functions():
    """Test all toggle functions"""
    print("Testing toggle functions...")

    # Create a simple test window
    root = tk.Tk()
    root.title("Toggle Function Test")
    root.geometry("400x300")

    # Create test frames and buttons
    tech_frame = tk.Frame(root, bg='lightgreen', height=50)
    tech_button = tk.Button(root, text='▶', command=lambda: toggle_technical_specs(tech_button, tech_frame))
    tech_button.pack(pady=5)

    sub_frame = tk.Frame(root, bg='lightblue', height=50)
    sub_button = tk.Button(root, text='▶', command=lambda: toggle_subassembly_details(sub_button, sub_frame))
    sub_button.pack(pady=5)

    beam_frame = tk.Frame(root, bg='lightyellow', height=50)
    beam_button = tk.Button(root, text='▶', command=lambda: toggle_beam_pocket_details(beam_button, beam_frame))
    beam_button.pack(pady=5)

    # Add labels
    tk.Label(root, text="Click buttons above to test toggle functions").pack(pady=10)
    tk.Label(root, text="Check console output for function calls").pack(pady=5)

    print("Test GUI created. Click the buttons to test toggle functions.")
    print("Each click should show/hide the colored frame and print status to console.")

    root.mainloop()

if __name__ == '__main__':
    test_toggle_functions()
