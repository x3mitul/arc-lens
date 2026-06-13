import re

def patch_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # 1. Revert CSS
    css_old = """.chart-wrapper {
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
    css_new = """.chart-wrapper {
  position: relative;
  width: 100%;
  height: 320px; /* Bigger height for easy readability */
}"""
    content = content.replace(css_old, css_new)

    # 2. Revert Canvas HTML Wrappers
    for chart_id in ['vitalsChart', 'dynamicsChart', 'structuralChart', 'flowChart']:
        content = content.replace(
            f'<div class="chart-wrapper"><div class="chart-container" id="{chart_id}-container"><canvas id="{chart_id}"></canvas></div></div>',
            f'<div class="chart-wrapper"><canvas id="{chart_id}"></canvas></div>'
        )

    # 3. Revert interval width logic
    loop_old = """// Decoupled render loop to prevent lag & dynamic scrolling width
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
}, 100); // render at 10 FPS for buttery performance without stuttering"""
    loop_new = """// Decoupled render loop
setInterval(() => {
  if (typeof vitalsChart !== 'undefined') vitalsChart.update();
  if (typeof dynamicsChart !== 'undefined') dynamicsChart.update();
  if (typeof structuralChart !== 'undefined') structuralChart.update();
  if (typeof flowChart !== 'undefined') flowChart.update();
}, 100);"""
    content = content.replace(loop_old, loop_new)

    # 4. Inject Hammer.js and Chartjs-Plugin-Zoom scripts
    if "hammerjs" not in content:
        content = content.replace(
            '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>',
            '<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>\n<script src="https://cdn.jsdelivr.net/npm/hammerjs@2.0.8"></script>\n<script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-zoom@2.0.1"></script>'
        )

    # 5. Add plugin zoom config to commonOptions
    if "zoom: {" not in content:
        # we need to inject the plugins: { zoom: ... } into all charts
        # Since they don't share a common plugins object, we can add it to commonOptions so we don't have to rewrite every chart.
        # But wait, plugins is at the root of the chart config, NOT inside `options`!
        # Actually, in Chart.js v3+, plugins config is inside `options.plugins`!
        # Let's check where commonScales is.
        zoom_config = """
    zoom: {
      pan: { enabled: true, mode: 'x' },
      zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' }
    },"""
        # wait, let's inject it into Chart options. The charts look like:
        # options: {
        #   responsive: true,
        #   animation: false,
        #   maintainAspectRatio: false,
        #   interaction: { mode: 'index', intersect: false },
        #   scales: { ... }
        # }
        content = re.sub(
            r"(interaction: \{ mode: 'index', intersect: false \},)",
            r"\1\n    plugins: {" + zoom_config + "},",
            content
        )

    with open(filepath, 'w') as f:
        f.write(content)
        print("Fixed poorly fit scrolling")

patch_file('media/demo_dashboard.html')
