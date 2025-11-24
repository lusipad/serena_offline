"""
Build a truly standalone, portable Serena distribution for Windows.
Dependencies: 'uv' must be installed and available in PATH.
"""

import os
import shutil
import subprocess
import sys
import logging
import stat
from pathlib import Path

# Configuration
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("SerenaBuilder")

# Paths
BUILDER_ROOT = Path(__file__).parent
PROJECT_ROOT = Path(r"D:\\Repos\\serena") # Hardcoded to original repo
DIST_DIR = BUILDER_ROOT / "dist" / "serena-standalone"
PYTHON_VERSION = "3.11"

def remove_readonly(func, path, _):
    """Clear the readonly bit and reattempt the removal"""
    os.chmod(path, stat.S_IWRITE)
    func(path)

def run_cmd(cmd, cwd=None, env=None, check=True):
    """Run a shell command."""
    logger.info(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(cmd, cwd=cwd, env=env, check=check, capture_output=True, text=True)
        if result.stdout:
            logger.debug(result.stdout)
        if result.stderr:
            logger.warning(result.stderr)
        return result
    except subprocess.CalledProcessError as e:
        if e.stdout:
            logger.error(f"Command stdout:\n{e.stdout}")
        if e.stderr:
            logger.error(f"Command stderr:\n{e.stderr}")
        raise e

def find_uv_python_path():
    """Find a clean Python installation managed by uv."""
    # Try to find via uv path
    # On Windows, uv stores python in %LOCALAPPDATA%/uv/python or %APPDATA%/uv/python
    # But simpler: let's check the current venv's pyvenv.cfg to find the "home"
    venv_cfg = PROJECT_ROOT / ".venv" / "pyvenv.cfg"
    if venv_cfg.exists():
        with open(venv_cfg, "r") as f:
            for line in f:
                if line.strip().startswith("home ="):
                    home_path = line.split("=", 1)[1].strip()
                    logger.info(f"Found Python home from venv: {home_path}")
                    return Path(home_path)
    
    logger.error("Could not find Python source. Make sure you are running in a uv-managed venv.")
    sys.exit(1)

def get_node_path():
    """Find node.exe in the system."""
    cmd = ["where", "node"]
    try:
        result = run_cmd(cmd, check=False)
        if result.returncode == 0:
            node_path = Path(result.stdout.strip().split('\n')[0])
            logger.info(f"Found Node.js at: {node_path}")
            return node_path
    except Exception:
        pass
    
    logger.warning("Node.js not found in PATH! Language servers requiring Node will not work.")
    return None

def download_node(target_dir):
    """Download Node.js binary if not found locally."""
    import urllib.request
    import zipfile
    import io
    
    NODE_VERSION = "v20.10.0"
    NODE_URL = f"https://nodejs.org/dist/{NODE_VERSION}/node-{NODE_VERSION}-win-x64.zip"
    
    logger.info(f"Downloading Node.js {NODE_VERSION} from {NODE_URL}...")
    try:
        with urllib.request.urlopen(NODE_URL) as response:
            with zipfile.ZipFile(io.BytesIO(response.read())) as z:
                # The zip contains a folder "node-v...". We want the contents of that folder.
                # Or specifically just node.exe for minimal size? 
                # npm is also needed for some LS that download packages via npm!
                # So we should extract the whole thing.
                
                # Extract to a temp dir first
                temp_extract = target_dir.parent / "node_temp"
                z.extractall(temp_extract)
                
                # Move contents
                extracted_folder = temp_extract / f"node-{NODE_VERSION}-win-x64"
                
                # Copy node.exe
                shutil.copy2(extracted_folder / "node.exe", target_dir / "node.exe")
                
                # Copy others if we want full npm support (optional but recommended)
                # For now, let's just stick to node.exe to keep it simple as per request
                # Most LS are single JS files run with 'node server.js'
                
                shutil.rmtree(temp_extract)
                logger.info("Node.js downloaded and extracted.")
                return target_dir / "node.exe"
    except Exception as e:
        logger.error(f"Failed to download Node.js: {e}")
        return None

def build_standalone():
    if DIST_DIR.exists():
        logger.info(f"Cleaning previous build: {DIST_DIR}")
        shutil.rmtree(DIST_DIR, onerror=remove_readonly)
    
    DIST_DIR.mkdir(parents=True)
    
    # Structure
    # /bin      -> entry points, node.exe
    # /python   -> embedded python
    # /lib      -> site-packages (dependencies + serena)
    # /data     -> language servers, etc.
    
    bin_dir = DIST_DIR / "bin"
    python_dest_dir = DIST_DIR / "python"
    lib_dir = DIST_DIR / "lib"
    data_dir = DIST_DIR / "data"
    
    bin_dir.mkdir()
    lib_dir.mkdir()
    data_dir.mkdir()

    # 1. Copy Python
    python_src = find_uv_python_path()
    logger.info(f"Copying Python from {python_src}...")
    shutil.copytree(python_src, python_dest_dir)
    
    # 2. Copy Node.js
    node_src = get_node_path()
    if node_src:
        logger.info("Copying Node.js...")
        shutil.copy2(node_src, bin_dir / "node.exe")
    else:
        logger.info("Local Node.js not found. Attempting download...")
        download_node(bin_dir)
    
    # 3. Export and Install Dependencies
    logger.info("Exporting dependencies...")
    # We assume serena is editable installed or we just want deps. 
    # Let's get deps from pyproject.toml
    req_file = DIST_DIR / "requirements.txt"
    
    # We need to run uv export in the PROJECT_ROOT
    run_cmd(["uv", "export", "--no-hashes", "--output-file", str(req_file)], cwd=PROJECT_ROOT)
    
    logger.info("Installing dependencies to isolated lib directory...")
    # Use uv pip install instead of python -m pip
    # uv pip install supports --target and doesn't require pip to be installed in the environment
    run_cmd(["uv", "pip", "install", "-r", str(req_file), "--target", str(lib_dir), "--no-deps"])
    
    # 4. Install Serena Source
    logger.info("Copying Serena source code...")
    # We copy src contents directly into lib/ to act as installed packages
    src_dir = PROJECT_ROOT / "src"
    for item in src_dir.iterdir():
        if item.is_dir() and not item.name.startswith(".") and not item.name.startswith("__"):
            dest = lib_dir / item.name
            if dest.exists(): shutil.rmtree(dest)
            shutil.copytree(item, dest)
            
    # Copy Launcher from resources
    launcher_src = BUILDER_ROOT / "resources" / "launcher.py"
    if launcher_src.exists():
        logger.info(f"Injecting launcher from {launcher_src}")
        shutil.copy2(launcher_src, lib_dir / "serena" / "launcher.py")
    else:
        logger.warning(f"Launcher not found at {launcher_src}")

    # Create __main__.py for serena package to be executable
    (lib_dir / "serena" / "__main__.py").write_text(
        "from serena.cli import top_level\nif __name__ == '__main__':\n    top_level()\n",
        encoding="utf-8"
    )
    
    # 5. Pre-download and Copy Language Servers
    # We assume the user might have run predownload_language_servers.py already, 
    # or we can check ~/.solidlsp
    home_solidlsp = Path.home() / ".solidlsp"
    dest_solidlsp = data_dir / "solidlsp"
    
    # Optional: Trigger download if missing
    # run_cmd([sys.executable, "scripts/predownload_language_servers.py"])
    
    if home_solidlsp.exists():
        logger.info(f"Copying Language Servers from {home_solidlsp}...")
        # Only copy language_servers directory to save space/time if other junk exists
        ls_src = home_solidlsp / "language_servers"
        if ls_src.exists():
            shutil.copytree(ls_src, dest_solidlsp / "language_servers")
        else:
            logger.warning("No language_servers found in .solidlsp!")
    else:
        logger.warning("~/.solidlsp does not exist. Language servers will be missing!")

    # 6. Create Launch Scripts
    logger.info("Creating launcher scripts...")
    create_launchers(DIST_DIR)
    
    logger.info("="*60)
    logger.info(f"Build Complete: {DIST_DIR}")
    logger.info("="*60)

def create_launchers(dist_path):
    # serena.bat
    # We need to set PYTHONPATH to lib and pywin32 subdirs
    # We need to add bin, python and pywin32_system32 to PATH
    # We need to set SOLIDLSP_DIR to data/solidlsp
    
    bat_content = r"""@echo off
setlocal enabledelayedexpansion

set "BASE_DIR=%~dp0"
set "BASE_DIR=%BASE_DIR:~0,-1%"

set "PYTHON_HOME=%BASE_DIR%\python"
set "NODE_HOME=%BASE_DIR%\bin"
set "LIB_DIR=%BASE_DIR%\lib"
set "SOLIDLSP_DIR=%BASE_DIR%\data\solidlsp"

REM Pywin32 paths
set "PYWIN32_SYS32=%LIB_DIR%\pywin32_system32"
set "WIN32_LIB=%LIB_DIR%\win32"
set "WIN32_LIB_LIB=%LIB_DIR%\win32\lib"
set "PYTHONWIN=%LIB_DIR%\Pythonwin"

REM Set Path to include Python, Node and pywin32 DLLs
set "PATH=%PYTHON_HOME%;%PYTHON_HOME%\Scripts;%NODE_HOME%;%PYWIN32_SYS32%;%PATH%"

REM Set PYTHONPATH to include our lib directory and pywin32 libraries
set "PYTHONPATH=%LIB_DIR%;%WIN32_LIB%;%WIN32_LIB_LIB%;%PYTHONWIN%;%PYTHONPATH%"

REM Run Serena
"%PYTHON_HOME%\python.exe" -m serena %*

if %ERRORLEVEL% NEQ 0 (
    echo Serena exited with error code %ERRORLEVEL%
    pause
)

endlocal
"""
    (dist_path / "serena.bat").write_text(bat_content, encoding="utf-8")

    # serena-launcher.bat (GUI)
    # Uses pythonw.exe to avoid console window
    gui_bat_content = r"""@echo off
setlocal enabledelayedexpansion

set "BASE_DIR=%~dp0"
set "BASE_DIR=%BASE_DIR:~0,-1%"

set "PYTHON_HOME=%BASE_DIR%\python"
set "NODE_HOME=%BASE_DIR%\bin"
set "LIB_DIR=%BASE_DIR%\lib"
set "SOLIDLSP_DIR=%BASE_DIR%\data\solidlsp"

REM Pywin32 paths
set "PYWIN32_SYS32=%LIB_DIR%\pywin32_system32"
set "WIN32_LIB=%LIB_DIR%\win32"
set "WIN32_LIB_LIB=%LIB_DIR%\win32\lib"
set "PYTHONWIN=%LIB_DIR%\Pythonwin"

REM Set Path to include Python, Node and pywin32 DLLs
set "PATH=%PYTHON_HOME%;%PYTHON_HOME%\Scripts;%NODE_HOME%;%PYWIN32_SYS32%;%PATH%"

REM Set PYTHONPATH to include our lib directory and pywin32 libraries
set "PYTHONPATH=%LIB_DIR%;%WIN32_LIB%;%WIN32_LIB_LIB%;%PYTHONWIN%;%PYTHONPATH%"

REM Run Serena GUI Launcher
"%PYTHON_HOME%\python.exe" -m serena.launcher %*

if %ERRORLEVEL% NEQ 0 (
    echo Launcher exited with error code %ERRORLEVEL%
    pause
)

endlocal
"""
    (dist_path / "serena-launcher.bat").write_text(gui_bat_content, encoding="utf-8")

    # README
    readme_content = "# Serena Standalone

This is a fully portable version of Serena.

## Prerequisites
- None! (Python and Node.js are included)

## Usage

### GUI Launcher (Recommended)
Run `serena-launcher.bat` to open the graphical interface.
- Configure Claude Desktop automatically
- Start/Stop server for debugging
- Manage settings

### Command Line
Run `serena.bat` followed by arguments.

Example:
```
serena.bat start-mcp-server
```

## Directory Structure
- `bin/`: Helper executables (Node.js)
- `python/`: Embedded Python environment
- `lib/`: Python libraries and Serena source
- `data/`: Data files (Language Servers)
"
    (dist_path / "README.txt").write_text(readme_content, encoding="utf-8")

if __name__ == "__main__":
    build_standalone()
