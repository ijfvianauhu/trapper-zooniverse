import subprocess

def extract_translations():
    """
    Genera el archivo POT a partir de las cadenas marcadas en el proyecto.
    """
    subprocess.run([
        "pybabel",
        "extract",
        "-F", "babel.cfg",
        "-o", "trapper_zooniverse/locales/messages.pot",
        "."
    ], check=True)
    print("Archivo POT generado en locales/messages.pot")
