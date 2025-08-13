#!/usr/bin/env python3
"""
Test Coverage Analysis Script for My Story Buddy Backend

This script runs the test suite and provides detailed coverage analysis
with visual reports, missing line identification, and coverage trends.
"""

import os
import sys
import subprocess
import json
import argparse
from datetime import datetime
from pathlib import Path
import xml.etree.ElementTree as ET

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

class CoverageAnalyzer:
    """Analyzes test coverage and generates detailed reports."""
    
    def __init__(self, project_root):
        self.project_root = Path(project_root)
        self.src_dir = self.project_root / 'src'
        self.tests_dir = self.project_root / 'tests'
        self.coverage_dir = self.project_root / 'coverage_reports'
        self.coverage_dir.mkdir(exist_ok=True)
        
    def run_coverage_analysis(self, html_report=True, xml_report=True, show_missing=True):
        """Run complete coverage analysis with multiple report formats."""
        print("🔍 Running Test Coverage Analysis...")
        print("=" * 60)
        
        # Build coverage command
        cmd = [
            sys.executable, '-m', 'pytest',
            str(self.tests_dir),
            f'--cov={self.src_dir}',
            '--cov-report=term-missing',
            '--cov-report=json:coverage_reports/coverage.json',
            '-v'
        ]
        
        if html_report:
            cmd.append(f'--cov-report=html:{self.coverage_dir}/html')
        
        if xml_report:
            cmd.append(f'--cov-report=xml:{self.coverage_dir}/coverage.xml')
        
        # Run coverage analysis
        try:
            result = subprocess.run(
                cmd,
                cwd=self.src_dir,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            print("📊 Coverage Analysis Results:")
            print(result.stdout)
            
            if result.stderr:
                print("⚠️  Warnings/Errors:")
                print(result.stderr)
            
            # Parse and display detailed results
            self._parse_coverage_results()
            
            return result.returncode == 0
            
        except subprocess.TimeoutExpired:
            print("❌ Coverage analysis timed out after 5 minutes")
            return False
        except Exception as e:
            print(f"❌ Error running coverage analysis: {e}")
            return False
    
    def _parse_coverage_results(self):
        """Parse coverage results and display detailed analysis."""
        json_file = self.coverage_dir / 'coverage.json'
        
        if not json_file.exists():
            print("❌ Coverage JSON report not found")
            return
        
        try:
            with open(json_file, 'r') as f:
                coverage_data = json.load(f)
            
            # Overall summary
            summary = coverage_data.get('totals', {})
            covered_lines = summary.get('covered_lines', 0)
            num_statements = summary.get('num_statements', 0)
            percent_covered = summary.get('percent_covered', 0)
            
            print("\n📈 COVERAGE SUMMARY")
            print("=" * 40)
            print(f"Total Lines of Code: {num_statements}")
            print(f"Lines Covered: {covered_lines}")
            print(f"Lines Missing: {num_statements - covered_lines}")
            print(f"Coverage Percentage: {percent_covered:.1f}%")
            
            # Coverage status
            if percent_covered >= 90:
                status = "🟢 EXCELLENT"
            elif percent_covered >= 80:
                status = "🟡 GOOD"
            elif percent_covered >= 70:
                status = "🟠 NEEDS IMPROVEMENT"
            else:
                status = "🔴 POOR"
            
            print(f"Coverage Status: {status}")
            
            # Per-file breakdown
            files = coverage_data.get('files', {})
            self._display_file_coverage(files)
            
            # Save historical data
            self._save_coverage_history(percent_covered, covered_lines, num_statements)
            
        except Exception as e:
            print(f"❌ Error parsing coverage results: {e}")
    
    def _display_file_coverage(self, files):
        """Display coverage breakdown by file."""
        print("\n📁 COVERAGE BY FILE")
        print("=" * 60)
        print(f"{'File':<40} {'Lines':<8} {'Covered':<8} {'%':<8} {'Status'}")
        print("-" * 60)
        
        sorted_files = sorted(files.items(), key=lambda x: x[1]['summary']['percent_covered'])
        
        for file_path, data in sorted_files:
            # Get relative path from src directory
            rel_path = file_path.replace(str(self.src_dir) + '/', '')
            if len(rel_path) > 35:
                rel_path = '...' + rel_path[-32:]
            
            summary = data['summary']
            lines = summary['num_statements']
            covered = summary['covered_lines']
            percent = summary['percent_covered']
            
            # Status indicator
            if percent >= 90:
                status = "🟢"
            elif percent >= 80:
                status = "🟡"
            elif percent >= 70:
                status = "🟠"
            else:
                status = "🔴"
            
            print(f"{rel_path:<40} {lines:<8} {covered:<8} {percent:<7.1f}% {status}")
            
            # Show missing lines if coverage is below 80%
            if percent < 80:
                missing_lines = data.get('missing_lines', [])
                if missing_lines and len(missing_lines) <= 10:  # Don't show too many
                    missing_str = ', '.join(map(str, missing_lines))
                    print(f"  📍 Missing lines: {missing_str}")
                elif len(missing_lines) > 10:
                    print(f"  📍 Missing lines: {len(missing_lines)} lines need coverage")
    
    def _save_coverage_history(self, percent, covered_lines, total_lines):
        """Save coverage data for trend analysis."""
        history_file = self.coverage_dir / 'coverage_history.json'
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'percent_covered': percent,
            'covered_lines': covered_lines,
            'total_lines': total_lines
        }
        
        history = []
        if history_file.exists():
            try:
                with open(history_file, 'r') as f:
                    history = json.load(f)
            except:
                history = []
        
        history.append(entry)
        
        # Keep only last 30 entries
        history = history[-30:]
        
        with open(history_file, 'w') as f:
            json.dump(history, f, indent=2)
    
    def show_coverage_trend(self):
        """Display coverage trend over time."""
        history_file = self.coverage_dir / 'coverage_history.json'
        
        if not history_file.exists():
            print("📊 No coverage history available yet. Run coverage analysis first.")
            return
        
        try:
            with open(history_file, 'r') as f:
                history = json.load(f)
            
            if len(history) < 2:
                print("📊 Need at least 2 coverage runs to show trends.")
                return
            
            print("\n📈 COVERAGE TREND (Last 10 runs)")
            print("=" * 50)
            
            recent_history = history[-10:]
            
            for i, entry in enumerate(recent_history):
                timestamp = datetime.fromisoformat(entry['timestamp'])
                percent = entry['percent_covered']
                
                # Show trend arrow
                if i > 0:
                    prev_percent = recent_history[i-1]['percent_covered']
                    if percent > prev_percent:
                        trend = "📈"
                    elif percent < prev_percent:
                        trend = "📉"
                    else:
                        trend = "➡️"
                else:
                    trend = "📊"
                
                print(f"{timestamp.strftime('%Y-%m-%d %H:%M')} | {percent:5.1f}% {trend}")
            
            # Summary
            first_percent = recent_history[0]['percent_covered']
            last_percent = recent_history[-1]['percent_covered']
            change = last_percent - first_percent
            
            if change > 0:
                print(f"\n🎉 Coverage improved by {change:.1f}% over time!")
            elif change < 0:
                print(f"\n⚠️  Coverage decreased by {abs(change):.1f}% over time.")
            else:
                print(f"\n➡️  Coverage remained stable at {last_percent:.1f}%")
                
        except Exception as e:
            print(f"❌ Error displaying coverage trend: {e}")
    
    def generate_coverage_badge(self):
        """Generate a coverage badge for README."""
        json_file = self.coverage_dir / 'coverage.json'
        
        if not json_file.exists():
            return None
        
        try:
            with open(json_file, 'r') as f:
                coverage_data = json.load(f)
            
            percent = coverage_data['totals']['percent_covered']
            
            # Determine badge color
            if percent >= 90:
                color = "brightgreen"
            elif percent >= 80:
                color = "green"
            elif percent >= 70:
                color = "yellow"
            elif percent >= 60:
                color = "orange"
            else:
                color = "red"
            
            badge_url = f"https://img.shields.io/badge/coverage-{percent:.0f}%25-{color}"
            
            badge_file = self.coverage_dir / 'coverage_badge.md'
            with open(badge_file, 'w') as f:
                f.write(f"![Coverage Badge]({badge_url})\n")
                f.write(f"Coverage: {percent:.1f}%\n")
            
            print(f"\n🏷️  Coverage badge generated: {badge_url}")
            return badge_url
            
        except Exception as e:
            print(f"❌ Error generating coverage badge: {e}")
            return None
    
    def check_coverage_requirements(self, min_coverage=80):
        """Check if coverage meets minimum requirements."""
        json_file = self.coverage_dir / 'coverage.json'
        
        if not json_file.exists():
            print("❌ No coverage data available")
            return False
        
        try:
            with open(json_file, 'r') as f:
                coverage_data = json.load(f)
            
            percent = coverage_data['totals']['percent_covered']
            
            if percent >= min_coverage:
                print(f"✅ Coverage requirement met: {percent:.1f}% >= {min_coverage}%")
                return True
            else:
                print(f"❌ Coverage requirement not met: {percent:.1f}% < {min_coverage}%")
                shortfall = min_coverage - percent
                print(f"   Need to improve coverage by {shortfall:.1f}%")
                return False
                
        except Exception as e:
            print(f"❌ Error checking coverage requirements: {e}")
            return False
    
    def find_untested_functions(self):
        """Identify functions/methods that lack test coverage."""
        print("\n🔍 ANALYZING UNTESTED CODE")
        print("=" * 40)
        
        # This would require more complex AST analysis
        # For now, provide guidance on using the HTML report
        html_report = self.coverage_dir / 'html' / 'index.html'
        
        if html_report.exists():
            print("📝 For detailed untested code analysis:")
            print(f"   Open: {html_report}")
            print("   Look for red highlighted lines in individual file reports")
        else:
            print("❌ HTML coverage report not found. Run with --html flag.")
    
    def run_quick_check(self):
        """Run a quick coverage check without full analysis."""
        print("⚡ Quick Coverage Check...")
        
        cmd = [
            sys.executable, '-m', 'pytest',
            str(self.tests_dir),
            f'--cov={self.src_dir}',
            '--cov-report=term',
            '--quiet'
        ]
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.src_dir,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                # Extract coverage percentage from output
                lines = result.stdout.split('\n')
                for line in lines:
                    if 'TOTAL' in line and '%' in line:
                        print(f"📊 {line.strip()}")
                        break
            else:
                print("❌ Quick coverage check failed")
                print(result.stderr)
                
        except Exception as e:
            print(f"❌ Error in quick coverage check: {e}")


def main():
    """Main CLI interface for coverage analysis."""
    parser = argparse.ArgumentParser(description='My Story Buddy Backend Coverage Analysis')
    parser.add_argument('--quick', action='store_true', help='Run quick coverage check')
    parser.add_argument('--trend', action='store_true', help='Show coverage trend')
    parser.add_argument('--badge', action='store_true', help='Generate coverage badge')
    parser.add_argument('--check', type=int, default=80, help='Check minimum coverage requirement')
    parser.add_argument('--no-html', action='store_true', help='Skip HTML report generation')
    parser.add_argument('--watch', action='store_true', help='Watch mode - run on file changes')
    
    args = parser.parse_args()
    
    # Find project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    analyzer = CoverageAnalyzer(project_root)
    
    if args.quick:
        analyzer.run_quick_check()
    elif args.trend:
        analyzer.show_coverage_trend()
    elif args.badge:
        analyzer.generate_coverage_badge()
    elif args.watch:
        print("🔄 Watch mode not implemented yet. Use --quick for frequent checks.")
    else:
        # Full coverage analysis
        success = analyzer.run_coverage_analysis(html_report=not args.no_html)
        
        if success:
            analyzer.generate_coverage_badge()
            analyzer.check_coverage_requirements(args.check)
            analyzer.find_untested_functions()
        
        return 0 if success else 1


if __name__ == '__main__':
    exit(main())