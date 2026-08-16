# USD Assembler
![image alt](https://github.com/arthurJusteau/usd-assembler/blob/main/usd-assembler%20screen.png?raw=true)

A PySide tool to compose USD assets and shots from published pipeline outputs: link modeling/rigging/animation/lighting outputs into an asset, link assets and assemblies into a shot, and publish versioned composition files. The actual USD composition happens downstream when these files are loaded in Houdini/Solaris or Maya. This tool only builds the sublayer graph.

### What's here

| Module | Role | Notable technical points |
|---|---|---|
| `scanner.py` (`AssetScanner`, `ProjectManager`) | Scans a project's `assets/` and `shots/` folders for published USD outputs by department | Version-aware lookup (`latest/` first, falls back to the highest `vXXX` folder), category filtering by asset name prefix |
| `ui.py` (`USDAssembler`) | Main window: pick an asset or shot, link department outputs together, publish a versioned assembly | Supports publishing a shot against a specific named assembly (not just `main`), each with its own root `.usda` |
| `widgets.py` | Custom dropdown and dialogs | Scrollable popup-style dropdown built for large asset/shot lists (hundreds of entries without a laggy native combo box) |
| `usda_io.py` | Read/write layer for the composition files | Uses `pxr.Sdf.Layer` directly - `subLayerPaths` are authored and read through the real USD API, not built or parsed as raw text |
| `main.py` | Entry point | PyQt6/PySide6 auto-detection |

### Setup
```bash
python main.py
```

Requires Python with `pxr` (USD) and PyQt6 or PySide6 (auto-detected), and a `PIPELINE_PROJECT_PATH` environment variable pointing at a project root with `assets/` and `shots/` subfolders.
