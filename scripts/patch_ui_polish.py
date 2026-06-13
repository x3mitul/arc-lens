import re

def patch_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    # 1. Enhance borders in Light Mode
    # Replace the faint border with a crisper border
    content = content.replace("--panel-border: rgba(0, 0, 0, 0.05);", "--panel-border: #e4e4e7;")
    # Soften the extreme shadow to match the crisper border better
    content = content.replace("--panel-shadow: 0 1px 2px rgba(0, 0, 0, 0.04), 0 8px 16px -4px rgba(0, 0, 0, 0.06);", "--panel-shadow: 0 1px 3px rgba(0,0,0,0.05), 0 4px 6px -2px rgba(0,0,0,0.03);")

    # 2. Change Download buttons to Icon Only
    # The current download button regex:
    pattern_btn = r'<button class="btn-theme" style="padding: 4px 8px; font-size: 12px; display:flex; align-items:center; border: 1px solid var\(--panel-border\);" onclick="downloadChart\(\'([a-zA-Z0-9_]+)\'\)" title="Download Graph"><svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" style="margin-right:4px"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>Download</button>'
    
    new_btn = r'<button class="btn-theme" style="padding: 6px; display:flex; align-items:center; justify-content:center; border: 1px solid var(--panel-border); border-radius: 6px; color: var(--text-secondary); transition: all 0.2s;" onclick="downloadChart(\'\1\')" title="Download Graph as PNG" onmouseover="this.style.color=\'var(--text-primary)\'; this.style.borderColor=\'var(--text-secondary)\'" onmouseout="this.style.color=\'var(--text-secondary)\'; this.style.borderColor=\'var(--panel-border)\'"><svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg></button>'
    
    content = re.sub(pattern_btn, new_btn, content)

    with open(filepath, 'w') as f:
        f.write(content)
        print(f"Patched UI in {filepath}")

patch_file('media/demo_dashboard.html')
