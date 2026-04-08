# CLI-Anything ChromaDB

CLI harness for ChromaDB vector database using the cli-anything methodology.

## Installation

```bash
cd agent-harness
pip install -e .
```

## Usage

### Interactive REPL (default)
```bash
cli-anything-chromadb
```

### Direct commands
```bash
# Server
cli-anything-chromadb server heartbeat
cli-anything-chromadb server version

# Collections
cli-anything-chromadb collection list
cli-anything-chromadb collection info hub_knowledge
cli-anything-chromadb collection create --name test_collection
cli-anything-chromadb collection delete --name test_collection

# Documents
cli-anything-chromadb document count --collection hub_knowledge
cli-anything-chromadb document get --collection hub_knowledge --limit 5
cli-anything-chromadb document add --collection hub_knowledge --id doc1 --document "Hello world"
cli-anything-chromadb document delete --collection hub_knowledge --id doc1

# Semantic search
cli-anything-chromadb query search --collection hub_knowledge --text "how does the pipeline work" --n-results 3
```

### JSON output
Add `--json` before any subcommand:
```bash
cli-anything-chromadb --json collection list
cli-anything-chromadb --json query search --collection hub_knowledge --text "pipeline" --n-results 3
```

## Configuration

- Default server: `http://localhost:8000`
- Override with `--host`: `cli-anything-chromadb --host http://other:8000 server heartbeat`
- Tenant: `default_tenant`, Database: `default_database`
