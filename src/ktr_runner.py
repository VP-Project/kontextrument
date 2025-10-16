#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
CLI Runner for Kontextrument
----------------------------
Provides a unified command-line interface to:
- Launch the graphical user interface (via 'gui' command)
- Create context files from the command line (via 'create' command)
- Apply context files from the command line (via 'apply' command)

This script launches the appropriate tool based on the command-line arguments.
"""

import argparse
import sys
import os
import traceback

class ContextToolsRunner:
    """Main class for parsing CLI arguments and running Kontextrument tools."""
    
    def __init__(self):
        """Initialize the runner and check for available modules."""
        self.gui_import_error = None
        self.debug = False
        self._check_module_availability()
        self._setup_windows_dpi()
    
    def _check_module_availability(self):
        """Check which modules are available for import."""
        try:
            from ktr import create_context
            self.create_context = create_context
            self.create_context_available = True
        except ImportError:
            self.create_context_available = False
        
        try:
            from ktr import apply_context
            self.apply_context = apply_context
            self.apply_context_available = True
        except ImportError:
            self.apply_context_available = False
        
        try:
            import ktr_gui_wx
            self.unified_gui_wx_available = True
        except Exception as e:
            self.unified_gui_wx_available = False
            self.gui_import_error = e

        try:
            from ktr.__version__ import version
            self._version = version
        except ImportError:
            self._version = "N/A"
            
    def _setup_windows_dpi(self):
        """Setup Windows DPI awareness if available."""
        if sys.platform == "win32":
            try:
                from ctypes import windll
                windll.shcore.SetProcessDpiAwareness(2)
            except (ImportError, AttributeError):
                pass
    
    def handle_gui_command(self, args, remaining_cli_args):
        """Handle the 'gui' command by launching the application."""
        initial_directory = None
        if remaining_cli_args:
            potential_dir = remaining_cli_args[0]
            if os.path.isdir(potential_dir):
                initial_directory = os.path.abspath(potential_dir)
            else:
                print(f"Warning: '{potential_dir}' is not a valid directory. Ignoring.", file=sys.stderr)
        
        self._run_unified_gui(initial_directory=initial_directory)

    def handle_create_command(self, args, remaining_cli_args):
        """Handle the 'create' command by running the CLI tool."""
        self._run_create_context_cli(remaining_cli_args)
    
    def handle_apply_command(self, args, remaining_cli_args):
        """Handle the 'apply' command by running the CLI tool."""
        self._run_apply_context_cli(remaining_cli_args)
    
    def _run_create_context_cli(self, cli_args):
        """Run the create_context.py CLI script."""
        if not self.create_context_available:
            print("Error: create_context.py not found.", file=sys.stderr)
            sys.exit(1)
        
        original_sys_argv = list(sys.argv)
        sys.argv = [os.path.basename(self.create_context.__file__)] + cli_args
        try:
            self.create_context.main_cli()
        except SystemExit as e:
            sys.exit(e.code)
        finally:
            sys.argv = original_sys_argv
    
    def _run_apply_context_cli(self, cli_args):
        """Run the apply_context.py CLI script."""
        if not self.apply_context_available:
            print("Error: apply_context.py not found.", file=sys.stderr)
            sys.exit(1)
        
        original_sys_argv = list(sys.argv)
        sys.argv = [os.path.basename(self.apply_context.__file__)] + cli_args
        try:
            self.apply_context.main_cli()
        except SystemExit as e:
            sys.exit(e.code)
        finally:
            sys.argv = original_sys_argv
    
    def _run_unified_gui(self, initial_directory=None):
        """Run the unified wxPython GUI."""
        if not self.unified_gui_wx_available:
            print("="*60, file=sys.stderr)
            print("ERROR: Failed to import the GUI module.", file=sys.stderr)
            if self.gui_import_error:
                print(f"({type(self.gui_import_error).__name__}) {self.gui_import_error}", file=sys.stderr)
                
                if self.debug:
                    print("\nTRACEBACK:", file=sys.stderr)
                    traceback.print_exception(
                        type(self.gui_import_error), 
                        self.gui_import_error, 
                        self.gui_import_error.__traceback__,
                        file=sys.stderr
                    )
                else:
                    print(f"\nRun with '-d' or '--debug' for a full traceback.", file=sys.stderr)
            else:
                print("\nAn unknown import error occurred.", file=sys.stderr)
            print("="*60, file=sys.stderr)
            sys.exit(1)

        print("Launching unified GUI...")
        if initial_directory:
            print(f"Opening with directory: {initial_directory}")
        
        try:
            from ktr_gui_wx import run
            run(initial_directory=initial_directory)
        except Exception as e:
            print("="*60, file=sys.stderr)
            print("ERROR: An unexpected error occurred while creating the GUI.", file=sys.stderr)
            print(f"\nError Details: ({type(e).__name__}) {e}", file=sys.stderr)
            if self.debug:
                print("\nDetailed traceback:", file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
            print("="*60, file=sys.stderr)
            sys.exit(1)

    def _create_parser(self):
        """Create and configure the argument parser."""
        parser = argparse.ArgumentParser(
            description=f"CLI Runner for Kontextrument.\nVersion: {self._version}",
            formatter_class=argparse.RawDescriptionHelpFormatter,
            epilog="""
Examples:
  %(prog)s gui                    (Launch the graphical user interface)
  %(prog)s gui -d /path/to/dir     (Launch GUI in debug mode)
  %(prog)s gui /path/to/dir       (Launch GUI with specified working directory)
  %(prog)s create -v .            (Create context file for the current directory)
  %(prog)s apply file.md          (Apply a context file to the current directory)
"""
        )
        
        parser.add_argument(
            '-d', '--debug',
            action='store_true',
            help='Show detailed traceback on errors.'
        )
        
        subparsers = parser.add_subparsers(title="Available commands", dest="command", metavar="COMMAND", required=False)
        
        parser_gui = subparsers.add_parser("gui", help="Launch the unified graphical user interface.")
        parser_gui.set_defaults(func=self.handle_gui_command)

        parser_create = subparsers.add_parser("create", help="Create a context file via the command line.", add_help=False)
        parser_create.set_defaults(func=self.handle_create_command)
        
        parser_apply = subparsers.add_parser("apply", help="Apply a context file via the command line.", add_help=False)
        parser_apply.set_defaults(func=self.handle_apply_command)
        
        return parser
    
    def main_cli(self):
        """Main CLI entry point for the runner."""
        parser = self._create_parser()
        args, unknown_args = parser.parse_known_args()
        self.debug = args.debug
        
        if hasattr(args, 'func'):
            args.func(args, unknown_args)
        else:
            if self.unified_gui_wx_available:
                self._run_unified_gui()
            else:
                parser.print_help()
                sys.exit(0)

def main():
    """Entry point when script is run directly."""
    runner = ContextToolsRunner()
    runner.main_cli()

if __name__ == "__main__":
    main()