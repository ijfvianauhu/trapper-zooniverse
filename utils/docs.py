import subprocess

def build_docs():
    subprocess.run([
        "pdoc",
        "trapper_zooniverse",
        "--output-dir", "docs",
        "--logo", "../img/wildIntel_logo.webp",
        "--favicon", "docs/favicon.ico",
        "--template-dir", "templates",
        "--footer-text", "© 2025 WildINTEL"
    ])