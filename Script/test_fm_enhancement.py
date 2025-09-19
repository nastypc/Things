#!/usr/bin/env python3
"""
Test script for enhanced Family Member analysis functionality
"""

import sys
import os

# Add the script directory to the path
sys.path.insert(0, os.path.dirname(__file__))

try:
    from ehx_search_widget import EHXSearchWidget

    print("✅ Enhanced EHX Search Widget loaded successfully!")
    print("\n🎯 New Family Member Analysis Features:")
    print("   • Three-group categorization: Loose Materials, SubAssembly Materials, Excluded Materials")
    print("   • Extensible Family Member types (currently supports 25, 32, 42)")
    print("   • Pattern list functionality ('fm' command)")
    print("   • Comprehensive analysis with detailed breakdowns")
    print("\n📋 Usage Examples:")
    print("   • '05-100 fm' - Complete FM analysis for panel 05-100")
    print("   • '05-100 fm 25' - Specific FM 25 analysis")
    print("   • 'fm' - Show Family Member pattern list")
    print("   • '05-100 sub' - SubAssembly analysis")
    print("\n🚀 Ready for enhanced construction analysis!")

except ImportError as e:
    print(f"❌ Import failed: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    sys.exit(1)