import re

def patch_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # 1. Fix MAX_DATAPOINTS to allow full 1000 step history for scrolling
    content = content.replace("const MAX_DATAPOINTS = 100;", "const MAX_DATAPOINTS = 100000;")
    
    # 2. Add Download Buttons to chart headers
    download_svg = '<svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" style="margin-right:4px"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>'
    
    charts = {
        'Training Vitals & Loss Trajectory': 'vitalsChart',
        'Gradient Dynamics': 'dynamicsChart',
        'Structural Integrity & Rank': 'structuralChart',
        'Weight & Flow Dynamics': 'flowChart'
    }
    
    for title, chart_id in charts.items():
        old_header = f'<div class="chart-header"><div class="chart-title">{title}</div></div>'
        new_header = f'<div class="chart-header" style="display:flex; justify-content:space-between; align-items:center;"><div class="chart-title">{title}</div><button class="btn-theme" style="padding: 4px 8px; font-size: 12px; display:flex; align-items:center; border: 1px solid var(--panel-border);" onclick="downloadChart(\'{chart_id}\')" title="Download Graph">{download_svg}Download</button></div>'
        content = content.replace(old_header, new_header)

    # 3. Add JS function for download
    download_js = """
// Download Chart Utility
function downloadChart(chartId) {
  const canvas = document.getElementById(chartId);
  if (!canvas) return;
  
  // Create a temporary canvas to draw the chart with a solid background
  // because ChartJS canvases are transparent by default.
  const tempCanvas = document.createElement('canvas');
  tempCanvas.width = canvas.width;
  tempCanvas.height = canvas.height;
  const ctx = tempCanvas.getContext('2d');
  
  // Fill background
  const bgColor = getComputedStyle(document.body).getPropertyValue('--panel-bg').trim() || '#ffffff';
  ctx.fillStyle = bgColor;
  ctx.fillRect(0, 0, tempCanvas.width, tempCanvas.height);
  
  // Draw chart
  ctx.drawImage(canvas, 0, 0);
  
  const link = document.createElement('a');
  link.download = chartId + '.png';
  link.href = tempCanvas.toDataURL('image/png');
  link.click();
}
"""
    if "function downloadChart" not in content:
        content = content.replace("function toggleTheme() {", download_js + "\nfunction toggleTheme() {")

    with open(filepath, 'w') as f:
        f.write(content)
        print(f"Patched download buttons & scrolling limit in {filepath}")

patch_file('media/demo_dashboard.html')
