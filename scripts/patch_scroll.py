import re

def patch_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # 1. Update .chart-wrapper CSS to allow scrolling
    css_old = """.chart-wrapper {
  position: relative;
  width: 100%;
  height: 320px; /* Bigger height for easy readability */
}"""
    css_new = """.chart-wrapper {
  position: relative;
  width: 100%;
  height: 320px;
  overflow-x: auto;
  overflow-y: hidden;
}
.chart-container {
  height: 100%;
  min-width: 100%;
  position: relative;
}"""
    content = content.replace(css_old, css_new)

    # 2. Wrap canvases in .chart-container
    for chart_id in ['vitalsChart', 'dynamicsChart', 'structuralChart', 'flowChart']:
        if f'<canvas id="{chart_id}"></canvas>' in content:
            content = content.replace(
                f'<div class="chart-wrapper"><canvas id="{chart_id}"></canvas></div>',
                f'<div class="chart-wrapper"><div class="chart-container" id="{chart_id}-container"><canvas id="{chart_id}"></canvas></div></div>'
            )

    # 3. Fix decoupling loop variables and add dynamic width
    loop_old = """// Decoupled render loop to prevent lag
setInterval(() => {
  lossChart.update();
  gradChart.update();
  lrChart.update();
  memChart.update();
}, 50); // render at ~20 FPS instead of 200 FPS"""
    loop_new = """// Decoupled render loop to prevent lag & dynamic scrolling width
setInterval(() => {
  if (typeof vitalsChart !== 'undefined') vitalsChart.update();
  if (typeof dynamicsChart !== 'undefined') dynamicsChart.update();
  if (typeof structuralChart !== 'undefined') structuralChart.update();
  if (typeof flowChart !== 'undefined') flowChart.update();
  
  const minPixelsPerPoint = 2; // Adjust for spacing
  const requiredWidth = Math.max(100, steps.length * minPixelsPerPoint);
  
  document.querySelectorAll('.chart-container').forEach(c => {
    c.style.width = requiredWidth + 'px';
  });
}, 50); // render at ~20 FPS instead of 200 FPS"""
    
    content = content.replace(loop_old, loop_new)

    with open(filepath, 'w') as f:
        f.write(content)
        print(f"Patched scrolling and variable names in {filepath}")

patch_file('media/demo_dashboard.html')
