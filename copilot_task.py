#!/usr/bin/env python3
"""
Copilot Task Runner for Sherlock
Allows running Sherlock commands and tests within GitHub Copilot context
"""

import subprocess
import sys
import json
from pathlib import Path
from typing import Optional

def run_command(cmd: list, description: str = "") -> tuple[int, str, str]:
    """Run a shell command and return status, stdout, stderr"""
    print(f"📍 Running: {' '.join(cmd)}")
    if description:
        print(f"   {description}")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr

def install_sherlock() -> bool:
    """Install Sherlock in development mode"""
    print("🔧 Installing Sherlock...")
    code, stdout, stderr = run_command(
        [sys.executable, "-m", "pip", "install", "-e", "."],
        "Installing from local directory in editable mode"
    )
    
    if code == 0:
        print("✅ Sherlock installed successfully")
        return True
    else:
        print(f"❌ Installation failed:\n{stderr}")
        return False

def verify_installation() -> bool:
    """Verify Sherlock is installed and working"""
    print("🧪 Verifying installation...")
    code, stdout, stderr = run_command(
        ["sherlock", "--version"],
        "Checking Sherlock version"
    )
    
    if code == 0:
        print(f"✅ {stdout.strip()}")
        return True
    else:
        print(f"❌ Verification failed:\n{stderr}")
        return False

def run_tests(test_file: Optional[str] = None, verbose: bool = False) -> bool:
    """Run pytest tests"""
    print("🧪 Running tests...")
    cmd = [sys.executable, "-m", "pytest"]
    
    if test_file:
        cmd.append(f"tests/{test_file}")
    else:
        cmd.append("tests/")
    
    if verbose:
        cmd.append("-v")
    
    cmd.append("--tb=short")
    
    code, stdout, stderr = run_command(cmd, "Running pytest suite")
    
    print(stdout)
    if stderr:
        print(f"Warnings:\n{stderr}")
    
    return code == 0

def run_sherlock_search(usernames: list, options: Optional[dict] = None) -> bool:
    """Run a Sherlock username search"""
    print(f"🔍 Searching for usernames: {', '.join(usernames)}")
    
    cmd = ["sherlock"] + usernames
    
    if options:
        if options.get("csv"):
            cmd.append("--csv")
        if options.get("verbose"):
            cmd.append("--verbose")
        if options.get("print_all"):
            cmd.append("--print-all")
        if options.get("sites"):
            for site in options["sites"]:
                cmd.extend(["--site", site])
    
    code, stdout, stderr = run_command(cmd, f"Searching {len(usernames)} username(s)")
    
    print(stdout)
    if stderr:
        print(f"Errors:\n{stderr}")
    
    return code == 0

def main():
    """Main entry point for Copilot task"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Copilot Task Runner for Sherlock",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 copilot_task.py install              # Install Sherlock
  python3 copilot_task.py verify               # Verify installation
  python3 copilot_task.py test                 # Run all tests
  python3 copilot_task.py test test_probes.py  # Run specific test
  python3 copilot_task.py search alice bob     # Search for usernames
  python3 copilot_task.py search alice --csv   # Search with CSV export
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Install command
    subparsers.add_parser("install", help="Install Sherlock")
    
    # Verify command
    subparsers.add_parser("verify", help="Verify Sherlock installation")
    
    # Test command
    test_parser = subparsers.add_parser("test", help="Run tests")
    test_parser.add_argument("test_file", nargs="?", help="Specific test file to run")
    test_parser.add_argument("-v", "--verbose", action="store_true", help="Verbose output")
    
    # Search command
    search_parser = subparsers.add_parser("search", help="Run Sherlock search")
    search_parser.add_argument("usernames", nargs="+", help="Usernames to search for")
    search_parser.add_argument("--csv", action="store_true", help="Export to CSV")
    search_parser.add_argument("--verbose", action="store_true", help="Verbose output")
    search_parser.add_argument("--print-all", action="store_true", help="Print all results")
    search_parser.add_argument("--sites", nargs="+", help="Specific sites to search")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    print("🔍 Sherlock - Copilot Task Runner")
    print("=" * 50)
    print()
    
    try:
        if args.command == "install":
            return 0 if install_sherlock() else 1
        
        elif args.command == "verify":
            return 0 if verify_installation() else 1
        
        elif args.command == "test":
            return 0 if run_tests(
                test_file=args.test_file,
                verbose=args.verbose
            ) else 1
        
        elif args.command == "search":
            options = {
                "csv": args.csv,
                "verbose": args.verbose,
                "print_all": args.print_all,
                "sites": args.sites,
            }
            return 0 if run_sherlock_search(args.usernames, options) else 1
    
    except KeyboardInterrupt:
        print("\n⚠️  Task interrupted by user")
        return 1
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
