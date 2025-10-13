import subprocess
import os

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

def init_translation(lang="en"):
    """
    Genera el archivo PO para el idioma especificado a partir del POT.
    Si el PO ya existe, actualiza su contenido.
    """
    po_dir = f"trapper_zooniverse/locales/{lang}/LC_MESSAGES"
    po_file = os.path.join(po_dir, "messages.po")

    # Crear carpeta si no existe
    os.makedirs(po_dir, exist_ok=True)

    if not os.path.exists(po_file):
        # Inicializar archivo PO si no existe
        subprocess.run([
            "pybabel",
            "init",
            "-i", "trapper_zooniverse/locales/messages.pot",
            "-d", f"trapper_zooniverse/locales",
            "-l", lang
        ], check=True)
        print(f"Archivo PO creado para idioma {lang} en {po_file}")
    else:
        # Actualizar PO existente
        subprocess.run([
            "pybabel",
            "update",
            "-i", "trapper_zooniverse/locales/messages.pot",
            "-d", f"trapper_zooniverse/locales",
            "-l", lang
        ], check=True)
        print(f"Archivo PO actualizado para idioma {lang} en {po_file}")

