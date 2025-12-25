#!/usr/bin/env python3
"""Debug script to check schema differences across years."""

import sqlite3
from pathlib import Path
import pandas as pd

def get_db_dir():
    home = Path.home()
    for db_dir in [home / 'HealthData' / 'DBs', home / '.GarminDb']:
        if db_dir.exists():
            return db_dir
    raise FileNotFoundError("DB directory not found")

def check_table_schema(db_path, table_name, years=[2015, 2018, 2021, 2024]):
    """Check schema for specific years."""
    conn = sqlite3.connect(str(db_path))

    print(f"\n{'='*60}")
    print(f"Table: {table_name} (from {db_path.name})")
    print(f"{'='*60}")

    # Get all data first to see overall schema
    df_all = pd.read_sql_query(f"SELECT * FROM {table_name} LIMIT 5", conn)
    print(f"\nOverall dtypes (first 5 rows):")
    print(df_all.dtypes)
    print(f"\nSample data:")
    print(df_all.head(2).to_string())

    # Check date/time columns for different years
    date_col = 'day' if 'day' in df_all.columns else 'timestamp' if 'timestamp' in df_all.columns else None

    if date_col:
        print(f"\n--- Checking '{date_col}' column across years ---")
        for year in years:
            try:
                if date_col == 'day':
                    query = f"SELECT * FROM {table_name} WHERE day LIKE '{year}%' LIMIT 3"
                else:
                    query = f"SELECT * FROM {table_name} WHERE timestamp LIKE '{year}%' LIMIT 3"

                df_year = pd.read_sql_query(query, conn)
                if not df_year.empty:
                    print(f"\nYear {year}: {len(df_year)} sample rows")
                    print(f"  {date_col} values: {df_year[date_col].tolist()}")
                    print(f"  {date_col} dtype: {df_year[date_col].dtype}")
                    # Check for None/NULL values
                    null_count = df_year[date_col].isna().sum()
                    if null_count > 0:
                        print(f"  NULL values: {null_count}")
                else:
                    print(f"\nYear {year}: No data")
            except Exception as e:
                print(f"\nYear {year}: Error - {e}")

    conn.close()

def main():
    db_dir = get_db_dir()
    print(f"Database directory: {db_dir}")

    # Tables and their DB files
    tables = {
        'daily_summary': 'garmin.db',
        'activities': 'garmin_activities.db',
        'sleep': 'garmin.db',
        'stress': 'garmin.db',
    }

    for table, db_file in tables.items():
        db_path = db_dir / db_file
        if db_path.exists():
            try:
                check_table_schema(db_path, table)
            except Exception as e:
                print(f"Error checking {table}: {e}")
        else:
            print(f"DB file not found: {db_path}")

if __name__ == '__main__':
    main()
