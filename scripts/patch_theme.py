import os

def patch_file(filepath, is_demo=False):
    with open(filepath, 'r') as f:
        content = f.read()

    # 1. CSS Variables
    content = content.replace("""
:root {
  --bg-color: #000000;
  --panel-bg: #0a0a0a;
  --panel-border: #222222;
  --text-primary: #ededed;
  --text-secondary: #888888;
""", """
:root {
  --bg-color: #000000;
  --panel-bg: #0a0a0a;
  --panel-border: #222222;
  --text-primary: #ededed;
  --text-secondary: #888888;
  --header-bg: rgba(0, 0, 0, 0.8);
}

[data-theme="light"] {
  --bg-color: #f7f7f7;
  --panel-bg: #ffffff;
  --panel-border: #e0e0e0;
  --text-primary: #111111;
  --text-secondary: #666666;
  --header-bg: rgba(255, 255, 255, 0.85);
}

body, .metric-card, .chart-card, header, .recovery-log-card, .btn-stop, .file-badge, .status-badge, .log-msg, .log-time, .btn-theme {
  transition: background-color 0.4s ease, border-color 0.4s ease, color 0.4s ease;
}
""")

    # 2. Header background
    content = content.replace("background: rgba(0, 0, 0, 0.8);", "background: var(--header-bg);")

    # 3. Logo text color
    content = content.replace("color: #ffffff;", "color: var(--text-primary);")

    # 4. Add btn-theme styles and log animation
    content = content.replace("""
.btn-stop:hover {
  opacity: 0.8;
}
""", """
.btn-stop:hover {
  opacity: 0.8;
}

.btn-theme {
  background: transparent;
  border: 1px solid var(--panel-border);
  color: var(--text-primary);
  border-radius: 4px;
  padding: 4px 8px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s;
}
.btn-theme:hover { background: var(--panel-border); }

/* Smooth Log Entries */
.recovery-log-item {
  animation: slideIn 0.3s cubic-bezier(0.2, 0.8, 0.2, 1);
}
@keyframes slideIn {
  from { opacity: 0; transform: translateX(-10px); }
  to { opacity: 1; transform: translateX(0); }
}
""")

    # 5. HTML Header
    if is_demo:
        content = content.replace("""
  <div class="header-controls">
    <span class="file-badge" id="file-name">Not running</span>
    <div class="status-badge status-idle" id="global-status">IDLE</div>
    <button class="btn-stop" onclick="alert('Demo Mode: Cannot stop active simulation.')">Stop Process</button>
  </div>
""", """
  <div class="header-controls">
    <button id="theme-toggle" class="btn-theme" onclick="toggleTheme()" title="Toggle Light/Dark Mode">☀️</button>
    <span class="file-badge" id="file-name">Not running</span>
    <div class="status-badge status-idle" id="global-status">IDLE</div>
    <button class="btn-stop" onclick="alert('Demo Mode: Cannot stop active simulation.')">Stop Process</button>
  </div>
""")
    else:
        content = content.replace("""
  <div class="header-controls">
    <span class="file-badge" id="file-name">Not running</span>
    <div class="status-badge status-idle" id="global-status">IDLE</div>
    <button class="btn-stop" onclick="stopTraining()">Stop Process</button>
  </div>
""", """
  <div class="header-controls">
    <button id="theme-toggle" class="btn-theme" onclick="toggleTheme()" title="Toggle Light/Dark Mode">☀️</button>
    <span class="file-badge" id="file-name">Not running</span>
    <div class="status-badge status-idle" id="global-status">IDLE</div>
    <button class="btn-stop" onclick="stopTraining()">Stop Process</button>
  </div>
""")

    # 6. Chart JS additions
    content = content.replace("""
// Clean global chart defaults for premium aesthetic
Chart.defaults.color = '#888888';
""", """
// Theme Toggle Logic
function toggleTheme() {
  const body = document.body;
  const isLight = body.getAttribute('data-theme') === 'light';
  body.setAttribute('data-theme', isLight ? 'dark' : 'light');
  document.getElementById('theme-toggle').textContent = isLight ? '☀️' : '🌙';
  
  const newIsLight = !isLight;
  Chart.defaults.color = newIsLight ? '#666666' : '#888888';
  Chart.defaults.plugins.tooltip.backgroundColor = newIsLight ? 'rgba(255, 255, 255, 0.95)' : 'rgba(0, 0, 0, 0.9)';
  Chart.defaults.plugins.tooltip.titleColor = newIsLight ? '#000' : '#fff';
  Chart.defaults.plugins.tooltip.bodyColor = newIsLight ? '#333' : '#ccc';
  Chart.defaults.plugins.tooltip.borderColor = newIsLight ? '#e0e0e0' : '#333';
  
  const gridColor = newIsLight ? 'rgba(0, 0, 0, 0.05)' : '#1a1a1a';
  [vitalsChart, dynamicsChart, structuralChart, flowChart].forEach(c => {
    if (c.options.scales.y) c.options.scales.y.grid.color = gridColor;
    if (c.options.scales['y-lr']) c.options.scales['y-lr'].grid.color = gridColor;
    if (c.options.scales['y-alt']) c.options.scales['y-alt'].grid.color = gridColor;
    c.update();
  });
}

// Clean global chart defaults for premium aesthetic
Chart.defaults.color = '#888888';
Chart.defaults.animation = { duration: 600, easing: 'easeOutQuart' };
""")

    # 7. Make lines smoother (tension 0.3 -> 0.4)
    content = content.replace("tension: 0.3", "tension: 0.4")

    with open(filepath, 'w') as f:
        f.write(content)
        print(f"Patched {filepath}")

patch_file('media/dashboard.html', is_demo=False)
patch_file('media/demo_dashboard.html', is_demo=True)

