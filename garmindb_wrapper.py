#!/usr/bin/env python3
"""
Wrapper for garmindb_cli.py that ensures stats parameter is never None
and provides proper configuration defaults.

This wrapper prevents TypeError that occurs when garmindb_cli.py is called
without any statistics arguments (--activities, --monitoring, etc.), which
would cause the stats parameter to be None and fail when using 'in' operator.

It also ensures proper configuration is in place to avoid None-related errors
in date calculations and activity counts.
"""

import sys
import subprocess
import os
import json
from pathlib import Path


def ensure_config_exists():
    """
    Ensure GarminConnectConfig.json exists with sensible defaults.
    
    This prevents None values in activity counts and date calculations
    that would cause TypeErrors in garmindb_cli.py.
    """
    config_dir = Path.home() / '.GarminDb'
    config_file = config_dir / 'GarminConnectConfig.json'
    
    # Create directory if it doesn't exist
    config_dir.mkdir(parents=True, exist_ok=True)
    
    # Check if config exists and has required fields
    config_needs_update = False
    
    if config_file.exists():
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"WARNING: Failed to read config file: {e}")
            config = {}
            config_needs_update = True
    else:
        config = {}
        config_needs_update = True
    
    # Ensure 'data' section exists with required defaults
    if 'data' not in config:
        config['data'] = {}
        config_needs_update = True

    # Set defaults for fields that can cause None-related errors
    data_defaults = {
        'download_days': 3,  # Default to last 3 days
        'download_latest_activities': 10,  # Default to last 10 activities
        'download_all_activities': 100,  # Default to last 100 activities when not using --latest
    }

    for key, default_value in data_defaults.items():
        if key not in config['data'] or config['data'][key] is None:
            config['data'][key] = default_value
            config_needs_update = True
            print(f"INFO: Setting default {key}={default_value}")

    # Set date defaults for all stat types (required format: YYYY-MM-DD strings in 'data' section)
    # GarminDB expects: data.monitoring_start_date, data.monitoring_end_date, etc.
    from datetime import date, timedelta
    today = date.today()
    start_date = (today - timedelta(days=30)).isoformat()
    end_date = today.isoformat()

    stat_types = ['monitoring', 'activities', 'sleep', 'rhr', 'weight']
    for stat_type in stat_types:
        start_key = f'{stat_type}_start_date'
        end_key = f'{stat_type}_end_date'

        if start_key not in config['data'] or config['data'][start_key] is None:
            config['data'][start_key] = start_date
            config_needs_update = True
            print(f"INFO: Setting default {start_key}={start_date}")

        if end_key not in config['data'] or config['data'][end_key] is None:
            config['data'][end_key] = end_date
            config_needs_update = True
            print(f"INFO: Setting default {end_key}={end_date}")
    
    # Save updated config if needed
    if config_needs_update:
        try:
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            print(f"INFO: Updated config file: {config_file}")
        except IOError as e:
            print(f"WARNING: Failed to update config file: {e}")
    
    return config


def main():
    """
    Wrapper that ensures garmindb_cli.py is called with appropriate arguments.
    
    If no statistics arguments are provided, defaults to --all to ensure
    stats is not None.
    """
    # Ensure config exists with proper defaults before running garmindb_cli
    ensure_config_exists()
    
    # Get all command line arguments
    args = sys.argv[1:]
    
    # Statistics flags that can be passed to garmindb_cli.py
    # Note: -A (capital A) is for --all, -a (lowercase a) is for --activities
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
