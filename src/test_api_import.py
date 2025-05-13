#!/usr/bin/env python3
"""Test API import issues"""

import sys
import os
import importlib
import traceback

# Add src to path
sys.path.append(os.path.abspath('.'))

def test_import(module_name):
    """Test importing a module and print results"""
    print(f"Testing import: {module_name}")
    try:
        module = importlib.import_module(module_name)
        print(f"✅ Successfully imported {module_name}")
        return True, module
    except Exception as e:
        print(f"❌ Failed to import {module_name}: {str(e)}")
        traceback.print_exc()
        return False, None

if __name__ == "__main__":
    print("==== Testing API imports ====")
    print(f"Python version: {sys.version}")
    print(f"Current directory: {os.getcwd()}")
    print(f"Python path: {sys.path}")
    
    # Test basic import
    success, _ = test_import('api')
    
    # Test specific imports
    test_import('api.chronicling_america')
    test_import('api.chronicling_america_improved')
    
    # Test client class imports
    test_import('api.chronicling_america.ChroniclingAmericaClient')
    
    # Try the actual imports used in the code
    print("\n==== Testing imports used in code ====")
    try:
        from api.chronicling_america_improved import ImprovedChroniclingAmericaClient as ChroniclingAmericaClient
        print("✅ Successfully imported ImprovedChroniclingAmericaClient")
    except ImportError:
        print("❌ Failed to import ImprovedChroniclingAmericaClient")
        try:
            from api.chronicling_america import ChroniclingAmericaClient
            print("✅ Successfully imported ChroniclingAmericaClient (fallback)")
        except ImportError:
            print("❌ Failed to import ChroniclingAmericaClient (fallback)")
            traceback.print_exc()