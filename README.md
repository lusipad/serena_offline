# Serena Offline Builder

This repository contains build scripts to create a **standalone, offline-capable distribution** of [Serena](https://github.com/lusipad/serena) for Windows.

It solves the problem of deploying Serena in environments with restricted internet access by pre-packaging:
*   An embedded Python runtime.
*   Required Python dependencies (managed via `uv`).
*   Node.js binary (optional, for JS/TS based servers).
*   **Offline Language Server Protocols (LSP)**: You can select and download exactly which language servers to bundle.

## Prerequisites

Before using the builder, ensure you have the following:

1.  **Python 3.11+**: Installed and available in your system `PATH`.
2.  **[uv](https://github.com/astral-sh/uv)**: The build tool uses `uv` for high-speed dependency resolution.
    ```bash
    pip install uv
    ```
3.  **Serena Source Code**: You need a local copy of the main Serena repository (e.g., `D:\Repos\serena`).

## Quick Start

### 1. Launch the GUI Builder (Recommended)

We provide a PowerShell wrapper that checks your environment and launches the builder.

1.  Right-click on **`run_builder.ps1`** and choose **"Run with PowerShell"**.
2.  (Alternatively) Open a terminal and run:
    ```powershell
    .\run_builder.ps1
    ```

### 2. Configure and Build

In the GUI window:
1.  **Paths**: Verify the "Project Root" points to your `serena` source folder.
2.  **Language Packages**:
    *   The list shows supported languages.
    *   **Cached**: Languages marked with `(Cached)` are already present in your local cache (`~/.solidlsp/language_servers`) and ready to pack.
    *   **Download**: Select languages you need that aren't cached, then click **"Download Selected"**. This runs the pre-download script to fetch them from the internet.
3.  **Select**: Check the boxes for the languages you want to include in the final offline build.
4.  **Build**: Click **"BUILD STANDALONE PACKAGE"**.

## Output

The build artifact will be created in `dist/serena-standalone` (configurable). It contains:

*   **`serena-launcher.bat`**: The main entry point for users. Launches the Serena configuration GUI.
*   **`serena.bat`**: Command-line interface.
*   **`python/`**: The embedded Python environment.
*   **`lib/`**: Installed dependencies and Serena source code.
*   **`data/`**: The offline language servers you selected.

## Scripts Overview

*   `build_gui.py`: The main Tkinter-based application for managing the build process.
*   `run_builder.ps1`: Helper script to setup the environment and launch the GUI.
*   `build.py`: The backend logic for creating the portable distribution (imported by the GUI).

## License

MIT
