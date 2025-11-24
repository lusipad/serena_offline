import json
import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import stat
import logging

# Configure logging for the GUI console
class TextHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        def append():
            self.text_widget.config(state='normal')
            self.text_widget.insert(tk.END, msg + '\n')
            self.text_widget.see(tk.END)
            self.text_widget.config(state='disabled')
        self.text_widget.after(0, append)

# Default Paths
DEFAULT_PROJECT_ROOT = Path(r"D:\\Repos\\serena")
DEFAULT_BUILD_DIR = Path(__file__).parent / "dist" / "serena-standalone"

# Known Downloadable Languages (Mirroring predownload_language_servers.py)
KNOWN_LANGUAGES = [
    "java", "kotlin", "typescript", "csharp", "cpp", "clojure", "bash", 
    "lua", "markdown", "terraform", "dart", "julia", "scala", "swift", 
    "elm", "zig", "yaml", "php", "perl", "ruby"
]

class SerenaBuilderGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Serena Offline Builder")
        self.geometry("800x700")
        
        # Styles
        style = ttk.Style()
        style.configure("TButton", padding=6)
        style.configure("TLabel", padding=6)
        
        # Variables
        self.project_root = tk.StringVar(value=str(DEFAULT_PROJECT_ROOT))
        self.build_dir = tk.StringVar(value=str(DEFAULT_BUILD_DIR))
        self.ls_source_dir = tk.StringVar(value=self.detect_ls_dir())
        self.python_path = tk.StringVar(value="") 
        self.selected_languages = {} # name -> BooleanVar
        
        # Layout
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 1. Paths Configuration
        paths_frame = ttk.LabelFrame(main_frame, text="Paths", padding="10")
        paths_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.create_path_entry(paths_frame, "Project Root:", self.project_root, 0)
        self.create_path_entry(paths_frame, "Build Output:", self.build_dir, 1)
        self.create_path_entry(paths_frame, "LS Source Cache:", self.ls_source_dir, 2)
        
        # 2. Language Selection
        ls_frame = ttk.LabelFrame(main_frame, text="Language Packages", padding="10")
        ls_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Toolbar for LS
        ls_toolbar = ttk.Frame(ls_frame)
        ls_toolbar.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(ls_toolbar, text="Refresh from Cache", command=self.refresh_ls_list).pack(side=tk.LEFT)
        ttk.Button(ls_toolbar, text="Select All", command=self.select_all_ls).pack(side=tk.LEFT, padx=5)
        ttk.Button(ls_toolbar, text="Select None", command=self.deselect_all_ls).pack(side=tk.LEFT, padx=5)
        
        # Download section
        ttk.Separator(ls_toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        ttk.Label(ls_toolbar, text="Download Tools:").pack(side=tk.LEFT)
        ttk.Button(ls_toolbar, text="Download Selected", command=self.download_selected_ls).pack(side=tk.LEFT, padx=5)
        
        # List area
        self.ls_canvas = tk.Canvas(ls_frame)
        scrollbar = ttk.Scrollbar(ls_frame, orient="vertical", command=self.ls_canvas.yview)
        self.ls_list_frame = ttk.Frame(self.ls_canvas)
        
        self.ls_canvas.create_window((0, 0), window=self.ls_list_frame, anchor="nw")
        self.ls_canvas.configure(yscrollcommand=scrollbar.set)
        
        self.ls_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        self.ls_list_frame.bind("<Configure>", lambda e: self.ls_canvas.configure(scrollregion=self.ls_canvas.bbox("all")))
        
        # 3. Log / Status
        log_frame = ttk.LabelFrame(main_frame, text="Build Log", padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.log_text = tk.Text(log_frame, height=10, state='disabled')
        self.log_text.pack(fill=tk.BOTH, expand=True)
        
        # Setup Logger
        self.logger = logging.getLogger("GuiBuilder")
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(TextHandler(self.log_text))
        
        # 4. Actions
        action_frame = ttk.Frame(main_frame)
        action_frame.pack(fill=tk.X)
        
        ttk.Button(action_frame, text="BUILD STANDALONE PACKAGE", command=self.start_build_thread).pack(side=tk.RIGHT, padx=5)

        # Initial populate
        self.refresh_ls_list()

    def create_path_entry(self, parent, label, variable, row):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w")
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, sticky="ew", padx=5)
        ttk.Button(parent, text="...", width=3, command=lambda: self.browse_path(variable)).grid(row=row, column=2)
        parent.columnconfigure(1, weight=1)

    def browse_path(self, variable):
        path = filedialog.askdirectory(initialdir=variable.get())
        if path:
            variable.set(path)

    def detect_ls_dir(self):
        # Check common locations
        paths = [
            Path.home() / ".solidlsp" / "language_servers",
            Path.home() / ".serena" / "language_servers"
        ]
        for p in paths:
            if p.exists():
                return str(p)
        return str(Path.home() / ".solidlsp" / "language_servers") # Default

    def refresh_ls_list(self):
        # Clear existing
        for widget in self.ls_list_frame.winfo_children():
            widget.destroy()
        self.selected_languages.clear()
        
        source_dir = Path(self.ls_source_dir.get())
        
        # Get cached directories
        cached = set()
        if source_dir.exists():
            for item in source_dir.iterdir():
                if item.is_dir():
                    cached.add(item.name)
        
        # Merge with known languages to show everything
        all_langs = sorted(list(set(KNOWN_LANGUAGES) | cached))
        
        r = 0
        c = 0
        for lang in all_langs:
            var = tk.BooleanVar(value=(lang in cached)) # Default select if cached
            self.selected_languages[lang] = var
            
            # Label text: Name + [Cached] status
            status = " (Cached)" if lang in cached else ""
            
            cb = ttk.Checkbutton(self.ls_list_frame, text=f"{lang}{status}", variable=var)
            cb.grid(row=r, column=c, sticky="w", padx=10, pady=2)
            
            c += 1
            if c > 3: # 4 columns
                c = 0
                r += 1

    def select_all_ls(self):
        for var in self.selected_languages.values():
            var.set(True)

    def deselect_all_ls(self):
        for var in self.selected_languages.values():
            var.set(False)

    def download_selected_ls(self):
        # Run scripts/predownload_language_servers.py
        selected = [l for l, v in self.selected_languages.items() if v.get()]
        if not selected:
            messagebox.showwarning("Warning", "No languages selected to download.")
            return
        
        proj_root = Path(self.project_root.get())
        script_path = proj_root / "scripts" / "predownload_language_servers.py"
        
        if not script_path.exists():
            self.logger.error(f"Download script not found: {script_path}")
            messagebox.showerror("Error", f"Script not found:\n{script_path}")
            return
            
        cmd = ["uv", "run", "python", str(script_path), "--languages", ",".join(selected)]
        
        threading.Thread(target=self.run_subprocess, args=(cmd, "Download Complete"), daemon=True).start()

    def start_build_thread(self):
        threading.Thread(target=self.run_build, daemon=True).start()

    def run_subprocess(self, cmd, success_msg):
        self.logger.info(f"Running: {' '.join(cmd)}")
        try:
            proc = subprocess.Popen(
                cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.STDOUT, 
                text=True, 
                cwd=self.project_root.get(),
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            for line in proc.stdout:
                self.logger.info(line.strip())
            
            proc.wait()
            if proc.returncode == 0:
                self.logger.info(success_msg)
                self.after(0, self.refresh_ls_list) # Refresh UI to show new cached items
            else:
                self.logger.error(f"Process failed with code {proc.returncode}")
        except Exception as e:
            self.logger.error(f"Error running subprocess: {e}")

    # ==============================================================================
    # BUILD LOGIC (Adapted from build.py)
    # ==============================================================================
    def run_build(self):
        try:
            self.logger.info("Starting Build Process...")
            
            dist_dir = Path(self.build_dir.get())
            project_root = Path(self.project_root.get())
            
            # 1. Clean / Create Dist
            if dist_dir.exists():
                self.logger.info("Cleaning previous build...")
                shutil.rmtree(dist_dir, onerror=self.remove_readonly)
            dist_dir.mkdir(parents=True)
            
            bin_dir = dist_dir / "bin"
            python_dest_dir = dist_dir / "python"
            lib_dir = dist_dir / "lib"
            data_dir = dist_dir / "data"
            
            for d in [bin_dir, lib_dir, data_dir]:
                d.mkdir()
                
            # 2. Find and Copy Python
            python_src = self.find_uv_python_path(project_root)
            self.logger.info(f"Copying Python from {python_src}...")
            shutil.copytree(python_src, python_dest_dir)
            
            # 3. Node.js
            node_src = self.get_node_path()
            if node_src:
                self.logger.info(f"Copying Node.js from {node_src}...")
                shutil.copy2(node_src, bin_dir / "node.exe")
            else:
                self.logger.warning("Node.js not found! Some LS may fail.")

            # 4. Dependencies
            self.logger.info("Exporting dependencies...")
            req_file = dist_dir / "requirements.txt"
            
            # uv export
            self.run_cmd(["uv", "export", "--no-hashes", "--output-file", str(req_file)], cwd=project_root)
            
            self.logger.info("Installing dependencies...")
            self.run_cmd(["uv", "pip", "install", "-r", str(req_file), "--target", str(lib_dir), "--no-deps"])
            
            # 5. Serena Source
            self.logger.info("Copying Serena source...")
            src_dir = project_root / "src"
            for item in src_dir.iterdir():
                if item.is_dir() and not item.name.startswith(".") and not item.name.startswith("__"):
                    dest = lib_dir / item.name
                    if dest.exists(): shutil.rmtree(dest)
                    shutil.copytree(item, dest)

            # Inject Launcher (if available in current workspace resources)
            # We are running this script from the workspace root probably
            launcher_src = Path(__file__).parent / "resources" / "launcher.py"
            if launcher_src.exists():
                self.logger.info("Injecting launcher...")
                shutil.copy2(launcher_src, lib_dir / "serena" / "launcher.py")
            else:
                self.logger.warning(f"Launcher not found at {launcher_src}")

            # Create __main__.py
            (lib_dir / "serena" / "__main__.py").write_text(
                "from serena.cli import top_level\nif __name__ == '__main__':\n    top_level()\n",
                encoding="utf-8"
            )

            # 6. Language Servers (Filtered)
            ls_source = Path(self.ls_source_dir.get())
            ls_dest = data_dir / "solidlsp" / "language_servers"
            ls_dest.parent.mkdir(parents=True, exist_ok=True)
            ls_dest.mkdir()
            
            selected = [l for l, v in self.selected_languages.items() if v.get()]
            self.logger.info(f"Copying {len(selected)} selected language servers...")
            
            if ls_source.exists():
                for lang in selected:
                    src = ls_source / lang
                    if src.exists() and src.is_dir():
                        self.logger.info(f"  - {lang}")
                        shutil.copytree(src, ls_dest / lang)
                    else:
                        self.logger.warning(f"  - {lang} NOT FOUND in cache (skipped)")
            else:
                self.logger.error(f"LS Source dir not found: {ls_source}")

            # 7. Launchers
            self.create_launchers(dist_dir)
            
            self.logger.info("BUILD COMPLETE SUCCESSFULY!")
            messagebox.showinfo("Success", "Build Complete!")

        except Exception as e:
            self.logger.error(f"Build Failed: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            messagebox.showerror("Error", f"Build Failed: {e}")

    def run_cmd(self, cmd, cwd=None, env=None):
        self.logger.info(f"Exec: {' '.join(cmd)}")
        subprocess.run(cmd, cwd=cwd, env=env, check=True, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)

    def remove_readonly(self, func, path, _):
        os.chmod(path, stat.S_IWRITE)
        func(path)

    def find_uv_python_path(self, project_root):
        venv_cfg = project_root / ".venv" / "pyvenv.cfg"
        if venv_cfg.exists():
            with open(venv_cfg, "r") as f:
                for line in f:
                    if line.strip().startswith("home ="):
                        return Path(line.split("=", 1)[1].strip())
        # Fallback to sys.executable's parent if running in venv
        return Path(sys.executable).parent

    def get_node_path(self):
        try:
            result = subprocess.run(["where", "node"], capture_output=True, text=True)
            if result.returncode == 0:
                return Path(result.stdout.strip().split('\n')[0])
        except:
            pass
        return None

    def create_launchers(self, dist_path):
        # Copy-paste of launcher creation logic
        bat_content = r"""@echo off
setlocal enabledelayedexpansion

set "BASE_DIR=%~dp0"
set "BASE_DIR=%BASE_DIR:~0,-1%"

set "PYTHON_HOME=%BASE_DIR%\python"
set "NODE_HOME=%BASE_DIR%\bin"
set "LIB_DIR=%BASE_DIR%\lib"
set "SOLIDLSP_DIR=%BASE_DIR%\data\solidlsp"

set "PYWIN32_SYS32=%LIB_DIR%\pywin32_system32"
set "WIN32_LIB=%LIB_DIR%\win32"
set "WIN32_LIB_LIB=%LIB_DIR%\win32\lib"
set "PYTHONWIN=%LIB_DIR%\Pythonwin"

set "PATH=%PYTHON_HOME%;%PYTHON_HOME%\Scripts;%NODE_HOME%;%PYWIN32_SYS32%;%PATH%"
set "PYTHONPATH=%LIB_DIR%;%WIN32_LIB%;%WIN32_LIB_LIB%;%PYTHONWIN%;%PYTHONPATH%"

"%PYTHON_HOME%\python.exe" -m serena %* 

if %ERRORLEVEL% NEQ 0 (
    echo Serena exited with error code %ERRORLEVEL%
    pause
)
endlocal
"""
        (dist_path / "serena.bat").write_text(bat_content, encoding="utf-8")
        
        gui_bat_content = r"""@echo off
setlocal enabledelayedexpansion
set "BASE_DIR=%~dp0"
set "BASE_DIR=%BASE_DIR:~0,-1%"
set "PYTHON_HOME=%BASE_DIR%\python"
set "NODE_HOME=%BASE_DIR%\bin"
set "LIB_DIR=%BASE_DIR%\lib"
set "SOLIDLSP_DIR=%BASE_DIR%\data\solidlsp"
set "PYWIN32_SYS32=%LIB_DIR%\pywin32_system32"
set "WIN32_LIB=%LIB_DIR%\win32"
set "WIN32_LIB_LIB=%LIB_DIR%\win32\lib"
set "PYTHONWIN=%LIB_DIR%\Pythonwin"
set "PATH=%PYTHON_HOME%;%PYTHON_HOME%\Scripts;%NODE_HOME%;%PYWIN32_SYS32%;%PATH%"
set "PYTHONPATH=%LIB_DIR%;%WIN32_LIB%;%WIN32_LIB_LIB%;%PYTHONWIN%;%PYTHONPATH%"
"%PYTHON_HOME%\python.exe" -m serena.launcher %*
if %ERRORLEVEL% NEQ 0 (
    echo Launcher exited with error code %ERRORLEVEL%
    pause
)
endlocal
"""
        (dist_path / "serena-launcher.bat").write_text(gui_bat_content, encoding="utf-8")


if __name__ == "__main__":
    app = SerenaBuilderGUI()
    app.mainloop()
