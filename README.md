# Localización argentina para Odoo Community 19

## Tests y coverage

Los tests de `l10n_ar_afipws` usan `TransactionCase` de Odoo y mocks de los
clientes AFIP (WSAA y padrón): no requieren credenciales ni consultan AFIP.
Cubren autenticación, caché del ticket, conexiones, certificados, configuración,
datos del padrón y los asistentes de carga y actualización. La suite de
`l10n_ar_afipws` tiene 30 tests y alcanza el 100 % de líneas y ramas del código
incluido en la medición.

Se necesita Docker con Docker Compose v2. No hace falta instalar Odoo, PostgreSQL
ni dependencias Python en el host.

```bash
./scripts/test-module.sh l10n_ar_afipws
```

El script construye la imagen de tests (`Dockerfile`, basada en `odoo:19`), levanta
PostgreSQL 17, espera a que esté disponible y ejecuta los tests sin datos demo. Al finalizar baja
Docker Compose, incluso si fallan los tests o se interrumpe la ejecución. Cada
invocación usa un proyecto aislado con una base temporal en memoria; los datos de
PostgreSQL se descartan al bajar el entorno. No se publican puertos en el host.

El primer argumento selecciona el módulo; los siguientes se pasan a Odoo:

```bash
./scripts/test-module.sh l10n_ar_afipws --log-level=test
```

El script limita los tests al módulo seleccionado y ejecuta Odoo sin workers.
Podés usarlo para cualquier módulo de este repositorio que tenga tests. La base
se llama `test_<modulo>`; podés cambiar el nombre con `TEST_DB`.

En cada ejecución se reemplaza la medición anterior del módulo y se generan:

- Resumen con líneas faltantes en consola.
- Reporte HTML: `coverage/<modulo>/html/index.html`.
- Reporte XML para CI: `coverage/<modulo>/coverage.xml`.

Se mide coverage de líneas y ramas del módulo, excluyendo tests, manifiesto y archivos `__init__.py`.
Incluye código ejecutado durante la carga/instalación de Odoo. También se intentan
generar los reportes si fallan los tests, conservando el código de error de Odoo.
`COVERAGE_DIR` permite cambiar la carpeta raíz de reportes del host (por defecto
`coverage/`); cada módulo tiene su propia subcarpeta. Los archivos se crean con
el UID/GID del usuario que ejecuta el script.

Para usar un entorno Odoo local existente, `scripts/run-module-tests.sh` conserva
la ejecución directa con coverage. Requiere instalar `requirements-test.txt` en
ese entorno y configurar `ODOO_BIN`, `PYTHON_BIN` y las opciones de conexión:

```bash
ODOO_BIN=/ruta/odoo-bin PYTHON_BIN=/ruta/venv/bin/python \
  ./scripts/run-module-tests.sh l10n_ar_afipws --config=/ruta/odoo.conf
```

En modo local la base no se elimina: usá una base exclusiva de tests. El script
Docker utiliza este mismo ejecutor dentro del contenedor.
