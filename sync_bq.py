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
from google.cloud import bigquery
from google.api_core import exceptions as google_exceptions


# Schema definitions for common GarminDB tables
# Used to create empty tables when no data exists yet
TABLE_SCHEMAS = {
    'daily_summary': [
        bigquery.SchemaField("day", "DATE"),
        bigquery.SchemaField("hr_min", "INTEGER"),
        bigquery.SchemaField("hr_avg", "FLOAT"),
        bigquery.SchemaField("hr_max", "INTEGER"),
        bigquery.SchemaField("rhr", "INTEGER"),
        bigquery.SchemaField("stress_avg", "INTEGER"),
        bigquery.SchemaField("step_goal", "INTEGER"),
        bigquery.SchemaField("steps", "INTEGER"),
        bigquery.SchemaField("moderate_activity_time", "INTEGER"),
        bigquery.SchemaField("vigorous_activity_time", "INTEGER"),
        bigquery.SchemaField("intensity_time", "INTEGER"),
        bigquery.SchemaField("floors_up", "FLOAT"),
        bigquery.SchemaField("floors_down", "FLOAT"),
        bigquery.SchemaField("distance", "FLOAT"),
        bigquery.SchemaField("calories_goal", "INTEGER"),
        bigquery.SchemaField("calories_total", "INTEGER"),
        bigquery.SchemaField("calories_bmr", "INTEGER"),
        bigquery.SchemaField("calories_active", "INTEGER"),
        bigquery.SchemaField("activities", "INTEGER"),
        bigquery.SchemaField("activities_distance", "FLOAT"),
        bigquery.SchemaField("hydration_goal", "INTEGER"),
        bigquery.SchemaField("hydration_intake", "INTEGER"),
        bigquery.SchemaField("sweat_loss", "INTEGER"),
        bigquery.SchemaField("spo2_avg", "FLOAT"),
        bigquery.SchemaField("spo2_min", "FLOAT"),
        bigquery.SchemaField("rr_waking_avg", "FLOAT"),
        bigquery.SchemaField("rr_max", "FLOAT"),
        bigquery.SchemaField("rr_min", "FLOAT"),
        bigquery.SchemaField("bb_charged", "FLOAT"),
        bigquery.SchemaField("bb_max", "FLOAT"),
        bigquery.SchemaField("bb_min", "FLOAT"),
        bigquery.SchemaField("description", "STRING"),
    ],
    'activities': [
        bigquery.SchemaField("activity_id", "STRING"),
        bigquery.SchemaField("name", "STRING"),
        bigquery.SchemaField("description", "STRING"),
        bigquery.SchemaField("type", "STRING"),
        bigquery.SchemaField("sport", "STRING"),
        bigquery.SchemaField("sub_sport", "STRING"),
        bigquery.SchemaField("start_time", "TIMESTAMP"),
        bigquery.SchemaField("stop_time", "TIMESTAMP"),
        bigquery.SchemaField("elapsed_time", "FLOAT"),
        bigquery.SchemaField("moving_time", "FLOAT"),
        bigquery.SchemaField("distance", "FLOAT"),
        bigquery.SchemaField("calories", "INTEGER"),
        bigquery.SchemaField("hr_avg", "INTEGER"),
        bigquery.SchemaField("hr_max", "INTEGER"),
        bigquery.SchemaField("speed_avg", "FLOAT"),
        bigquery.SchemaField("speed_max", "FLOAT"),
        bigquery.SchemaField("cadence_avg", "FLOAT"),
        bigquery.SchemaField("cadence_max", "FLOAT"),
        bigquery.SchemaField("ascent", "FLOAT"),
        bigquery.SchemaField("descent", "FLOAT"),
    ],
    'sleep': [
        bigquery.SchemaField("day", "DATE"),
        bigquery.SchemaField("start", "TIMESTAMP"),
        bigquery.SchemaField("end", "TIMESTAMP"),
        bigquery.SchemaField("total_sleep", "FLOAT"),
        bigquery.SchemaField("deep_sleep", "FLOAT"),
        bigquery.SchemaField("light_sleep", "FLOAT"),
        bigquery.SchemaField("rem_sleep", "FLOAT"),
        bigquery.SchemaField("awake", "FLOAT"),
        bigquery.SchemaField("avg_spo2", "FLOAT"),
        bigquery.SchemaField("avg_rr", "FLOAT"),
        bigquery.SchemaField("avg_hr", "FLOAT"),
    ],
}


def ensure_dataset_exists(client, project_id, dataset_id):
    """
    Ensure BigQuery dataset exists, create if not.
    
    Args:
        client: BigQuery client instance
        project_id: GCP project ID
        dataset_id: BigQuery dataset ID
    """
    dataset_ref = f"{project_id}.{dataset_id}"
    
    try:
        client.get_dataset(dataset_ref)
        print(f"  ✓ Dataset {dataset_ref} already exists")
    except google_exceptions.NotFound:
        print(f"  Creating dataset {dataset_ref}...")
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "US"  # You can make this configurable if needed
        client.create_dataset(dataset, timeout=30)
        print(f"  ✓ Dataset {dataset_ref} created")
    except Exception as e:
        print(f"  ⚠️  Error checking/creating dataset: {e}")
        raise


def get_db_path():
    """
    Get the path to the GarminDB SQLite database.
    
    Returns:
        str: Path to the database file
        
    Raises:
        FileNotFoundError: If the database doesn't exist with helpful error message
    """
    home = Path.home()
    db_dir = home / '.GarminDb'
    db_path = db_dir / 'garmin.db'
    
    if not db_path.exists():
        # Check if the directory exists
        if not db_dir.exists():
            raise FileNotFoundError(
                f"GarminDB directory not found at {db_dir}. "
                "This is likely the first run. Please ensure the 'Import Garmin data' "
                "step in the workflow completed successfully to create the database."
            )
        
        # Directory exists but no database file
        raise FileNotFoundError(
            f"GarminDB database not found at {db_path}. "
            "The database directory exists but the database file hasn't been created yet. "
            "This may be because:\n"
            "  1. This is the first run and data import hasn't completed\n"
            "  2. The import step failed (check workflow logs)\n"
            "  3. No data has been downloaded from Garmin Connect yet\n"
            "\n"
            "To create the database, run: python garmindb_wrapper.py --download --import --analyze --latest --all"
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


def sync_table_to_bigquery(conn, table_name, project_id, dataset_id, client):
    """
    Read a table from SQLite and upload to BigQuery.
    Creates empty table if no data exists to allow users to see schema.
    
    Args:
        conn: SQLite connection object
        table_name: Name of the table to sync
        project_id: GCP project ID
        dataset_id: BigQuery dataset ID
        client: BigQuery client instance
        
    Returns:
        int: Number of rows synced (0 if table is empty or doesn't exist)
    """
    print(f"Processing table: {table_name}")
    
    # Validate table name to prevent SQL injection
    validated_table_name = validate_table_name(table_name)
    
    cursor = conn.cursor()
    if not check_table_exists(cursor, validated_table_name):
        print(f"  ⚠️  Table '{validated_table_name}' not found in SQLite database. Skipping.")
        return 0
    
    # Read table from SQLite - use parameterized query via pandas
    try:
        # Using pandas read_sql_query with table name validation above
        # The table name has been validated to contain only safe characters
        df = pd.read_sql_query(f"SELECT * FROM {validated_table_name}", conn)
        
        destination_table = f"{dataset_id}.{validated_table_name}"
        row_count = len(df)
        
        if df.empty:
            print(f"  ⚠️  Table '{validated_table_name}' is empty in SQLite")
            # Create empty table in BigQuery with schema if available
            if validated_table_name in TABLE_SCHEMAS:
                print(f"  📋 Creating empty table with predefined schema in BigQuery...")
                try:
                    table_ref = f"{project_id}.{destination_table}"
                    schema = TABLE_SCHEMAS[validated_table_name]
                    table = bigquery.Table(table_ref, schema=schema)
                    client.create_table(table, exists_ok=True)
                    print(f"  ✓ Empty table created/verified at {project_id}.{destination_table}")
                except Exception as e:
                    print(f"  ⚠️  Failed to create empty table: {type(e).__name__}: {e}")
            else:
                print(f"  ℹ️  No predefined schema available for {validated_table_name}, skipping empty table creation")
            return 0
        
        print(f"  📊 Read {row_count} rows from {validated_table_name}")
        
        # Upload to BigQuery using append mode
        # This allows incremental updates and preserves historical data
        try:
            to_gbq(
                df,
                destination_table=destination_table,
                project_id=project_id,
                if_exists='append',
                progress_bar=False
            )
            
            print(f"  ✅ Uploaded {row_count} rows to {project_id}.{destination_table}")
            
            # Try to get job information for debugging
            try:
                table_ref = f"{project_id}.{destination_table}"
                table = client.get_table(table_ref)
                print(f"  ℹ️  Table now has {table.num_rows} total rows")
            except Exception:
                # Don't fail if we can't get table info
                pass
                
            return row_count
            
        except Exception as e:
            print(f"  ❌ Error uploading to BigQuery for table '{table_name}': {type(e).__name__}: {e}")
            raise
        
    except Exception as e:
        print(f"  ❌ Error syncing table '{table_name}' at reading stage: {type(e).__name__}: {e}")
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
    
    # Initialize BigQuery client
    try:
        client = bigquery.Client(project=project_id)
        print(f"✓ BigQuery client initialized")
    except Exception as e:
        print(f"❌ Failed to initialize BigQuery client: {type(e).__name__}: {e}")
        sys.exit(1)
    
    # Ensure dataset exists
    try:
        ensure_dataset_exists(client, project_id, dataset_id)
    except Exception as e:
        print(f"❌ Failed to ensure dataset exists: {e}")
        sys.exit(1)
    
    # Connect to SQLite database
    try:
        db_path = get_db_path()
        print(f"📂 Connecting to database: {db_path}")
        conn = sqlite3.connect(db_path)
    except Exception as e:
        print(f"❌ Failed to connect to database: {type(e).__name__}: {e}")
        sys.exit(1)
    
    # Tables to sync (add more as needed)
    tables_to_sync = [
        'daily_summary',
        'activities',
        'sleep'
    ]
    
    print(f"📋 Tables to sync: {', '.join(tables_to_sync)}")
    print()
    
    # Sync each table and track statistics
    success_count = 0
    failed_count = 0
    total_rows = 0
    table_row_counts = {}
    
    for table_name in tables_to_sync:
        try:
            rows_synced = sync_table_to_bigquery(conn, table_name, project_id, dataset_id, client)
            table_row_counts[table_name] = rows_synced
            total_rows += rows_synced
            success_count += 1
        except Exception as e:
            print(f"Failed to sync {table_name}: {type(e).__name__}: {e}")
            table_row_counts[table_name] = 0
            failed_count += 1
    
    conn.close()
    
    print()
    print(f"=" * 60)
    print(f"✨ Sync Summary")
    print(f"=" * 60)
    print(f"Project: {project_id}")
    print(f"Dataset: {dataset_id}")
    print()
    print(f"Table Row Counts:")
    for table_name, row_count in table_row_counts.items():
        status_icon = "✅" if row_count > 0 else "⚪"
        print(f"  {status_icon} {table_name}: {row_count:,} rows")
    print()
    print(f"Total rows synced: {total_rows:,}")
    print(f"Tables processed: {success_count}/{len(tables_to_sync)}")
    print(f"Failed: {failed_count}/{len(tables_to_sync)}")
    print(f"=" * 60)
    
    if failed_count > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
