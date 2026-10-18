#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || ! "$1" =~ ^[a-zA-Z_][a-zA-Z0-9_]*$ ]]; then
    echo "Uso: $0 MODULO [opciones de Odoo...]" >&2
    exit 2
fi
module="$1"
shift
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ ! -f "$repo_root/$module/__manifest__.py" ]]; then
    echo "No existe el módulo: $module" >&2
    exit 2
fi
python_bin="${PYTHON_BIN:-python3}"
odoo_bin="${ODOO_BIN:-odoo}"
if [[ "$odoo_bin" != */* ]]; then
    odoo_bin="$(command -v "$odoo_bin")" || { echo "Configurá ODOO_BIN con la ruta a odoo-bin." >&2; exit 2; }
fi
report_dir="${COVERAGE_DIR:-$repo_root/coverage/$module}"
mkdir -p "$report_dir"
export COVERAGE_FILE="$report_dir/.coverage"
"$python_bin" -m coverage erase
status=0
"$python_bin" -m coverage run --branch --source="$repo_root/$module" \
    --omit='*/tests/*,*/__manifest__.py,*/__init__.py' "$odoo_bin" \
    "$@" -d "${TEST_DB:-test_$module}" -i "$module" \
    --test-enable --test-tags "/$module" --stop-after-init --workers=0 --max-cron-threads=0 \
    --http-port="${TEST_HTTP_PORT:-8079}" || status=$?
# Emitir los reportes también cuando falla un test, conservando el código de salida.
report_status=0
"$python_bin" -m coverage report -m || report_status=$?
"$python_bin" -m coverage html -d "$report_dir/html" || report_status=$?
"$python_bin" -m coverage xml -o "$report_dir/coverage.xml" || report_status=$?
echo "Coverage: $report_dir/html/index.html"
if [[ "$status" -ne 0 ]]; then
    exit "$status"
fi
exit "$report_status"
