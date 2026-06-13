import re

def patch_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # 1. Update Zoom Config to disable auto-scrolling on pan/zoom
    zoom_old = """    zoom: {
      pan: { enabled: true, mode: 'x' },
      zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x' }
    },"""
    zoom_new = """    zoom: {
      pan: { enabled: true, mode: 'x', onPanStart: function() { window.isAutoScrolling = false; } },
      zoom: { wheel: { enabled: true }, pinch: { enabled: true }, mode: 'x', onZoomStart: function() { window.isAutoScrolling = false; } }
    },"""
    content = content.replace(zoom_old, zoom_new)

    # 2. Add isAutoScrolling variable and sliding window logic to interval
    loop_old = """// Decoupled render loop
setInterval(() => {
  if (typeof vitalsChart !== 'undefined') vitalsChart.update();
  if (typeof dynamicsChart !== 'undefined') dynamicsChart.update();
  if (typeof structuralChart !== 'undefined') structuralChart.update();
  if (typeof flowChart !== 'undefined') flowChart.update();
}, 100);"""
    
    loop_new = """// Decoupled render loop with auto-scrolling window
window.isAutoScrolling = true;

setInterval(() => {
  if (window.isAutoScrolling && steps.length > 0) {
    const WINDOW_SIZE = 150; // Default zoom level: last 150 steps
    const currentMaxIndex = steps.length - 1;
    const currentMinIndex = Math.max(0, currentMaxIndex - WINDOW_SIZE);
    
    const minLabel = steps[currentMinIndex];
    const maxLabel = steps[currentMaxIndex];

    [vitalsChart, dynamicsChart, structuralChart, flowChart].forEach(c => {
      if (typeof c !== 'undefined') {
        c.options.scales.x.min = minLabel;
        c.options.scales.x.max = maxLabel;
      }
    });
  }

  if (typeof vitalsChart !== 'undefined') vitalsChart.update('none'); // 'none' to skip internal animation for manual bounds
  if (typeof dynamicsChart !== 'undefined') dynamicsChart.update('none');
  if (typeof structuralChart !== 'undefined') structuralChart.update('none');
  if (typeof flowChart !== 'undefined') flowChart.update('none');
}, 100);"""
    content = content.replace(loop_old, loop_new)

    with open(filepath, 'w') as f:
        f.write(content)
        print("Patched auto-scrolling logic")

patch_file('media/demo_dashboard.html')
