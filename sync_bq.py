#!/usr/bin/env python3
"""
Sync GarminDB SQLite data to Google BigQuery.

This script reads tables from the GarminDB SQLite database and uploads them
to Google BigQuery using pandas and pandas-gbq.

Configuration is via environment variables:
- GCP_PROJECT_ID: Google Cloud Project ID (required)
- DATASET_ID: BigQuery dataset name (default: 'garmin_data')
"""

import os
import re
import sqlite3
import sys
from pathlib import Path

import pandas as pd
from pandas_gbq import to_gbq


def get_db_path():
    """Get the path to the GarminDB SQLite database."""
    home = Path.home()
    db_path = home / '.GarminDb' / 'garmin.db'
    
    if not db_path.exists():
        raise FileNotFoundError(
            f"GarminDB database not found at {db_path}. "
            "Please run garmindb_cli.py first to create the database."
        )
    
    return str(db_path)


def validate_table_name(table_name):
    """
    Validate table name to prevent SQL injection.
    Only allows alphanumeric characters and underscores.
    """
    if not re.match(r'^[a-zA-Z0-9_]+$', table_name):
        raise ValueError(f"Invalid table name: {table_name}")
    return table_name


def check_table_exists(cursor, table_name):
    """Check if a table exists in the SQLite database."""
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    return cursor.fetchone() is not None


def sync_table_to_bigquery(conn, table_name, project_id, dataset_id):
    """
    Read a table from SQLite and upload to BigQuery.
    
    Args:
        conn: SQLite connection object
        table_name: Name of the table to sync
        project_id: GCP project ID
        dataset_id: BigQuery dataset ID
    """
    print(f"Processing table: {table_name}")
    
    # Validate table name to prevent SQL injection
    validated_table_name = validate_table_name(table_name)
    
    cursor = conn.cursor()
    if not check_table_exists(cursor, validated_table_name):
        print(f"  ⚠️  Table '{validated_table_name}' not found in database. Skipping.")
        return
    
    # Read table from SQLite - use parameterized query via pandas
    try:
        # Using pandas read_sql_query with table name validation above
        # The table name has been validated to contain only safe characters
        df = pd.read_sql_query(f"SELECT * FROM {validated_table_name}", conn)
        
        if df.empty:
            print(f"  ⚠️  Table '{validated_table_name}' is empty. Skipping.")
            return
        
        print(f"  📊 Read {len(df)} rows from {validated_table_name}")
        
        # Upload to BigQuery
        # Note: Using 'replace' for simplicity. For large datasets or incremental
        # updates, consider using 'append' with proper deduplication logic.
        destination_table = f"{dataset_id}.{validated_table_name}"
        
        to_gbq(
            df,
            destination_table=destination_table,
            project_id=project_id,
            if_exists='replace',
            progress_bar=False
        )
        
        print(f"  ✅ Uploaded {len(df)} rows to {project_id}.{destination_table}")
        
    except Exception as e:
        print(f"  ❌ Error syncing table '{table_name}': {e}")
        raise


def main():
    """Main function to sync GarminDB to BigQuery."""
    # Get configuration from environment variables
    project_id = os.getenv('GCP_PROJECT_ID')
    dataset_id = os.getenv('DATASET_ID', 'garmin_data')
    
    if not project_id:
        print("Error: GCP_PROJECT_ID environment variable is required")
        sys.exit(1)
    
    print(f"🚀 Starting sync to BigQuery")
    print(f"   Project: {project_id}")
    print(f"   Dataset: {dataset_id}")
    print()
    
    # Connect to SQLite database
    try:
        db_path = get_db_path()
        print(f"📂 Connecting to database: {db_path}")
        conn = sqlite3.connect(db_path)
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        sys.exit(1)
    
    # Tables to sync (add more as needed)
    tables_to_sync = [
        'daily_summary',
        'activities',
        'sleep'
    ]
    
    print(f"📋 Tables to sync: {', '.join(tables_to_sync)}")
    print()
    
    # Sync each table
    success_count = 0
    failed_count = 0
    
    for table_name in tables_to_sync:
        try:
            sync_table_to_bigquery(conn, table_name, project_id, dataset_id)
            success_count += 1
        except Exception as e:
            print(f"Failed to sync {table_name}: {e}")
            failed_count += 1
    
    conn.close()
    
    print()
    print(f"✨ Sync complete!")
    print(f"   Success: {success_count}/{len(tables_to_sync)}")
    print(f"   Failed: {failed_count}/{len(tables_to_sync)}")
    
    if failed_count > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
