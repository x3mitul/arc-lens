import re

def patch_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # 1. Ultra-Classy Light Mode
    content = content.replace("""[data-theme="light"] {
  --bg-color: #f9fafb; /* Cooler, modern off-white */
  --panel-bg: #ffffff;
  --panel-border: rgba(0, 0, 0, 0.08); /* More subtle border */
  --text-primary: #111827; /* Rich dark slate for premium contrast */
  --text-secondary: #6b7280;
  --header-bg: rgba(255, 255, 255, 0.85);
  --panel-shadow: 0 4px 12px rgba(0, 0, 0, 0.04), 0 1px 3px rgba(0, 0, 0, 0.02);
}""", """[data-theme="light"] {
  --bg-color: #f7f7f8; /* Warm, classy alabaster off-white */
  --panel-bg: #ffffff;
  --panel-border: rgba(0, 0, 0, 0.05); /* Extremely faint elegant border */
  --text-primary: #09090b; /* Deep ink for pristine readability */
  --text-secondary: #71717a; /* Muted, modern zinc */
  --header-bg: rgba(255, 255, 255, 0.90);
  --panel-shadow: 0 1px 2px rgba(0, 0, 0, 0.04), 0 8px 16px -4px rgba(0, 0, 0, 0.06); /* Rich, diffuse depth shadow */
}""")

    # 2. Performance: tension: 0
    content = content.replace("tension: 0.4,", "tension: 0, /* Disabled bezier curves for maximum performance */")

    # 3. Performance: render loop interval
    content = content.replace("}, 50); // render at ~20 FPS instead of 200 FPS", "}, 100); // render at 10 FPS for buttery performance without stuttering")

    with open(filepath, 'w') as f:
        f.write(content)
        print(f"Patched performance and light mode in {filepath}")

patch_file('media/demo_dashboard.html')
patch_file('media/dashboard.html')
