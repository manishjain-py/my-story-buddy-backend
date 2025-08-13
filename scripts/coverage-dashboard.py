#!/usr/bin/env python3
"""
Coverage Dashboard Generator

Creates an interactive HTML dashboard showing coverage statistics,
trends, and detailed analysis of test coverage.
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime, timedelta
import argparse

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

class CoverageDashboard:
    """Generates interactive coverage dashboard."""
    
    def __init__(self, project_root):
        self.project_root = Path(project_root)
        self.coverage_dir = self.project_root / 'coverage_reports'
        self.coverage_dir.mkdir(exist_ok=True)
        
    def generate_dashboard(self):
        """Generate complete coverage dashboard."""
        print("📊 Generating Coverage Dashboard...")
        
        # Load coverage data
        coverage_data = self._load_coverage_data()
        history_data = self._load_history_data()
        
        if not coverage_data:
            print("❌ No coverage data found. Run coverage analysis first.")
            return False
        
        # Generate HTML dashboard
        html_content = self._generate_html_dashboard(coverage_data, history_data)
        
        # Save dashboard
        dashboard_file = self.coverage_dir / 'dashboard.html'
        with open(dashboard_file, 'w') as f:
            f.write(html_content)
        
        print(f"✅ Dashboard generated: {dashboard_file}")
        print(f"🌐 Open in browser: file://{dashboard_file.absolute()}")
        
        return True
    
    def _load_coverage_data(self):
        """Load current coverage data."""
        json_file = self.coverage_dir / 'coverage.json'
        
        if not json_file.exists():
            return None
            
        try:
            with open(json_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"❌ Error loading coverage data: {e}")
            return None
    
    def _load_history_data(self):
        """Load coverage history data."""
        history_file = self.coverage_dir / 'coverage_history.json'
        
        if not history_file.exists():
            return []
            
        try:
            with open(history_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Error loading history data: {e}")
            return []
    
    def _generate_html_dashboard(self, coverage_data, history_data):
        """Generate HTML dashboard content."""
        # Extract key metrics
        totals = coverage_data.get('totals', {})
        files = coverage_data.get('files', {})
        
        total_lines = totals.get('num_statements', 0)
        covered_lines = totals.get('covered_lines', 0)
        missing_lines = total_lines - covered_lines
        coverage_percent = totals.get('percent_covered', 0)
        
        # Generate file statistics
        low_coverage_files = []
        high_coverage_files = []
        
        for file_path, data in files.items():
            summary = data['summary']
            percent = summary['percent_covered']
            
            rel_path = file_path.replace(str(self.project_root / 'src') + '/', '')
            
            file_info = {
                'path': rel_path,
                'percent': percent,
                'lines': summary['num_statements'],
                'covered': summary['covered_lines'],
                'missing_lines': data.get('missing_lines', [])
            }
            
            if percent < 80:
                low_coverage_files.append(file_info)
            elif percent >= 95:
                high_coverage_files.append(file_info)
        
        # Sort files
        low_coverage_files.sort(key=lambda x: x['percent'])
        high_coverage_files.sort(key=lambda x: x['percent'], reverse=True)
        
        # Generate trend data for chart
        trend_data = self._generate_trend_data(history_data)
        
        # HTML template
        html_template = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>My Story Buddy Backend - Coverage Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
            color: #333;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .metrics {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .metric-card {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .metric-value {{
            font-size: 2.5em;
            font-weight: bold;
            margin: 10px 0;
        }}
        .metric-label {{
            color: #666;
            font-size: 0.9em;
        }}
        .coverage-excellent {{ color: #28a745; }}
        .coverage-good {{ color: #ffc107; }}
        .coverage-poor {{ color: #dc3545; }}
        .charts {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            margin-bottom: 30px;
        }}
        .chart-container {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .file-lists {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}
        .file-list {{
            background: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .file-item {{
            padding: 10px;
            margin: 5px 0;
            border-radius: 5px;
            background: #f8f9fa;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        .file-path {{
            font-family: monospace;
            font-size: 0.9em;
        }}
        .file-percent {{
            font-weight: bold;
            padding: 4px 8px;
            border-radius: 4px;
        }}
        .percent-excellent {{ background: #d4edda; color: #155724; }}
        .percent-good {{ background: #fff3cd; color: #856404; }}
        .percent-poor {{ background: #f8d7da; color: #721c24; }}
        .timestamp {{
            color: #666;
            font-size: 0.9em;
            margin-top: 20px;
        }}
        .missing-lines {{
            font-size: 0.8em;
            color: #666;
            margin-top: 5px;
        }}
        h2 {{
            color: #333;
            border-bottom: 2px solid #007bff;
            padding-bottom: 5px;
        }}
        .status-indicator {{
            display: inline-block;
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }}
        .status-excellent {{ background: #28a745; }}
        .status-good {{ background: #ffc107; }}
        .status-poor {{ background: #dc3545; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧪 My Story Buddy Backend - Test Coverage Dashboard</h1>
            <p>Comprehensive analysis of test coverage across the entire backend codebase</p>
            <div class="timestamp">
                Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </div>
        </div>
        
        <div class="metrics">
            <div class="metric-card">
                <div class="metric-value coverage-{self._get_coverage_class(coverage_percent)}">{coverage_percent:.1f}%</div>
                <div class="metric-label">Overall Coverage</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">{total_lines}</div>
                <div class="metric-label">Total Lines</div>
            </div>
            <div class="metric-card">
                <div class="metric-value coverage-excellent">{covered_lines}</div>
                <div class="metric-label">Lines Covered</div>
            </div>
            <div class="metric-card">
                <div class="metric-value coverage-poor">{missing_lines}</div>
                <div class="metric-label">Lines Missing</div>
            </div>
        </div>
        
        <div class="charts">
            <div class="chart-container">
                <h2>📈 Coverage Trend</h2>
                <canvas id="trendChart"></canvas>
            </div>
            <div class="chart-container">
                <h2>📊 Coverage Distribution</h2>
                <canvas id="distributionChart"></canvas>
            </div>
        </div>
        
        <div class="file-lists">
            <div class="file-list">
                <h2>🔴 Files Needing Attention (&lt;80%)</h2>
                {self._generate_file_list_html(low_coverage_files, True)}
            </div>
            <div class="file-list">
                <h2>🟢 Well-Tested Files (≥95%)</h2>
                {self._generate_file_list_html(high_coverage_files, False)}
            </div>
        </div>
    </div>
    
    <script>
        // Coverage trend chart
        const trendCtx = document.getElementById('trendChart').getContext('2d');
        new Chart(trendCtx, {{
            type: 'line',
            data: {{
                labels: {trend_data['labels']},
                datasets: [{{
                    label: 'Coverage %',
                    data: {trend_data['values']},
                    borderColor: '#007bff',
                    backgroundColor: 'rgba(0, 123, 255, 0.1)',
                    tension: 0.1,
                    fill: true
                }}]
            }},
            options: {{
                responsive: true,
                scales: {{
                    y: {{
                        beginAtZero: true,
                        max: 100,
                        ticks: {{
                            callback: function(value) {{
                                return value + '%';
                            }}
                        }}
                    }}
                }},
                plugins: {{
                    legend: {{
                        display: false
                    }}
                }}
            }}
        }});
        
        // Coverage distribution chart
        const distCtx = document.getElementById('distributionChart').getContext('2d');
        const distributionData = {self._generate_distribution_data(files)};
        new Chart(distCtx, {{
            type: 'doughnut',
            data: {{
                labels: ['Excellent (90-100%)', 'Good (80-89%)', 'Needs Work (<80%)'],
                datasets: [{{
                    data: [distributionData.excellent, distributionData.good, distributionData.poor],
                    backgroundColor: ['#28a745', '#ffc107', '#dc3545']
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{
                        position: 'bottom'
                    }}
                }}
            }}
        }});
    </script>
</body>
</html>
        """
        
        return html_template
    
    def _get_coverage_class(self, percent):
        """Get CSS class for coverage percentage."""
        if percent >= 90:
            return "excellent"
        elif percent >= 80:
            return "good"
        else:
            return "poor"
    
    def _generate_file_list_html(self, files, show_missing=False):
        """Generate HTML for file lists."""
        if not files:
            return "<p>No files in this category.</p>"
        
        html_parts = []
        
        for file_info in files[:10]:  # Limit to top 10
            percent = file_info['percent']
            path = file_info['path']
            
            if percent >= 90:
                percent_class = "percent-excellent"
            elif percent >= 80:
                percent_class = "percent-good"
            else:
                percent_class = "percent-poor"
            
            html = f"""
            <div class="file-item">
                <div>
                    <div class="file-path">{path}</div>
            """
            
            if show_missing and file_info['missing_lines']:
                missing_lines = file_info['missing_lines'][:10]  # First 10 missing lines
                missing_str = ', '.join(map(str, missing_lines))
                if len(file_info['missing_lines']) > 10:
                    missing_str += f" (+{len(file_info['missing_lines']) - 10} more)"
                html += f'<div class="missing-lines">Missing lines: {missing_str}</div>'
            
            html += f"""
                </div>
                <div class="file-percent {percent_class}">{percent:.1f}%</div>
            </div>
            """
            
            html_parts.append(html)
        
        return ''.join(html_parts)
    
    def _generate_trend_data(self, history_data):
        """Generate trend data for chart."""
        if not history_data or len(history_data) < 2:
            return {'labels': '[]', 'values': '[]'}
        
        # Get last 15 data points
        recent_data = history_data[-15:]
        
        labels = []
        values = []
        
        for entry in recent_data:
            timestamp = datetime.fromisoformat(entry['timestamp'])
            labels.append(timestamp.strftime('%m/%d %H:%M'))
            values.append(round(entry['percent_covered'], 1))
        
        return {
            'labels': json.dumps(labels),
            'values': json.dumps(values)
        }
    
    def _generate_distribution_data(self, files):
        """Generate distribution data for pie chart."""
        excellent = 0  # 90-100%
        good = 0       # 80-89%
        poor = 0       # <80%
        
        for file_path, data in files.items():
            percent = data['summary']['percent_covered']
            
            if percent >= 90:
                excellent += 1
            elif percent >= 80:
                good += 1
            else:
                poor += 1
        
        return {
            'excellent': excellent,
            'good': good,
            'poor': poor
        }


def main():
    """Main entry point for dashboard generation."""
    parser = argparse.ArgumentParser(description='Generate Coverage Dashboard')
    parser.add_argument('--auto-open', action='store_true', help='Automatically open dashboard in browser')
    
    args = parser.parse_args()
    
    # Find project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    dashboard = CoverageDashboard(project_root)
    success = dashboard.generate_dashboard()
    
    if success and args.auto_open:
        import webbrowser
        dashboard_file = project_root / 'coverage_reports' / 'dashboard.html'
        webbrowser.open(f'file://{dashboard_file.absolute()}')
    
    return 0 if success else 1


if __name__ == '__main__':
    exit(main())