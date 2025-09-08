#!/usr/bin/env python3
"""
Test script to verify bundle pagination logic
"""

def test_bundle_pagination():
    # Simulate the bundle pagination logic
    all_bundle_keys = ['BundleA', 'BundleB', 'BundleC', 'BundleD', 'BundleE', 'BundleF']
    bundles_per_page = 5

    # Calculate total pages
    total_bundle_pages = (len(all_bundle_keys) + bundles_per_page - 1) // bundles_per_page
    print(f"Total bundles: {len(all_bundle_keys)}")
    print(f"Bundles per page: {bundles_per_page}")
    print(f"Total bundle pages: {total_bundle_pages}")

    # Test pagination for each page
    for page in range(total_bundle_pages):
        start_idx = page * bundles_per_page
        end_idx = min(start_idx + bundles_per_page, len(all_bundle_keys))
        page_bundle_keys = all_bundle_keys[start_idx:end_idx]

        print(f"\nPage {page + 1}:")
        print(f"  Bundles: {page_bundle_keys}")
        print(f"  Navigation: Prev={'disabled' if page == 0 else 'enabled'}, Next={'disabled' if page == total_bundle_pages - 1 else 'enabled'}")

if __name__ == "__main__":
    test_bundle_pagination()
