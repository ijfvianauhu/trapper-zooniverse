#!/usr/bin/env bash
set -euo pipefail

# Directory of this script
script_dir="$(cd "$(dirname "$0")" && pwd)"

# Base directory for locales (relative to script location)
locales_base="${script_dir}/../trapper_browser/locales"

# Helper: if file exists, ask before overwriting and make a backup
backup_and_overwrite() {
    local outfile="$1"

    if [[ -f "$outfile" ]]; then
        echo "⚠️  File '$outfile' already exists."
        read -p "Do you want to overwrite it? (y/N): " resp
        if [[ "$resp" =~ ^[yY]$ ]]; then
            local timestamp
            timestamp=$(date +"%Y%m%d_%H%M%S")
            local backup="${outfile}.${timestamp}.bak"
            cp "$outfile" "$backup"
            echo "Backup created at: $backup"
        else
            echo "⏭️  Skipping generation of '$outfile'."
            return 1
        fi
    fi
    return 0
}

# Generate POT file
pot_file="${locales_base}/messages.pot"
if backup_and_overwrite "$pot_file"; then
    pygettext.py -d messages -o "$pot_file" "${script_dir}/../trapper-browser/"*.py
fi

# Languages to process
locales=(es en)

# Iterate over languages
for lang in "${locales[@]}"; do
    po_file="${locales_base}/${lang}/LC_MESSAGES/messages.po"
    mo_file="${locales_base}/${lang}/LC_MESSAGES/messages.mo"

    mkdir -p "$(dirname "$po_file")"

    if backup_and_overwrite "$po_file"; then
        msginit --no-translator --locale="$lang" --input="$pot_file" --output="$po_file"
    fi

    if backup_and_overwrite "$mo_file"; then
        msgfmt "$po_file" -o "$mo_file"
    fi
done
