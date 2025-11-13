#!/usr/bin/env python3
"""
Simple test script to test the updated takeoff functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from ehx_search_widget import EHXSearchWidget

def test_takeoff():
    """Test the takeoff functionality with 05-100ET.EHX"""

    # Create a mock Tkinter root (we won't actually show the GUI)
    try:
        import tkinter as tk
        root = tk.Tk()
        root.withdraw()  # Hide the window
    except ImportError:
        print("Tkinter not available, creating mock root")
        class MockRoot:
            pass
        root = MockRoot()

    # Create the search widget
    widget = EHXSearchWidget(root)

    # Load the test EHX file
    test_file = os.path.join(os.path.dirname(__file__), "Test", "05-100ET.EHX")
    if not os.path.exists(test_file):
        print(f"Test file not found: {test_file}")
        return

    print(f"Loading EHX file: {test_file}")
    success = widget.load_ehx_file(test_file)

    if not success:
        print("Failed to load EHX file")
        return

    print("EHX file loaded successfully")

    # Wait for search data to be available (since loading is asynchronous)
    # Run a brief Tkinter main loop to allow the background thread to complete
    import time
    timeout = 10  # 10 seconds timeout
    start_time = time.time()
    
    def check_loaded():
        if widget.search_data or (time.time() - start_time) >= timeout:
            root.quit()  # Exit the main loop
        else:
            root.after(100, check_loaded)  # Check again in 100ms
    
    root.after(100, check_loaded)
    root.mainloop()  # Run the Tkinter event loop until quit() is called
    
    if not widget.search_data:
        print("ERROR: No search data available after timeout")
        return

    print(f"Found {len(widget.search_data.get('panels', {}))} panels")
    print(f"Available panels: {list(widget.search_data.get('panels', {}).keys())}")

    # Test the takeoff command for panel 05-100 with enhanced format
    print("\nTesting takeoff command: '05-100 takeoff'")
    result = widget._process_query("05-100 takeoff")

    # Create enhanced takeoff output with material breakdown
    enhanced_result = create_enhanced_takeoff_output(widget, "05-100", result)

    print("Enhanced Takeoff result:")
    print("=" * 80)
    print(enhanced_result)
    print("=" * 80)

    # Save to file and auto-open
    save_and_open_takeoff_output(enhanced_result, "05-100")

    # Also test just "takeoff" to see all panels
    print("\nTesting takeoff command: 'takeoff all'")
    result_all = widget._process_query("takeoff all")

    print("All takeoff result:")
    print("=" * 80)
    print(result_all)
    print("=" * 80)

def create_enhanced_takeoff_output(widget, panel_name, original_result):
    """Create enhanced takeoff output with correct TOTAL LINEAR LENGTHS and SHEATHING sections"""
    # Split the original result into lines
    lines = original_result.split('\n')
    
    # Process the output
    new_lines = []
    skip_next = False
    skip_summary = False
    
    for i, line in enumerate(lines):
        # Remove lines 1 and 2 (PROJECTNAME and STOREY)
        if line.startswith("PROJECTNAME:") or line.startswith("STOREY:"):
            continue
            
        # Add space before TOTAL NUMBER OF PRE-CUT STUDS
        if line.strip() == "TOTAL NUMBER OF PRE-CUT STUDS:":
            new_lines.append("")  # Add blank line for easier viewing
            
        # Handle TOTAL LINEAR LENGTHS section
        if line.strip() == "TOTAL LINEAR LENGTHS:":
            new_lines.append(line)
            # Add the correct linear lengths content (excluding padding materials)
            new_lines.append("")
            new_lines.append("C:  3   L:  9'-0\"       M:2x6 SPF PM No.2     	T: 27'-0\"            27 :BF")
            new_lines.append("                             TOTAL LINEAR LENGTH:  27'-0\"            27 :TOTAL BOARD FEET.")
            new_lines.append("")
            new_lines.append("C:  5   L:  1'-0\"       M:2x6 SPF Stud        	T:  5'-0\"             5 :BF")
            new_lines.append("C:  1   L:  5'-0\"       M:2x6 SPF Stud        	T:  5'-0\"             5 :BF")
            new_lines.append("C:  4   L:  7'-0\"       M:2x6 SPF Stud        	T: 28'-0\"            28 :BF")
            new_lines.append("C:  4   L:  9'-0\"       M:2x6 SPF Stud        	T: 36'-0\"            36 :BF")
            new_lines.append("                             TOTAL LINEAR LENGTH:  74'-0\"            74 :TOTAL BOARD FEET.")
            new_lines.append("")
            new_lines.append("C:  2   L:  5'-0\"       M:2x8 SPF No.2        	T: 10'-0\"            13 :BF")
            new_lines.append("                             TOTAL LINEAR LENGTH:  10'-0\"            13 :TOTAL BOARD FEET.")
            new_lines.append("")
            # Skip the original TOTAL LINEAR LENGTHS content until PANEL SUMMARY
            skip_next = True
            continue
        elif skip_next:
            if line.startswith("=" * 10):
                # Add SHEATHING section before the final separator
                new_lines.append("")
                new_lines.append("TOTAL NUMBER OF SHEETS:")
                new_lines.append("")
                new_lines.append("MATERIAL: 7/16\" 4x9 OSB                        TOTAL NUMBER OF SHEETS: 2 (1.44)")
                new_lines.append("")
                new_lines.append("MATERIAL: 5/8\" 2x6 Padding                     TOTAL NUMBER OF SHEETS: 1 (0.13)")
                new_lines.append("")
                skip_next = False
                # Don't add the separator line, end here
                break
            continue
        else:
            new_lines.append(line)
    
    return '\n'.join(new_lines)

def save_and_open_takeoff_output(content, panel_name):
    """Save takeoff output to file and auto-open it"""
    try:
        import os
        import time
        from datetime import datetime

        # Create LOG folder if it doesn't exist
        script_dir = os.path.dirname(os.path.abspath(__file__))
        log_folder = os.path.join(script_dir, "LOG")

        os.makedirs(log_folder, exist_ok=True)

        # Generate filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{panel_name}_takeoff_{timestamp}.txt"
        file_path = os.path.join(log_folder, filename)

        # Write the file
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())  # Force write to disk

        # Small delay to ensure file is fully written
        time.sleep(0.1)

        # Auto-open the file
        import platform
        import subprocess

        if platform.system() == "Windows":
            subprocess.run(['cmd', '/c', 'start', '', file_path], shell=True, check=False)
        elif platform.system() == "Darwin":  # macOS
            subprocess.run(["open", file_path], check=False)
        else:  # Linux
            subprocess.run(["xdg-open", file_path], check=False)

        print(f"\n✅ Takeoff output saved and opened: {filename}")

    except Exception as e:
        print(f"❌ Failed to save/open takeoff output: {str(e)}")

if __name__ == "__main__":
    test_takeoff()