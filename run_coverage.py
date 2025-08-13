#!/usr/bin/env python3
"""
Simple Python-based coverage runner that handles dependencies and virtual environments properly.
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

def check_and_install_dependencies():
    """Check and install required dependencies."""
    print("🔍 Checking dependencies...")
    
    # Check if pytest-cov is installed
    try:
        import pytest_cov
        print("✅ pytest-cov is installed")
    except ImportError:
        print("📦 Installing test dependencies...")
        subprocess.check_call([
            sys.executable, '-m', 'pip', 'install', '-r', 
            'tests/requirements-test.txt'
        ])
        print("✅ Dependencies installed")

def run_coverage():
    """Run the coverage analysis."""
    print("\n🧪 Running coverage analysis...")
    
    # Import the coverage module after ensuring dependencies
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'scripts'))
    
    try:
        from coverage import main as coverage_main
        
        # Change sys.argv to simulate command line arguments
        original_argv = sys.argv
        sys.argv = ['coverage.py']
        
        # Run coverage analysis
        exit_code = coverage_main()
        
        # Restore original argv
        sys.argv = original_argv
        
        return exit_code
        
    except Exception as e:
        print(f"❌ Error running coverage: {e}")
        return 1

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='My Story Buddy Backend Coverage Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_coverage.py              # Run full coverage analysis
  python run_coverage.py --quick      # Quick coverage check
  python run_coverage.py --dashboard  # Generate and open dashboard
  python run_coverage.py --watch      # Start watch mode
        """
    )
    
    parser.add_argument('--quick', action='store_true', 
                       help='Run quick coverage check')
    parser.add_argument('--dashboard', action='store_true',
                       help='Generate and open coverage dashboard')
    parser.add_argument('--watch', action='store_true',
                       help='Start coverage watch mode')
    parser.add_argument('--install-deps', action='store_true',
                       help='Install dependencies only')
    
    args = parser.parse_args()
    
    # Always check dependencies first
    check_and_install_dependencies()
    
    if args.install_deps:
        print("✅ Dependencies check complete")
        return 0
    
    # Handle different modes
    if args.quick:
        print("\n⚡ Running quick coverage check...")
        return subprocess.call([
            sys.executable, 'scripts/coverage.py', '--quick'
        ])
    
    elif args.dashboard:
        print("\n📊 Generating coverage dashboard...")
        # First run coverage to ensure we have data
        subprocess.call([sys.executable, 'scripts/coverage.py'])
        return subprocess.call([
            sys.executable, 'scripts/coverage-dashboard.py', '--auto-open'
        ])
    
    elif args.watch:
        print("\n👁️  Starting coverage watch mode...")
        try:
            import watchdog
        except ImportError:
            print("📦 Installing watchdog for watch mode...")
            subprocess.check_call([
                sys.executable, '-m', 'pip', 'install', 'watchdog'
            ])
        
        return subprocess.call([
            sys.executable, 'scripts/coverage-watch.py'
        ])
    
    else:
        # Default: run full coverage analysis
        return run_coverage()

if __name__ == '__main__':
    sys.exit(main())