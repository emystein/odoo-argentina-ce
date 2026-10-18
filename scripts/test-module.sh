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
command -v docker >/dev/null || { echo "Se requiere Docker con Docker Compose v2." >&2; exit 2; }
# Proyecto exclusivo de esta ejecución: no comparte bases ni contenedores.
project="afipws-tests-$(id -u)-$$"
export COVERAGE_DIR="${COVERAGE_DIR:-$repo_root/coverage}"
mkdir -p "$COVERAGE_DIR"
COVERAGE_DIR="$(cd -- "$COVERAGE_DIR" && pwd)"
export COVERAGE_DIR
compose=(docker compose --project-name "$project" --file "$repo_root/docker-compose.yml")
cleanup() {
    local status=$?
    trap - EXIT
    "${compose[@]}" down --volumes --remove-orphans || {
        echo "No se pudo limpiar el entorno de tests $project." >&2
        if [[ "$status" -eq 0 ]]; then status=1; fi
    }
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
"${compose[@]}" build tests
"${compose[@]}" up --detach --wait db
"${compose[@]}" run --rm --no-deps --user "$(id -u):$(id -g)" \
    -e "COVERAGE_DIR=/coverage/$module" tests "$module" \
    --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo_test \
    --data-dir=/tmp/odoo-test-data --without-demo=True \
    --addons-path=/usr/lib/python3/dist-packages/odoo/addons,/mnt/extra-addons \
    "$@"
echo "Coverage: $COVERAGE_DIR/$module/html/index.html"
