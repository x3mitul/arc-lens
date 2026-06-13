import os

def patch_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Update :root
    content = content.replace("""
:root {
  --bg-color: #000000;
  --panel-bg: #0a0a0a;
  --panel-border: #222222;
  --text-primary: #ededed;
  --text-secondary: #888888;
  --header-bg: rgba(0, 0, 0, 0.8);
}
""", """
:root {
  --bg-color: #000000;
  --panel-bg: #0a0a0a;
  --panel-border: #222222;
  --text-primary: #ededed;
  --text-secondary: #888888;
  --header-bg: rgba(0, 0, 0, 0.8);
  --panel-shadow: none;
}
""")

    # Update [data-theme="light"]
    content = content.replace("""
[data-theme="light"] {
  --bg-color: #f7f7f7;
  --panel-bg: #ffffff;
  --panel-border: #e0e0e0;
  --text-primary: #111111;
  --text-secondary: #666666;
  --header-bg: rgba(255, 255, 255, 0.85);
}
""", """
[data-theme="light"] {
  --bg-color: #f9fafb; /* Cooler, modern off-white */
  --panel-bg: #ffffff;
  --panel-border: rgba(0, 0, 0, 0.08); /* More subtle border */
  --text-primary: #111827; /* Rich dark slate for premium contrast */
  --text-secondary: #6b7280;
  --header-bg: rgba(255, 255, 255, 0.85);
  --panel-shadow: 0 4px 12px rgba(0, 0, 0, 0.04), 0 1px 3px rgba(0, 0, 0, 0.02);
}
""")

    # Add shadow transition
    content = content.replace("""
body, .metric-card, .chart-card, header, .recovery-log-card, .btn-stop, .file-badge, .status-badge, .log-msg, .log-time, .btn-theme {
  transition: background-color 0.4s ease, border-color 0.4s ease, color 0.4s ease;
}
""", """
body, .metric-card, .chart-card, header, .recovery-log-card, .btn-stop, .file-badge, .status-badge, .log-msg, .log-time, .btn-theme {
  transition: background-color 0.4s ease, border-color 0.4s ease, color 0.4s ease, box-shadow 0.4s ease;
}
""")

    # Add shadow to cards
    if "box-shadow: var(--panel-shadow);" not in content:
        content = content.replace("""
.metric-card {
  background: var(--panel-bg);
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  padding: 20px;
  display: flex;
  flex-direction: column;
}
""", """
.metric-card {
  background: var(--panel-bg);
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  padding: 20px;
  display: flex;
  flex-direction: column;
  box-shadow: var(--panel-shadow);
}
""")
        content = content.replace("""
.chart-card {
  background: var(--panel-bg);
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  padding: 24px;
  position: relative;
}
""", """
.chart-card {
  background: var(--panel-bg);
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  padding: 24px;
  position: relative;
  box-shadow: var(--panel-shadow);
}
""")
        content = content.replace("""
.recovery-log-card {
  background: var(--panel-bg);
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  padding: 24px;
}
""", """
.recovery-log-card {
  background: var(--panel-bg);
  border: 1px solid var(--panel-border);
  border-radius: 8px;
  padding: 24px;
  box-shadow: var(--panel-shadow);
}
""")

    with open(filepath, 'w') as f:
        f.write(content)
        print(f"Beautified Light Mode for {filepath}")

patch_file('media/dashboard.html')
patch_file('media/demo_dashboard.html')
