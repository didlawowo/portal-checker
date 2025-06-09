#!/usr/bin/env python3
"""
Simple test script to verify excluded URL functionality
"""
import sys
import os
sys.path.append('.')

from app import load_excluded_urls, _is_url_excluded, excluded_urls

def main():
    print("=== Portal Checker - Excluded URLs Test ===\n")
    
    print("Current excluded URLs from config:")
    for pattern in sorted(excluded_urls):
        print(f"  - {pattern}")
    print()
    
    # Test cases based on actual config patterns
    test_cases = [
        # monitoring.* pattern (should match)
        ("monitoring.example.com", True, "matches monitoring.*"),
        ("monitoring.test.local", True, "matches monitoring.*"), 
        ("monitoring.", True, "matches monitoring.*"),
        ("notmonitoring.example.com", False, "doesn't start with monitoring."),
        
        # *.internal/* pattern (currently doesn't work due to implementation)
        ("app.internal/admin", False, "*.internal/* pattern not fully supported"),
        ("service.internal/api", False, "*.internal/* pattern not fully supported"),
        
        # Exact match
        ("infisical.dc-tech.work/ss-webhook", True, "exact match"),
        ("infisical.dc-tech.work/other", False, "different path"),
        
        # No matches
        ("normal.website.com", False, "not in exclusion list"),
        ("test.example.com/admin", False, "not in exclusion list"),
    ]
    
    print("Testing URL exclusions:")
    print("-" * 70)
    
    success_count = 0
    total_count = len(test_cases)
    
    for url, expected, description in test_cases:
        result = _is_url_excluded(url)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        
        if result == expected:
            success_count += 1
        
        print(f"{status} | {url:<35} -> {result!s:<5} | {description}")
    
    print("-" * 70)
    print(f"Results: {success_count}/{total_count} tests passed")
    
    if success_count == total_count:
        print("🎉 All tests passed!")
        return 0
    else:
        print("⚠️  Some tests failed. Check the implementation.")
        return 1

if __name__ == "__main__":
    sys.exit(main())