#!/usr/bin/env python3
"""Delete BigQuery tables to allow schema recreation."""

import os
import sys
from google.cloud import bigquery

TABLES = [
    'daily_summary',
    'activities',
    'sleep',
    'stress',
    'weight',
    'resting_hr',
]

def main():
    project_id = os.getenv('GCP_PROJECT_ID')
    dataset_id = os.getenv('DATASET_ID', 'garmin_data')

    if not project_id:
        print("Error: GCP_PROJECT_ID required")
        sys.exit(1)

    client = bigquery.Client(project=project_id)

    print(f"Deleting tables from {project_id}.{dataset_id}")

    for table_name in TABLES:
        table_id = f"{project_id}.{dataset_id}.{table_name}"
        try:
            client.delete_table(table_id, not_found_ok=True)
            print(f"  ✅ Deleted {table_name}")
        except Exception as e:
            print(f"  ❌ Failed to delete {table_name}: {e}")

    print("\nDone! Run full_refresh to recreate tables with correct schema.")

if __name__ == '__main__':
    main()
