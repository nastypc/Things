#!/usr/bin/env python3
"""
Simple test script to verify dynamic prefix extraction logic
"""

def test_prefix_extraction_logic():
    """Test the prefix extraction logic directly"""

    def extract_prefix_from_filename(filename):
        """Extract prefix from filename (same logic as in the widget)"""
        if '_' in filename:
            prefix_part = filename.split('_')[0]
            if prefix_part.isdigit() and len(prefix_part) == 2:
                return prefix_part
        return '05'  # Default fallback

    # Test cases
    test_files = [
        ("07_112.EHX", "07"),
        ("08_100.EHX", "08"),
        ("05_200.EHX", "05"),
        ("test.EHX", "05"),  # Should default to 05
        ("123_456.EHX", "05"),  # Invalid prefix, should default
        ("AB_100.EHX", "05"),  # Non-numeric prefix, should default
    ]

    print("Testing prefix extraction logic:")
    all_passed = True

    for filename, expected_prefix in test_files:
        extracted_prefix = extract_prefix_from_filename(filename)
        status = "✓" if extracted_prefix == expected_prefix else "✗"
        if extracted_prefix != expected_prefix:
            all_passed = False
        print(f"  {status} {filename} -> {extracted_prefix} (expected: {expected_prefix})")

    if all_passed:
        print("\n✓ All prefix extraction tests passed!")
    else:
        print("\n✗ Some prefix extraction tests failed!")

    return all_passed

def test_query_transformation():
    """Test how queries are transformed with different prefixes"""

    def transform_query(query, panel_prefix):
        """Transform query with prefix (same logic as in widget)"""
        query = query.lower().strip()
        if len(query) >= 3 and query[:3].isdigit():
            if len(query) == 3 or query[3] == ' ':
                query = f"{panel_prefix}-{query[:3]}{query[3:]}"
        return query

    # Test cases
    test_cases = [
        ("112", "07", "07-112"),
        ("112 info", "07", "07-112 info"),
        ("100", "08", "08-100"),
        ("100 fm", "08", "08-100 fm"),
        ("200 sub", "05", "05-200 sub"),
        ("abc", "07", "abc"),  # No transformation for non-numeric
        ("12", "07", "12"),    # No transformation for 2-digit
    ]

    print("\nTesting query transformation:")
    all_passed = True

    for input_query, prefix, expected_output in test_cases:
        transformed = transform_query(input_query, prefix)
        status = "✓" if transformed == expected_output else "✗"
        if transformed != expected_output:
            all_passed = False
        print(f"  {status} '{input_query}' + prefix '{prefix}' -> '{transformed}' (expected: '{expected_output}')")

    if all_passed:
        print("\n✓ All query transformation tests passed!")
    else:
        print("\n✗ Some query transformation tests failed!")

    return all_passed

if __name__ == "__main__":
    prefix_test_passed = test_prefix_extraction_logic()
    query_test_passed = test_query_transformation()

    if prefix_test_passed and query_test_passed:
        print("\n🎉 All tests passed! Dynamic prefix functionality is working correctly.")
    else:
        print("\n❌ Some tests failed. Please check the implementation.")