#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dynamic PyInstaller Spec File Generator for Kontextrument
----------------------------------------------------------
This script generates a .spec file for PyInstaller by automatically detecting
all necessary paths from the current Python environment, making the project
buildable on any system.

Usage:
    python generate_spec.py [--output FILENAME] [--debug]
"""
import sys
import os
import argparse
from pathlib import Path
import importlib.util
import site


def find_package_path(package_name):
    """
    Find the installation path of a Python package.
    
    Args:
        package_name: Name of the package to find
    
    Returns:
        Path object pointing to the package directory, or None if not found
    """
    try:
        spec = importlib.util.find_spec(package_name)
        if spec and spec.origin:
            package_path = Path(spec.origin)
            if package_path.name == "__init__.py":
                return package_path.parent
            return package_path
        return None
    except (ImportError, AttributeError, ValueError):
        return None


def find_wx_loader_dll():
    """
    Find the Loader.dll file in the wx package.
    
    Returns:
        Tuple of (source_path, destination_folder) or None if not found
    """
    wx_path = find_package_path("wx")
    if not wx_path:
        return None
    
    for dll_path in wx_path.rglob("Loader.dll"):
        return (str(dll_path), "wx")
    
    for dll_path in wx_path.rglob("WebView2Loader.dll"):
        return (str(dll_path), "wx")
    
    return None


def find_data_files():
    """
    Find all data files (assets) that need to be included.
    
    Returns:
        List of tuples (source, destination)
    """
    data_files = []
    project_root = Path(__file__).parent.resolve()
    assets_dir = project_root / "assets"
    
    if assets_dir.is_dir():
        for asset_file in assets_dir.iterdir():
            if asset_file.is_file():
                data_files.append((str(asset_file), "assets"))
    
    return data_files


def find_hidden_imports():
    """
    Determine which hidden imports are needed.
    
    Returns:
        List of module names to include as hidden imports
    """
    hidden_imports = [
        "wxktr_modules.create_context_panel",
        "wxktr_modules.wxbrowse",
        "wxktr_modules.apply_context_panel",
        "wxktr_modules.wxworkspace",
        "wxktr_modules.modules_parts.wxedit",
        "wxktr_modules.modules_parts.wxterm",
        "wxktr_modules.wxgit",
        "wxktr_modules.wxlauncher",
        "wxktr_modules.wxmodmanager",
        "wxktr_modules.settings_manager",
        "wxktr_modules.project_settings"
    ]
    
    if sys.platform == "win32":
        if find_package_path("winpty"):
            hidden_imports.append("winpty")
        if find_package_path("pathspec"):
            hidden_imports.append("pathspec")
    
    return hidden_imports


def get_project_root():
    """
    Get the absolute path to the project root directory.
    """
    return Path(__file__).parent.resolve()


def find_entry_point():
    """
    Find the entry point script, trying multiple possible locations.
    
    Returns:
        Path object pointing to the entry point, or None if not found
    """
    project_root = get_project_root()
    possible_entry_points = [
        project_root / "src" / "ktr_runner.py",
        project_root / "ktr_runner.py",
    ]
    
    for entry_point in possible_entry_points:
        if entry_point.exists():
            return entry_point
    
    return None


def escape_path_for_spec(path):
    """
    Escape a path string for use in a .spec file.
    Converts backslashes to forward slashes for cross-platform compatibility.
    
    Args:
        path: Path object or string to escape
    
    Returns:
        String with properly escaped path
    """
    path_str = str(path).replace("\\", "/")
    return path_str


def generate_spec_content(spec_name="ktr", entry_point=None, console=False, 
                         debug=False, onefile=True, strip_binaries=None):
    """
    Generate the content of the .spec file.
    
    Args:
        spec_name: Name of the output executable
        entry_point: Path to the main Python script (if None, will auto-detect)
        console: Whether to show console window
        debug: Whether to enable debug mode
        onefile: Whether to build as a single executable file (True) or 
                 as a folder with dependencies (False)
        strip_binaries: Whether to strip debug symbols from binaries (None=auto-detect)
    
    Returns:
        String containing the .spec file content
    """
    project_root = get_project_root()
    
    if strip_binaries is None:
        strip_binaries = sys.platform.startswith('linux')
    
    if entry_point is None:
        entry_point_path = find_entry_point()
        if entry_point_path is None:
            raise FileNotFoundError(
                "Could not find entry point. Tried:\n" + 
                "\n".join(f"  - {p}" for p in ["src/ktr_runner.py", "ktr_runner.py"])
            )
    else:
        entry_point_path = project_root / entry_point
        if not entry_point_path.exists():
            raise FileNotFoundError(f"Entry point not found: {entry_point_path}")
    
    data_files = find_data_files()
    hidden_imports = find_hidden_imports()
    wx_loader = find_wx_loader_dll()
    
    binaries = []
    if wx_loader:
        binaries.append(f"('{escape_path_for_spec(wx_loader[0])}', '{wx_loader[1]}')")
    
    data_str = ",\n        ".join(
        f"('{escape_path_for_spec(src)}', '{dst}')" 
        for src, dst in data_files
    ) if data_files else ""
    
    binaries_str = ",\n        ".join(binaries) if binaries else ""
    
    hidden_imports_str = ",\n        ".join(
        f"'{imp}'" for imp in hidden_imports
    ) if hidden_imports else ""
    
    icon_path = project_root / "assets" / "icon.ico"
    icon_str = f"'{escape_path_for_spec(icon_path)}'" if icon_path.exists() else "None"
    
    entry_point_str = escape_path_for_spec(entry_point_path)
    
    spec_content = f'''# -*- mode: python ; coding: utf-8 -*-
# Auto-generated PyInstaller spec file for {spec_name}
# Generated by generate_spec.py
# Do not edit manually - regenerate using: python generate_spec.py

import sys
import os
sys.setrecursionlimit(5000)

block_cipher = None

# Add the 'src' directory to the path for PyInstaller to find modules
# Use SPECPATH, the reliable path to the spec file provided by PyInstaller
spec_dir = os.path.dirname(os.path.abspath(SPECPATH))
src_path = os.path.join(spec_dir, 'src')

# --- Start of Conda/Mamba environment fix ---
# PyInstaller sometimes struggles to find DLLs in Conda environments.
# We explicitly add the environment's library paths to the search path.
conda_env_path = sys.prefix
conda_libs_path = os.path.join(conda_env_path, 'Library', 'bin')
pathex_paths = [src_path, conda_env_path, conda_libs_path]
# --- End of Conda/Mamba environment fix ---

a = Analysis(
    ['{entry_point_str}'],
    pathex=pathex_paths,  # Use the extended search path
    binaries=[
        {binaries_str}
    ],
    datas=[
        {data_str}
    ],
    hiddenimports=[
        {hidden_imports_str}
    ],
    hookspath=[],
    hooksconfig={{}},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
'''

    if onefile:
        spec_content += f'''
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='{spec_name}',
    debug={bool(debug)},
    bootloader_ignore_signals=False,
    strip={bool(strip_binaries)},
    upx=True,
    console={bool(console)},
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon={icon_str},
)
'''
    else:
        spec_content += f'''
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='{spec_name}',
    debug={bool(debug)},
    bootloader_ignore_signals=False,
    strip={bool(strip_binaries)},
    upx=True,
    console={bool(console)},
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon={icon_str},
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip={bool(strip_binaries)},
    upx=True,
    upx_exclude=[],
    name='{spec_name}',
)
'''
    
    return spec_content.strip()


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description="Generate PyInstaller spec file for Kontextrument",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python generate_spec.py
  python generate_spec.py --output mycustom.spec
  python generate_spec.py --debug --console --onefolder
  python generate_spec.py --strip    # Force stripping (smaller size)
  python generate_spec.py --no-strip # Disable stripping (better debugging)
        """
    )
    
    parser.add_argument(
        "--output", "-o",
        default="kontextrument.spec",
        help="Output filename for the spec file (default: kontextrument.spec)"
    )
    
    parser.add_argument(
        "--entry-point", "-e",
        default=None,
        help="Entry point script (default: auto-detect from src/ktr_runner.py or similar)"
    )
    
    parser.add_argument(
        "--console", "-c",
        type=lambda x: str(x).lower() in ("true", "1", "yes"),
        default=False,
        help="Show console window (True/False, default: False)"
    )
    
    parser.add_argument(
        "--debug", "-d",
        action="store_true",
        help="Enable debug mode in the generated spec file (default: False)"
    )
    
    parser.add_argument(
        "--name", "-n",
        default="ktr",
        help="Name of the output executable (default: ktr)"
    )
    
    parser.add_argument(
        "--onefolder", "-f",
        action="store_true",
        help="Create one-folder distribution instead of one-file (default: one-file)"
    )
    
    strip_group = parser.add_mutually_exclusive_group()
    strip_group.add_argument(
        "--strip",
        action="store_true",
        dest="strip_binaries",
        default=None,
        help="Strip debug symbols from binaries (reduces size, enabled by default on Linux)"
    )
    strip_group.add_argument(
        "--no-strip",
        action="store_false",
        dest="strip_binaries",
        help="Don't strip debug symbols (better for debugging, default on Windows/macOS)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print detailed information during generation"
    )
    
    args = parser.parse_args()
    
    try:
        if args.verbose:
            print("-" * 60)
            print("PyInstaller Spec File Generator for Kontextrument")
            print("-" * 60)
            print(f"Project root: {get_project_root()}")
            print(f"Platform: {sys.platform}")
            
            if args.entry_point:
                print(f"Entry point (specified): {args.entry_point}")
            else:
                entry_point = find_entry_point()
                if entry_point:
                    print(f"Entry point (auto-detected): {entry_point}")
                else:
                    print("Entry point: Not found (will fail)")
            
            print(f"Output file: {args.output}")
            print(f"Executable name: {args.name}")
            print(f"Console mode: {args.console}")
            print(f"Debug mode: {args.debug}")
            print(f"Build type: {'one-folder' if args.onefolder else 'one-file'}")
            
            if args.strip_binaries is None:
                strip_auto = sys.platform.startswith('linux')
                print(f"Strip binaries: {strip_auto} (auto-detected for {sys.platform})")
            else:
                print(f"Strip binaries: {args.strip_binaries} (user-specified)")
            
            print("-" * 60)
            print("Components:")
            print(f"  Data files: {len(find_data_files())} files")
            print(f"  Hidden imports: {len(find_hidden_imports())} modules")
            
            wx_loader = find_wx_loader_dll()
            if wx_loader:
                print(f"  wx Loader DLL: Found at {wx_loader[0]}")
            else:
                print("  wx Loader DLL: Not found (may cause issues on Windows)")
            
            print("-" * 60)
        
        spec_content = generate_spec_content(
            spec_name=args.name,
            entry_point=args.entry_point,
            console=args.console,
            debug=args.debug,
            onefile=not args.onefolder,
            strip_binaries=args.strip_binaries
        )
        
        output_path = get_project_root() / args.output
        output_path.write_text(spec_content, encoding="utf-8")
        
        print(f"✓ Successfully generated: {output_path}")
        print(f"\nTo build the executable, run:")
        print(f"  pyinstaller {output_path}")
        
        if args.verbose:
            print("-" * 60)
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
