import re

def patch_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # Find the chart-header divs and inject the zoom hint
    # Current header format from previous patch:
    # <div class="chart-header" style="display:flex; justify-content:space-between; align-items:center;"><div class="chart-title">TITLE</div><button class="btn-theme" style="padding: 4px 8px; font-size: 12px; display:flex; align-items:center; border: 1px solid var(--panel-border);" onclick="downloadChart('ID')" title="Download Graph"><svg...>Download</button></div>

    # We want to wrap the title in a flex container with the hint.
    
    # We will use regex to find and replace.
    pattern = r'(<div class="chart-header"[^>]*>)(<div class="chart-title">)(.*?)(</div>)'
    
    hint_html = r'\2\3\4 <div style="font-size: 11px; color: var(--text-secondary); background: var(--bg-color); padding: 2px 6px; border-radius: 4px; display: flex; align-items: center; border: 1px solid var(--panel-border); margin-left: 12px; user-select: none;"><svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none" style="margin-right:4px;"><path d="M5 9l-3 3 3 3M9 5l3-3 3 3M19 9l3 3-3 3M9 19l3 3 3-3M2 12h20M12 2v20"></path></svg>Drag to pan &middot; Scroll to zoom</div>'
    
    # But wait, `<div class="chart-title">` is a block. We need to put both in a flex container.
    replacement = r'\1<div style="display:flex; align-items:center;">\2\3\4 <div style="font-size: 11px; color: var(--text-secondary); background: var(--bg-color); padding: 3px 8px; border-radius: 6px; display: flex; align-items: center; border: 1px solid var(--panel-border); margin-left: 12px; user-select: none; opacity: 0.8;"><svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none" style="margin-right:6px;"><path d="M5 9l-3 3 3 3M9 5l3-3 3 3M19 9l3 3-3 3M9 19l3 3 3-3M2 12h20M12 2v20"></path></svg>Drag to pan &middot; Scroll to zoom</div></div>'

    new_content = re.sub(pattern, replacement, content)
    
    # Also add a "Resume Auto-Scroll" button globally in the metrics header? 
    # Or let's just do the hint first.
    
    with open(filepath, 'w') as f:
        f.write(new_content)
        print("Patched zoom hints")

patch_file('media/demo_dashboard.html')
