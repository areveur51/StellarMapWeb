#!/usr/bin/env python
"""
StellarMapWeb Test Runner

Runs comprehensive test suite for the application including:
- Cassandra model integration tests
- Helper function tests with mocked dependencies
- Cron command workflow tests
- View integration tests

Usage:
    python run_tests.py                    # Run all tests
    python run_tests.py --verbose          # Run with verbose output
    python run_tests.py --app apiApp       # Run tests for specific app
    python run_tests.py --pattern test_*   # Run tests matching pattern
"""

import sys
import os
import django
from django.conf import settings
from django.test.utils import get_runner

# Add project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'StellarMapWeb.settings')
django.setup()


def run_tests(verbosity=1, pattern='test_*.py', app_label=None):
    """
    Run Django test suite with specified configuration.
    
    Args:
        verbosity (int): Test output verbosity level (0-3)
        pattern (str): Test file pattern to match
        app_label (str): Specific app to test (e.g., 'apiApp', 'webApp')
    
    Returns:
        int: Number of test failures
    """
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=verbosity, pattern=pattern, keepdb=False)
    
    if app_label:
        test_labels = [app_label]
    else:
        test_labels = ['apiApp.tests', 'webApp.tests', 'radialTidyTreeApp.tests']
    
    failures = test_runner.run_tests(test_labels)
    
    return failures


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Run StellarMapWeb test suite')
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Verbose test output'
    )
    parser.add_argument(
        '--app',
        type=str,
        help='Run tests for specific app (apiApp, webApp, radialTidyTreeApp)'
    )
    parser.add_argument(
        '--pattern', '-p',
        type=str,
        default='test_*.py',
        help='Test file pattern (default: test_*.py)'
    )
    parser.add_argument(
        '--keepdb', '-k',
        action='store_true',
        help='Preserve test database between runs'
    )
    
    args = parser.parse_args()
    
    verbosity = 2 if args.verbose else 1
    
    print("=" * 70)
    print("StellarMapWeb Test Suite")
    print("=" * 70)
    print(f"Verbosity: {verbosity}")
    print(f"Pattern: {args.pattern}")
    if args.app:
        print(f"App: {args.app}")
    else:
        print("Testing: All apps")
    print("=" * 70)
    print()
    
    failures = run_tests(
        verbosity=verbosity,
        pattern=args.pattern,
        app_label=args.app
    )
    
    print()
    print("=" * 70)
    if failures:
        print(f"FAILED: {failures} test(s) failed")
        print("=" * 70)
        sys.exit(1)
    else:
        print("SUCCESS: All tests passed!")
        print("=" * 70)
        sys.exit(0)
