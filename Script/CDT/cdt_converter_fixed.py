#!/usr/bin/env python3
import sys
import os
import re
from pathlib import Path

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

def should_convert_line(line):
    """Check if line should get imperial conversion."""
    # Only convert lines that start with coordinate record types
    coordinate_types = ['ELM:', 'SPB:', 'STA:', 'BOO1:', 'INKT:', 'NL:', 'GL:', 'ROB:', 'RL:']
    return any(line.startswith(coord_type) for coord_type in coordinate_types)

def convert_line(line):
    """Convert coordinate line to imperial."""
    numbers = re.findall(r'(\d+\.?\d*)', line)
    if len(numbers) < 3:
        return None

    imperial_parts = [mm_to_imperial(float(num)) for num in numbers]

    parts = line.split(':')
    result_parts = []
    num_index = 0

    for part in parts:
        part = part.strip()
        if re.match(r'^\d+\.?\d*$', part) and num_index < len(imperial_parts):
            result_parts.append(imperial_parts[num_index])
            num_index += 1
        else:
            result_parts.append(part)

    return ':'.join(result_parts)

def process_file(input_file, suffix):
    """Process CDT file."""
    input_path = Path(input_file)
    output_file = input_path.parent / f"{input_path.stem}_{suffix}{input_path.suffix}"

    print(f"Processing {input_file} -> {output_file}")

    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    processed_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            processed_lines.append("")
            continue

        # Add the original line
        processed_lines.append(line)

        # Add imperial conversion only for coordinate lines
        if should_convert_line(line):
            imperial = convert_line(line)
            if imperial:
                processed_lines.append(f"TXT:{imperial}")
        elif line.startswith('STE'):
            # Replace STE with TXT:
            processed_lines.append("TXT:")

    with open(output_file, 'w', encoding='utf-8') as f:
        for line in processed_lines:
            f.write(line + '\n')

    print(f"Created {output_file}")

def main():
    if len(sys.argv) < 3:
        print("Usage: python cdt_converter.py <input_file.cdt> <suffix1> [suffix2] ...")
        sys.exit(1)

    input_file = sys.argv[1]
    if not os.path.exists(input_file):
        print(f"File not found: {input_file}")
        sys.exit(1)

    for suffix in sys.argv[2:]:
        process_file(input_file, suffix)

    print("Done!")

if __name__ == "__main__":
    main()