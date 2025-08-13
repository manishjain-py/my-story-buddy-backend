#!/bin/bash
# Comprehensive Coverage Analysis Runner
# This script provides a simple interface to run different types of coverage analysis

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to detect Python command
detect_python() {
    if command -v python3 &> /dev/null; then
        echo "python3"
    elif command -v python &> /dev/null; then
        echo "python"
    else
        print_error "Python not found. Please install Python 3.7+"
        exit 1
    fi
}

# Set Python command
PYTHON_CMD=$(detect_python)

# Function to check if Python packages are installed
check_dependencies() {
    print_status "Checking dependencies..."
    
    cd "$PROJECT_ROOT"
    
    # Check if we're in a virtual environment
    if [[ -z "$VIRTUAL_ENV" ]] && [[ -d "venv" ]]; then
        print_warning "Virtual environment detected but not activated."
        print_status "Activating virtual environment..."
        source venv/bin/activate
    fi
    
    # Check if pytest-cov is installed
    if ! $PYTHON_CMD -c "import pytest_cov" 2>/dev/null; then
        print_warning "pytest-cov not found. Installing test dependencies..."
        $PYTHON_CMD -m pip install -r tests/requirements-test.txt
        
        if [ $? -ne 0 ]; then
            print_error "Failed to install dependencies"
            print_status "Try running: $PYTHON_CMD -m pip install -r tests/requirements-test.txt"
            exit 1
        fi
    fi
    
    # Check if watchdog is available for watch mode
    if ! $PYTHON_CMD -c "import watchdog" 2>/dev/null; then
        if [[ "$1" == "watch" ]]; then
            print_warning "watchdog not found. Installing for watch mode..."
            $PYTHON_CMD -m pip install watchdog
            
            if [ $? -ne 0 ]; then
                print_error "Failed to install watchdog"
                exit 1
            fi
        fi
    fi
    
    print_success "Dependencies checked"
}

# Function to run basic coverage analysis
run_basic_coverage() {
    print_status "Running basic coverage analysis..."
    cd "$PROJECT_ROOT"
    
    $PYTHON_CMD scripts/coverage.py
    
    if [ $? -eq 0 ]; then
        print_success "Coverage analysis completed"
        
        # Generate dashboard if coverage data exists
        if [ -f "coverage_reports/coverage.json" ]; then
            print_status "Generating coverage dashboard..."
            $PYTHON_CMD scripts/coverage-dashboard.py
            print_success "Dashboard generated at coverage_reports/dashboard.html"
        fi
    else
        print_error "Coverage analysis failed"
        exit 1
    fi
}

# Function to run quick coverage check
run_quick_coverage() {
    print_status "Running quick coverage check..."
    cd "$PROJECT_ROOT"
    
    $PYTHON_CMD scripts/coverage.py --quick
}

# Function to show coverage trend
show_coverage_trend() {
    print_status "Showing coverage trend..."
    cd "$PROJECT_ROOT"
    
    $PYTHON_CMD scripts/coverage.py --trend
}

# Function to run coverage watch mode
run_coverage_watch() {
    print_status "Starting coverage watch mode..."
    print_status "This will monitor file changes and run coverage analysis automatically"
    print_warning "Press Ctrl+C to stop watching"
    
    cd "$PROJECT_ROOT"
    
    $PYTHON_CMD scripts/coverage-watch.py
}

# Function to open coverage dashboard
open_dashboard() {
    cd "$PROJECT_ROOT"
    
    if [ -f "coverage_reports/dashboard.html" ]; then
        print_status "Opening coverage dashboard..."
        $PYTHON_CMD scripts/coverage-dashboard.py --auto-open
    else
        print_warning "Dashboard not found. Running coverage analysis first..."
        run_basic_coverage
        $PYTHON_CMD scripts/coverage-dashboard.py --auto-open
    fi
}

# Function to check coverage requirements
check_coverage_requirements() {
    local min_coverage=${1:-80}
    
    print_status "Checking coverage requirements (minimum: ${min_coverage}%)..."
    cd "$PROJECT_ROOT"
    
    $PYTHON_CMD scripts/coverage.py --check "$min_coverage"
    
    if [ $? -eq 0 ]; then
        print_success "Coverage requirements met!"
        return 0
    else
        print_error "Coverage requirements not met!"
        return 1
    fi
}

# Function to clean coverage reports
clean_coverage() {
    print_status "Cleaning coverage reports..."
    cd "$PROJECT_ROOT"
    
    rm -rf coverage_reports/
    rm -rf htmlcov/
    rm -f .coverage
    
    print_success "Coverage reports cleaned"
}

# Function to show help
show_help() {
    echo "My Story Buddy Backend - Coverage Analysis Tool"
    echo ""
    echo "Usage: $0 [COMMAND] [OPTIONS]"
    echo ""
    echo "Commands:"
    echo "  run, analyze     Run complete coverage analysis (default)"
    echo "  quick           Run quick coverage check"
    echo "  trend           Show coverage trend over time"
    echo "  watch           Start coverage watch mode (monitors file changes)"
    echo "  dashboard       Generate and open coverage dashboard"
    echo "  check [MIN%]    Check if coverage meets minimum requirement (default: 80%)"
    echo "  clean           Clean all coverage reports"
    echo "  help            Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                    # Run complete coverage analysis"
    echo "  $0 quick             # Quick coverage check"
    echo "  $0 watch             # Start watch mode"
    echo "  $0 check 85          # Check if coverage >= 85%"
    echo "  $0 dashboard         # Generate and open dashboard"
    echo ""
    echo "Output files:"
    echo "  coverage_reports/dashboard.html    - Interactive coverage dashboard"
    echo "  coverage_reports/html/index.html  - Detailed HTML coverage report"
    echo "  coverage_reports/coverage.json    - Coverage data in JSON format"
}

# Main script logic
main() {
    local command=${1:-run}
    
    case "$command" in
        run|analyze)
            check_dependencies
            run_basic_coverage
            ;;
        quick)
            check_dependencies
            run_quick_coverage
            ;;
        trend)
            check_dependencies
            show_coverage_trend
            ;;
        watch)
            check_dependencies "watch"
            run_coverage_watch
            ;;
        dashboard)
            check_dependencies
            open_dashboard
            ;;
        check)
            check_dependencies
            check_coverage_requirements "$2"
            ;;
        clean)
            clean_coverage
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "Unknown command: $command"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"