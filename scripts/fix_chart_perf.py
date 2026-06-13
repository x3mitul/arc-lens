import re

def patch_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # 1. Disable animations for high-performance rendering
    content = content.replace("animation: {\n        duration: 600,\n        easing: 'easeOutQuart'\n      }", "animation: false")
    
    # 2. Add performance parsing options to commonOptions
    content = content.replace("responsive: true,", "responsive: true,\n      animation: false,\n      parsing: false,\n      normalized: true,")

    # 3. Decouple chart.update() from data ingestion
    # Find handleMessage where it updates charts:
    content = content.replace("""
      lossChart.update();
      gradChart.update();
      lrChart.update();
      memChart.update();
""", "")

    # Now add a setInterval just for chart updates
    if "setInterval(() => { lossChart.update();" not in content:
        # We need to inject the render loop at the bottom
        # Let's add it right before `</script>` at the end of the file
        content = content.replace("</script>\n\n</body>", """
// Decoupled render loop to prevent lag
setInterval(() => {
  lossChart.update();
  gradChart.update();
  lrChart.update();
  memChart.update();
}, 50); // render at ~20 FPS instead of 200 FPS
</script>\n\n</body>""")

    with open(filepath, 'w') as f:
        f.write(content)
        print(f"Patched performance in {filepath}")

patch_file('media/demo_dashboard.html')
# don't patch dashboard.html with this exact script because dashboard.html might want animations since it's real time.
# But actually, normalized: true and parsing: false is good for dashboard.html too.
