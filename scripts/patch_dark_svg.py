import os

SUN_SVG = '<svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line></svg>'
MOON_SVG = '<svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>'

def patch_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # 1. Update Dark Mode (:root)
    content = content.replace("""
:root {
  --bg-color: #000000;
  --panel-bg: #0a0a0a;
  --panel-border: #222222;
  --text-primary: #ededed;
  --text-secondary: #888888;
  --header-bg: rgba(0, 0, 0, 0.8);
  --panel-shadow: none;
}
""", """
:root {
  --bg-color: #09090b;
  --panel-bg: #18181b;
  --panel-border: #27272a;
  --text-primary: #f4f4f5;
  --text-secondary: #a1a1aa;
  --header-bg: rgba(9, 9, 11, 0.85);
  --panel-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}
""")

    # 2. Update HTML icon
    content = content.replace(
        '<button id="theme-toggle" class="btn-theme" onclick="toggleTheme()" title="Toggle Light/Dark Mode">☀️</button>',
        f'<button id="theme-toggle" class="btn-theme" onclick="toggleTheme()" title="Toggle Light/Dark Mode" style="display:flex;align-items:center;justify-content:center;width:28px;height:28px;padding:0;">{SUN_SVG}</button>'
    )

    # 3. Update Javascript toggleTheme icon swapping
    content = content.replace(
        "document.getElementById('theme-toggle').textContent = isLight ? '☀️' : '🌙';",
        f"document.getElementById('theme-toggle').innerHTML = isLight ? '{SUN_SVG}' : '{MOON_SVG}';"
    )

    with open(filepath, 'w') as f:
        f.write(content)
        print(f"Patched dark mode & icons in {filepath}")

patch_file('media/dashboard.html')
patch_file('media/demo_dashboard.html')
