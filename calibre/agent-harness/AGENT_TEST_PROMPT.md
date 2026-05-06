# Calibre Agent Test Prompt (Bilingual)

> Purpose: reproducible **Agent test** prompt for OpenCode/Cursor/Claude Code in CLI-only mode.  
> 目的：提供可复用的 **Agent test** 提示词（仅 CLI），用于开源复现。
> Note / 说明：This file is an **example agent-test prompt/keyword template** for reproducible validation and can be adapted per environment.  
> 注：该文件是用于复现实验的**示例智能体测试提示词/关键词模板**，可按环境替换路径与参数。
> Status / 状态：**Example template (not a normative spec)**.  
> 状态：**示例模板（非规范性标准文档）**。

---

## Quick Notes / 使用说明

- **System / 系统**: Windows (PowerShell examples below)
- **Terminal / 终端类型**: PowerShell (if using CMD, adjust line continuation syntax)
- **Agent mode / 代理模式**: CLI-only (no GUI actions during Agent test)
- **Path placeholders / 路径变量可替换**:
  - `{{LIB}}` = calibre library root (must contain `metadata.db`)
  - `{{EPUB}}` = input epub path
  - `{{OUT}}` = export output directory
  - `{{CONVERTED_FILE}}` = converted mobi output path

Recommended defaults:

```text
{{LIB}} = D:\Books\Calibre Library
{{EPUB}} = D:\AgentTest\sample.epub
{{OUT}} = D:\AgentTest\out
{{CONVERTED_FILE}} = D:\AgentTest\out\converted\agent-test.mobi
```

---

## Prompt (ZH + EN)

```text
[中文]
你是一个只允许使用 CLI 的执行代理。当前目标：完成 calibre 的 Agent test（加分/高阶验证）。不要生成新 harness，不要使用任何 GUI。

【环境与固定路径】
- OS: Windows (PowerShell)
- calibre 已安装
- cli-anything-calibre 已安装
- LIB = {{LIB}}
- EPUB = {{EPUB}}
- OUT = {{OUT}}
- CONVERTED_FILE = {{CONVERTED_FILE}}

【硬性规则】
1) 禁止猜参数；不确定必须先运行对应 --help。
2) 每一步都输出：执行命令、exit code、关键输出。
3) 失败时先打印错误，再自修复继续。
4) 全程仅 CLI，不得调用 GUI。
5) 路径必须使用绝对路径。

【Preflight（必须先执行）】
A. 检查命令可用（逐条执行）：
- cli-anything-calibre --help
- calibredb --version
- ebook-convert --version
- ebook-meta --version

B. 若 `cli-anything-calibre` 不可调用：
- 自动定位并使用 Python 用户 Scripts 下的 `cli-anything-calibre.exe`（或临时修正 PATH）后重试，直到可用。

C. 若 `EPUB` 不存在：
- 自动创建一个合法 EPUB 后继续（可用 html -> ebook-convert，或最小合法 zip 结构，确保 mimetype 未压缩）。

D. 若 `LIB` 不是有效 calibre 书库（缺少 metadata.db）：
- 先初始化书库（例如 `calibredb --with-library "<LIB>" list`），再继续。

E. 探测子命令帮助（逐条执行）：
- cli-anything-calibre library --help
- cli-anything-calibre book --help
- cli-anything-calibre export --help
- cli-anything-calibre convert --help
- cli-anything-calibre meta --help

【主任务链（严格按顺序）】
1) `library stats`（JSON）
2) `book add`：将 `EPUB` 入库，`--title "Agent Test Book"`，`--authors "OpenCode Bot"`
3) `book search "title:Agent Test Book"` 并提取 `book_id`（字段通常为 `id`）
4) `export book <book_id> --to-dir "<OUT>" --single-dir`
5) 在 `OUT` 下递归发现导出的 `.epub`（不要写死文件名），记为 `exported_epub`
6) `convert run "<exported_epub>" "<CONVERTED_FILE>" --preset kindle`
7) `meta show "<exported_epub>"`
8) 校验 `CONVERTED_FILE` 存在且大小 > 0，并输出字节数

【输出格式要求】
- 先输出完整分步复盘（命令 + exit code + 关键输出）
- 最后一行必须输出单行 JSON：
  FINAL_RESULT={"library_path":"...","book_id":...,"export_dir":"...","exported_epub":"...","converted_file":"...","converted_file_size_bytes":...,"all_exit_zero":true/false}

------------------------------------------------------------

[English]
You are a CLI-only execution agent. Goal: complete a calibre Agent test (bonus/advanced verification). Do not generate a new harness. Do not use GUI.

[Environment and fixed paths]
- OS: Windows (PowerShell)
- calibre is installed
- cli-anything-calibre is installed
- LIB = {{LIB}}
- EPUB = {{EPUB}}
- OUT = {{OUT}}
- CONVERTED_FILE = {{CONVERTED_FILE}}

[Hard rules]
1) Do not guess arguments; run --help first when unsure.
2) For every step, print command, exit code, and key output.
3) On failure, print error first, then self-correct and continue.
4) CLI-only flow; no GUI actions.
5) Use absolute paths only.

[Preflight (required)]
A. Verify command availability:
- cli-anything-calibre --help
- calibredb --version
- ebook-convert --version
- ebook-meta --version

B. If `cli-anything-calibre` is not callable:
- Auto-locate `cli-anything-calibre.exe` from Python user Scripts (or temporarily fix PATH), then retry.

C. If `EPUB` does not exist:
- Auto-create a valid EPUB (html -> ebook-convert, or minimal valid zip EPUB with uncompressed mimetype).

D. If `LIB` is not a valid calibre library (missing metadata.db):
- Initialize it first (e.g., `calibredb --with-library "<LIB>" list`).

E. Probe subcommand helps:
- cli-anything-calibre library --help
- cli-anything-calibre book --help
- cli-anything-calibre export --help
- cli-anything-calibre convert --help
- cli-anything-calibre meta --help

[Main task chain (strict order)]
1) `library stats` (JSON)
2) `book add` with `--title "Agent Test Book"` and `--authors "OpenCode Bot"`
3) `book search "title:Agent Test Book"` and extract `book_id` (typically `id`)
4) `export book <book_id> --to-dir "<OUT>" --single-dir`
5) Recursively discover exported `.epub` under `OUT` (do not hardcode filename), call it `exported_epub`
6) `convert run "<exported_epub>" "<CONVERTED_FILE>" --preset kindle`
7) `meta show "<exported_epub>"`
8) Validate `CONVERTED_FILE` exists and size > 0, print file size in bytes

[Output requirements]
- First provide step-by-step recap (command + exit code + key output)
- Final line must be a one-line JSON:
  FINAL_RESULT={"library_path":"...","book_id":...,"export_dir":"...","exported_epub":"...","converted_file":"...","converted_file_size_bytes":...,"all_exit_zero":true/false}
```

---

## Optional: GUI Round-trip Checklist / 可选 GUI 往返检查

After CLI flow succeeds, verify consistency in Calibre GUI:

1. Open the same library path (`{{LIB}}`).
2. Confirm book row exists (`Agent Test Book` / `OpenCode Bot`).
3. Open metadata editor and verify title/author.
4. Confirm exported and converted files exist and are non-empty.

