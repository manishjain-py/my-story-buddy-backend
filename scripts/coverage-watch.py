#!/usr/bin/env python3
"""
Real-time Coverage Monitoring Script

Watches for file changes and automatically runs coverage analysis,
providing continuous feedback on test coverage as you develop.
"""

import os
import sys
import time
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import threading
import json
from datetime import datetime

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

class CoverageWatcher(FileSystemEventHandler):
    """File system event handler for coverage monitoring."""
    
    def __init__(self, analyzer):
        self.analyzer = analyzer
        self.last_run = 0
        self.debounce_seconds = 3  # Wait 3 seconds after last change
        self.timer = None
        
    def on_modified(self, event):
        if event.is_directory:
            return
            
        # Only watch Python files
        if not event.src_path.endswith('.py'):
            return
            
        # Ignore coverage reports and cache files
        if any(ignore in event.src_path for ignore in [
            '__pycache__', '.pytest_cache', 'coverage_reports',
            '.coverage', 'htmlcov'
        ]):
            return
            
        print(f"📝 File changed: {Path(event.src_path).name}")
        
        # Debounce: cancel previous timer and start new one
        if self.timer:
            self.timer.cancel()
            
        self.timer = threading.Timer(self.debounce_seconds, self._run_coverage)
        self.timer.start()
    
    def _run_coverage(self):
        """Run coverage analysis with debouncing."""
        current_time = time.time()
        
        print("\n" + "="*60)
        print(f"🔄 Running coverage analysis... ({datetime.now().strftime('%H:%M:%S')})")
        print("="*60)
        
        # Run quick coverage check
        self.analyzer.run_quick_check()
        
        self.last_run = current_time
        print(f"\n⏰ Watching for changes... (Press Ctrl+C to stop)")


class RealTimeCoverageAnalyzer:
    """Real-time coverage analysis with file watching."""
    
    def __init__(self, project_root):
        self.project_root = Path(project_root)
        self.src_dir = self.project_root / 'src'
        self.tests_dir = self.project_root / 'tests'
        self.coverage_dir = self.project_root / 'coverage_reports'
        self.coverage_dir.mkdir(exist_ok=True)
        
    def run_quick_check(self):
        """Run a quick coverage check with minimal output."""
        cmd = [
            sys.executable, '-m', 'pytest',
            str(self.tests_dir),
            f'--cov={self.src_dir}',
            '--cov-report=term',
            '--cov-report=json:coverage_reports/coverage_watch.json',
            '--quiet',
            '--tb=no'  # No traceback for cleaner output
        ]
        
        try:
            result = subprocess.run(
                cmd,
                cwd=self.src_dir,
                capture_output=True,
                text=True,
                timeout=60  # Shorter timeout for watch mode
            )
            
            if result.returncode == 0:
                self._display_quick_results(result.stdout)
                self._save_watch_data()
            else:
                print("❌ Tests failed:")
                # Show only the essential error info
                lines = result.stdout.split('\n')
                for line in lines[-10:]:  # Last 10 lines
                    if line.strip():
                        print(f"   {line}")
                        
        except subprocess.TimeoutExpired:
            print("⏰ Coverage check timed out (>60s)")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    def _display_quick_results(self, output):
        """Display quick coverage results."""
        lines = output.split('\n')
        
        # Find the TOTAL coverage line
        for line in lines:
            if 'TOTAL' in line and '%' in line:
                parts = line.split()
                if len(parts) >= 4:
                    try:
                        statements = parts[1]
                        missing = parts[2] 
                        coverage = parts[3]
                        
                        # Parse coverage percentage
                        percent = float(coverage.rstrip('%'))
                        
                        # Status emoji
                        if percent >= 90:
                            status = "🟢"
                        elif percent >= 80:
                            status = "🟡"
                        elif percent >= 70:
                            status = "🟠"
                        else:
                            status = "🔴"
                        
                        print(f"📊 Coverage: {coverage} {status} | Lines: {statements} | Missing: {missing}")
                        
                        # Show trend if available
                        self._show_trend_indicator()
                        
                    except ValueError:
                        print(f"📊 {line.strip()}")
                break
    
    def _save_watch_data(self):
        """Save watch session data for trend analysis."""
        json_file = self.coverage_dir / 'coverage_watch.json'
        watch_history_file = self.coverage_dir / 'watch_history.json'
        
        if not json_file.exists():
            return
            
        try:
            with open(json_file, 'r') as f:
                coverage_data = json.load(f)
            
            percent = coverage_data['totals']['percent_covered']
            
            # Save to watch history
            entry = {
                'timestamp': datetime.now().isoformat(),
                'percent_covered': percent,
                'session': 'watch'
            }
            
            history = []
            if watch_history_file.exists():
                try:
                    with open(watch_history_file, 'r') as f:
                        history = json.load(f)
                except:
                    history = []
            
            history.append(entry)
            
            # Keep only last 50 entries for watch mode
            history = history[-50:]
            
            with open(watch_history_file, 'w') as f:
                json.dump(history, f, indent=2)
                
        except Exception as e:
            print(f"⚠️  Could not save watch data: {e}")
    
    def _show_trend_indicator(self):
        """Show trend indicator based on recent watch history."""
        history_file = self.coverage_dir / 'watch_history.json'
        
        if not history_file.exists():
            return
            
        try:
            with open(history_file, 'r') as f:
                history = json.load(f)
            
            if len(history) < 2:
                return
                
            # Compare with previous run
            current = history[-1]['percent_covered']
            previous = history[-2]['percent_covered']
            
            if current > previous:
                print(f"   📈 Improved from {previous:.1f}%")
            elif current < previous:
                print(f"   📉 Decreased from {previous:.1f}%")
            # Don't show anything if no change to keep output clean
                
        except:
            pass  # Silently fail to keep watch mode clean
    
    def start_watching(self):
        """Start watching files for changes."""
        print("🔍 My Story Buddy Backend - Coverage Watch Mode")
        print("="*50)
        print(f"📁 Watching: {self.src_dir} and {self.tests_dir}")
        print(f"📊 Coverage reports: {self.coverage_dir}")
        print("\n⏰ Starting initial coverage analysis...")
        
        # Initial coverage run
        self.run_quick_check()
        
        # Set up file watcher
        event_handler = CoverageWatcher(self)
        observer = Observer()
        
        # Watch both src and tests directories
        observer.schedule(event_handler, str(self.src_dir), recursive=True)
        observer.schedule(event_handler, str(self.tests_dir), recursive=True)
        
        observer.start()
        
        print(f"\n👁️  Watching for changes... (Press Ctrl+C to stop)")
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n🛑 Stopping coverage watch...")
            observer.stop()
            
        observer.join()
        print("✅ Coverage watch stopped.")


def main():
    """Main entry point for coverage watch mode."""
    # Find project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # Check if watchdog is installed
    try:
        from watchdog.observers import Observer
        from watchdog.events import FileSystemEventHandler
    except ImportError:
        print("❌ Coverage watch requires the 'watchdog' package.")
        print("   Install with: pip install watchdog")
        return 1
    
    analyzer = RealTimeCoverageAnalyzer(project_root)
    analyzer.start_watching()
    
    return 0


if __name__ == '__main__':
    exit(main())