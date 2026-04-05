# cli-anything-n8n

[![PyPI](https://img.shields.io/pypi/v/cli-anything-n8n.svg)](https://pypi.org/project/cli-anything-n8n/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![CLI-Anything](https://img.shields.io/badge/CLI--Anything-harness-orange.svg)](https://github.com/HKUDS/CLI-Anything)
[![n8n API v1.1.1](https://img.shields.io/badge/n8n-API%20v1.1.1-EA4B71.svg)](https://docs.n8n.io/api/api-reference/)

> [Leer en Español](#spanish) | [Read in English](#english)

---

<a id="english"></a>

## English

Control your [n8n](https://n8n.io) instance from the terminal. List workflows, check executions, manage tags — all without opening the browser.

Built with the [CLI-Anything](https://github.com/HKUDS/CLI-Anything) pattern, so AI agents can use it too.

### Try it now (2 minutes)

```bash
# 1. Install
pip install cli-anything-n8n

# 2. Connect to your n8n
export N8N_BASE_URL=https://your-n8n-instance.com
export N8N_API_KEY=your-api-key

# 3. Try it!
cli-anything-n8n workflow list
```

> **Where do I get my API key?** In n8n, go to Settings > API > Create API Key.

### What can I do?

```bash
# List your workflows
cli-anything-n8n workflow list

# See only active workflows
cli-anything-n8n workflow list --active

# Check failed executions
cli-anything-n8n execution list --status error

# Get details of a specific workflow
cli-anything-n8n workflow get ABC123

# Create a tag
cli-anything-n8n tag create "production"

# Get JSON output (for scripts or AI agents)
cli-anything-n8n --json workflow list

# Interactive mode — just type commands
cli-anything-n8n
n8n> workflow list
n8n> tag list
n8n> exit
```

### All commands

| Group | Commands | What it does |
|-------|----------|--------------|
| **workflow** | list, get, create, update, delete, activate, deactivate, tags, set-tags, transfer | Manage your workflows |
| **execution** | list, get, delete, retry | Check and retry executions |
| **credential** | create, delete, schema, transfer | Manage credentials |
| **variable** | list, create, update, delete | Manage environment variables |
| **tag** | list, get, create, update, delete | Organize with tags |
| **config** | show, set | Save your connection settings |

### Save your connection (so you don't type it every time)

```bash
cli-anything-n8n config set base_url https://your-n8n-instance.com
cli-anything-n8n config set api_key your-api-key

# Now just use it directly
cli-anything-n8n workflow list
```

### Configuration options

| Method | Priority | Example |
|--------|----------|---------|
| CLI flags | 1 (highest) | `--url https://... --api-key xxx` |
| Environment variables | 2 | `N8N_BASE_URL`, `N8N_API_KEY` |
| Config file | 3 | `cli-anything-n8n config set ...` |

Extra env vars: `N8N_TIMEOUT` (default: 30 seconds)

### For AI agents and scripts

```bash
# Always use --json for machine-readable output
cli-anything-n8n --json workflow list

# Pass complex data from files
cli-anything-n8n workflow create @my-workflow.json

# Check exit codes
cli-anything-n8n workflow get ABC123 && echo "OK" || echo "FAILED"
```

### n8n compatibility

Verified against **n8n 2.43.0** (Public API v1.1.1). Works with any n8n >= 1.0.0.

> **Note**: Some n8n features (Data Tables, credential listing, execution stop) are not available through the public API. This CLI only exposes verified, working endpoints.

### Development

```bash
git clone https://github.com/webcomunicasolutions/cli-n8n.git
cd cli-n8n
pip install -e .

# Run tests (no n8n needed)
pip install pytest
pytest cli_anything/n8n/tests/test_core.py -v

# Run E2E tests (needs a running n8n)
export N8N_BASE_URL=https://your-n8n.com
export N8N_API_KEY=your-key
pytest cli_anything/n8n/tests/test_full_e2e.py -v
```

### Project structure

```
cli_anything/n8n/
├── n8n_cli.py          # CLI + interactive REPL
├── core/               # API wrappers (one file per resource)
│   ├── workflows.py
│   ├── executions.py
│   ├── credentials.py
│   ├── variables.py
│   ├── tags.py
│   └── project.py      # Config management
├── utils/
│   ├── n8n_backend.py  # HTTP client
│   └── repl_skin.py    # Terminal UI
└── tests/
    ├── test_core.py    # Unit tests (mocked)
    └── test_full_e2e.py # E2E tests (live n8n)
```

### License

MIT - Juan Jose Sanchez Bernal / [Webcomunica Soluciones Informaticas](https://webcomunica.solutions)

---

<a id="spanish"></a>

## Español

Controla tu instancia de [n8n](https://n8n.io) desde la terminal. Lista workflows, revisa ejecuciones, gestiona tags — todo sin abrir el navegador.

Construido con el patron [CLI-Anything](https://github.com/HKUDS/CLI-Anything), para que agentes IA tambien puedan usarlo.

### Pruebalo ahora (2 minutos)

```bash
# 1. Instalar
pip install cli-anything-n8n

# 2. Conectar a tu n8n
export N8N_BASE_URL=https://tu-instancia-n8n.com
export N8N_API_KEY=tu-api-key

# 3. Probar!
cli-anything-n8n workflow list
```

> **Donde consigo mi API key?** En n8n, ve a Settings > API > Create API Key.

### Que puedo hacer?

```bash
# Listar workflows
cli-anything-n8n workflow list

# Solo los activos
cli-anything-n8n workflow list --active

# Ver ejecuciones fallidas
cli-anything-n8n execution list --status error

# Detalle de un workflow
cli-anything-n8n workflow get ABC123

# Crear un tag
cli-anything-n8n tag create "produccion"

# Salida JSON (para scripts o agentes IA)
cli-anything-n8n --json workflow list

# Modo interactivo
cli-anything-n8n
n8n> workflow list
n8n> tag list
n8n> exit
```

### Todos los comandos

| Grupo | Comandos | Que hace |
|-------|----------|----------|
| **workflow** | list, get, create, update, delete, activate, deactivate, tags, set-tags, transfer | Gestionar workflows |
| **execution** | list, get, delete, retry | Revisar y reintentar ejecuciones |
| **credential** | create, delete, schema, transfer | Gestionar credenciales |
| **variable** | list, create, update, delete | Gestionar variables de entorno |
| **tag** | list, get, create, update, delete | Organizar con tags |
| **config** | show, set | Guardar configuracion de conexion |

### Guardar conexion (para no escribirla cada vez)

```bash
cli-anything-n8n config set base_url https://tu-instancia-n8n.com
cli-anything-n8n config set api_key tu-api-key

# Ahora usalo directamente
cli-anything-n8n workflow list
```

### Compatibilidad con n8n

Verificado contra **n8n 2.43.0** (API publica v1.1.1). Funciona con cualquier n8n >= 1.0.0.

> **Nota**: Algunas funcionalidades de n8n (Data Tables, listar credenciales, parar ejecuciones) no estan disponibles via la API publica. Este CLI solo expone endpoints verificados y funcionales.

### Desarrollo

```bash
git clone https://github.com/webcomunicasolutions/cli-n8n.git
cd cli-n8n
pip install -e .
pip install pytest
pytest cli_anything/n8n/tests/test_core.py -v
```

### Licencia

MIT - Juan Jose Sanchez Bernal / [Webcomunica Soluciones Informaticas](https://webcomunica.solutions)
