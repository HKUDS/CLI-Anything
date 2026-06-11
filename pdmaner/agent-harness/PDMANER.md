# PDManer — Agent Harness Analysis

## Software Summary

PDManer (元数建模) is an open-source desktop database modeling tool — the Chinese
PowerDesigner alternative. Built with Electron + React + Redux + Java (jar backend).

- **Version**: 4.9.4
- **Repo**: https://gitee.com/robergroup/pdmaner
- **Status**: Archived, superseded by PDMaas
- **Native format**: JSON project files (`.chnr.json` extension)

## Phase 1: Codebase Analysis

### 1. Backend Engine

PDManer has **two backends**:

| Component | Tech | Role |
|-----------|------|------|
| Project data | JSON file (`.chnr.json`) | Full project state serialization |
| Java operations | `pdmaner-java.jar` | DB reverse engineering, code generation, connection testing |

No headless CLI exists. The CLI harness will:
- **Manipulate JSON directly** for project/entity/view/diagram/dict/domain CRUD
- **Call Java jar via subprocess** for DB operations (reverse parse, connect test, code-gen)

### 2. Data Model

The `.chnr.json` project file structure:

```json
{
  "name": "project-name",
  "describe": "",
  "avatar": "",
  "version": "4.9.4",
  "createdTime": "2024-01-19 16:23:16",
  "updatedTime": "2024-01-19 16:23:16",
  "dbConns": [],
  "profile": {
    "default": { "db": "<uuid>", "dbConn": "", "entityInitFields": [...] },
    "dataTypeSupports": [{ "defKey": "MySQL", "id": "<uuid>", ... }],
    "codeTemplates": [...],
    "uiHint": [],
    "headers": [...],
    "namingRules": { ... }
  },
  "entities": [{
    "id": "<uuid>", "defKey": "", "defName": "", "comment": "",
    "type": "P", "fields": [...], "indexes": [...], "correlations": [...],
    "headers": [...], "properties": {}, "sysProps": { "nameTemplate": "{defKey}[{defName}]" },
    "notes": {}, "env": { "base": { "nameSpace": "", "codeRoot": "" } }
  }],
  "views": [...],
  "diagrams": [{ "id": "<uuid>", "defKey": "", "defName": "",
    "relationType": "entity", "canvasData": { "cells": [...] } }],
  "dicts": [{ "id": "<uuid>", "defKey": "", "defName": "", "items": [...] }],
  "domains": [{ "id": "<uuid>", "defKey": "", "defName": "", "applyFor": "", "len": "", "scale": "" }],
  "dataTypeMapping": { "mappings": [{ "id": "<uuid>", "defKey": "", "MySQL": "...", "PostgreSQL": "..." }] },
  "viewGroups": [{ "id": "<uuid>", "defKey": "", "refEntities": [...], "refViews": [...], "refDiagrams": [...] }],
  "standardFields": [...],
  "logicEntities": [...],
  "namingRules": { "entityDefKey": {...}, "fieldDefKey": {...} }
}
```

### 3. Key Domain Objects

#### Entity (Data Table)
- `defKey` — table code (snake_case)
- `defName` — table display name (中文)
- `fields[]` — column definitions with defKey, type, len, scale, primaryKey, notNull, etc.
- `indexes[]` — index definitions
- `correlations[]` — foreign key relationships
- `type` — 'P' (physical) or 'L' (logical)

#### Field
- `defKey` — column code
- `defName` — column name
- `type` — database type (set via domain mapping)
- `domain` — domain ref (references domains[].id)
- `len`, `scale` — type parameters
- `primaryKey`, `notNull`, `autoIncrement` — constraints
- `comment` — column comment
- `refDict` — data dictionary reference
- `defaultValue` — default value
- `hideInGraph` — hidden in ER diagram

#### Diagram (ER Canvas)
- `canvasData.cells[]` — nodes (shape=table/edit-node) and edges (shape=erdRelation)
- Table nodes reference entities via `originKey`
- ER relations define source/target ports

### 4. GUI Actions → Operations Mapping

| GUI Action | Redux Action | CLI Operation |
|------------|-------------|---------------|
| New project | CREATE_PROJECT_SUCCESS | `project new` |
| Open project | READ_PROJECT_SUCCESS | `project open` |
| Save project | SAVE_PROJECT_SUCCESS | `project save` |
| Add entity | (tab system) | `entity add` |
| Edit entity fields | (tab system) | `entity update-field` |
| Delete entity | (tab system) | `entity delete` |
| Add relation | (canvas) | `diagram add-relation` |
| Export SQL | (tool) | `export ddl` |
| Import PDM | (tool) | `import pdman` |
| Reverse DB | (tool) | `db reverse` |
| Code generate | (tool) | `code generate` |

### 5. Java Backend Capabilities

The `pdmaner-java.jar` supports:
- Database connection testing
- Database reverse engineering (schema → entities)
- Code generation (Java, MyBatis, etc.)
- SQL DDL generation

### 6. Approach for This Harness

Since PDManer has no headless CLI, we take a **hybrid approach**:
1. **JSON manipulation** (Python) — project, entity, view, diagram, dict, domain CRUD
2. **Java subprocess** — DB operations, code generation (call pdmaner-java.jar)
3. **SQL generation** (Python) — generate DDL from entity definitions using type mappings
4. **Export** (Python) — generate Word/Excel/markdown from project data
