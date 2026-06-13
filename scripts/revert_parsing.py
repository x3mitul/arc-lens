def patch_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()

    content = content.replace("parsing: false,", "")
    content = content.replace("normalized: true,", "")

    with open(filepath, 'w') as f:
        f.write(content)

patch_file('media/demo_dashboard.html')
