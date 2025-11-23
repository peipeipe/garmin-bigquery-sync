#!/usr/bin/env python3
"""
Wrapper for garmindb_cli.py that ensures stats parameter is never None.

This wrapper prevents TypeError that occurs when garmindb_cli.py is called
without any statistics arguments (--activities, --monitoring, etc.), which
would cause the stats parameter to be None and fail when using 'in' operator.
"""

import sys
import subprocess


def main():
    """
    Wrapper that ensures garmindb_cli.py is called with appropriate arguments.
    
    If no statistics arguments are provided, defaults to --all to ensure
    stats is not None.
    """
    # Get all command line arguments
    args = sys.argv[1:]
    
    # Statistics flags that can be passed to garmindb_cli.py
    stats_flags = {'-A', '--all', '-a', '--activities', '-m', '--monitoring', 
                   '-r', '--rhr', '-s', '--sleep', '-w', '--weight'}
    
    # Check if any statistics flags are present
    has_stats_flag = any(arg in stats_flags for arg in args)
    
    # If no statistics flags are provided, add --all to prevent None stats
    if not has_stats_flag:
        # Check if we're doing operations that require stats
        # (download, copy, import, delete_db, rebuild_db)
        operations_needing_stats = {'-d', '--download', '-c', '--copy', 
                                   '-i', '--import', '--delete_db', '--rebuild_db'}
        has_operation = any(arg in operations_needing_stats for arg in args)
        
        if has_operation:
            print("INFO: No statistics flags provided, adding --all to prevent TypeError")
            args.append('--all')
    
    # Call the actual garmindb_cli.py with the modified arguments
    try:
        cmd = ['garmindb_cli.py'] + args
        result = subprocess.run(cmd, check=False)
        sys.exit(result.returncode)
    except FileNotFoundError:
        print("ERROR: garmindb_cli.py not found. Please ensure garmindb is installed.")
        print("Install with: pip install garmindb")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to execute garmindb_cli.py: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
