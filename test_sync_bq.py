#!/usr/bin/env python3
"""
Tests for sync_bq.py to ensure proper BigQuery sync functionality,
empty table creation, and error handling.
"""

import unittest
import sqlite3
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

# Import functions from sync_bq
from sync_bq import (
    validate_table_name,
    check_table_exists,
    ensure_dataset_exists,
    TABLE_SCHEMAS
)


class TestValidateTableName(unittest.TestCase):
    """Test table name validation to prevent SQL injection."""
    
    def test_valid_table_names(self):
        """Test that valid table names pass validation."""
        valid_names = [
            'daily_summary',
            'activities',
            'sleep',
            'monitoring_hr',
            'test_table_123',
            'TABLE_NAME',
        ]
        for name in valid_names:
            with self.subTest(name=name):
                self.assertEqual(validate_table_name(name), name)
    
    def test_invalid_table_names(self):
        """Test that invalid table names raise ValueError."""
        invalid_names = [
            'table; DROP TABLE users;',
            'table name',  # space
            'table-name',  # hyphen
            'table.name',  # dot
            'table/name',  # slash
            "table'name",  # quote
            'table"name',  # double quote
            'table`name',  # backtick
        ]
        for name in invalid_names:
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    validate_table_name(name)


class TestCheckTableExists(unittest.TestCase):
    """Test SQLite table existence checking."""
    
    def setUp(self):
        """Create a temporary SQLite database for testing."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.conn = sqlite3.connect(self.temp_db.name)
        self.cursor = self.conn.cursor()
        
        # Create a test table
        self.cursor.execute('CREATE TABLE test_table (id INTEGER, name TEXT)')
        self.conn.commit()
    
    def tearDown(self):
        """Clean up temporary database."""
        self.conn.close()
        os.unlink(self.temp_db.name)
    
    def test_existing_table(self):
        """Test that existing table is detected."""
        self.assertTrue(check_table_exists(self.cursor, 'test_table'))
    
    def test_nonexistent_table(self):
        """Test that non-existent table is not detected."""
        self.assertFalse(check_table_exists(self.cursor, 'nonexistent_table'))


class TestTableSchemas(unittest.TestCase):
    """Test that table schemas are properly defined."""
    
    def test_schemas_exist(self):
        """Test that required table schemas are defined."""
        required_tables = ['daily_summary', 'activities', 'sleep']
        for table in required_tables:
            with self.subTest(table=table):
                self.assertIn(table, TABLE_SCHEMAS)
                self.assertIsInstance(TABLE_SCHEMAS[table], list)
                self.assertGreater(len(TABLE_SCHEMAS[table]), 0)
    
    def test_schema_fields_valid(self):
        """Test that schema fields have required attributes."""
        from google.cloud import bigquery
        
        for table_name, schema in TABLE_SCHEMAS.items():
            with self.subTest(table=table_name):
                for field in schema:
                    self.assertIsInstance(field, bigquery.SchemaField)
                    self.assertIsNotNone(field.name)
                    self.assertIsNotNone(field.field_type)


class TestEnsureDatasetExists(unittest.TestCase):
    """Test dataset creation functionality."""
    
    @patch('sync_bq.bigquery.Client')
    def test_dataset_already_exists(self, mock_client_class):
        """Test that existing dataset is not recreated."""
        mock_client = Mock()
        mock_client.get_dataset.return_value = Mock()  # Dataset exists
        
        ensure_dataset_exists(mock_client, 'test-project', 'test_dataset')
        
        # Should check for dataset
        mock_client.get_dataset.assert_called_once_with('test-project.test_dataset')
        # Should not create dataset
        mock_client.create_dataset.assert_not_called()
    
    @patch('sync_bq.bigquery.Client')
    def test_dataset_creation(self, mock_client_class):
        """Test that missing dataset is created."""
        from google.api_core import exceptions as google_exceptions
        
        mock_client = Mock()
        mock_client.get_dataset.side_effect = google_exceptions.NotFound('Dataset not found')
        
        ensure_dataset_exists(mock_client, 'test-project', 'test_dataset')
        
        # Should check for dataset
        mock_client.get_dataset.assert_called_once()
        # Should create dataset
        mock_client.create_dataset.assert_called_once()


class TestSyncTableToBigQuery(unittest.TestCase):
    """Test the main sync function."""
    
    def setUp(self):
        """Create a temporary SQLite database with test data."""
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
        self.temp_db.close()
        self.conn = sqlite3.connect(self.temp_db.name)
        self.cursor = self.conn.cursor()
        
        # Create a test table with data
        self.cursor.execute('''
            CREATE TABLE test_table (
                id INTEGER,
                name TEXT,
                value REAL
            )
        ''')
        self.cursor.execute('INSERT INTO test_table VALUES (1, "test1", 10.5)')
        self.cursor.execute('INSERT INTO test_table VALUES (2, "test2", 20.5)')
        self.conn.commit()
    
    def tearDown(self):
        """Clean up temporary database."""
        self.conn.close()
        os.unlink(self.temp_db.name)
    
    @patch('sync_bq.to_gbq')
    @patch('sync_bq.bigquery.Client')
    def test_sync_with_data(self, mock_client_class, mock_to_gbq):
        """Test syncing a table with data."""
        from sync_bq import sync_table_to_bigquery
        
        mock_client = Mock()
        mock_table = Mock()
        mock_table.num_rows = 2
        mock_client.get_table.return_value = mock_table
        
        result = sync_table_to_bigquery(
            self.conn, 
            'test_table', 
            'test-project', 
            'test_dataset',
            mock_client
        )
        
        # Should return 2 rows synced
        self.assertEqual(result, 2)
        # Should call to_gbq with append mode
        mock_to_gbq.assert_called_once()
        call_kwargs = mock_to_gbq.call_args[1]
        self.assertEqual(call_kwargs['if_exists'], 'append')
        self.assertEqual(call_kwargs['project_id'], 'test-project')
    
    @patch('sync_bq.bigquery.Client')
    def test_sync_nonexistent_table(self, mock_client_class):
        """Test syncing a table that doesn't exist."""
        from sync_bq import sync_table_to_bigquery
        
        mock_client = Mock()
        
        result = sync_table_to_bigquery(
            self.conn,
            'nonexistent_table',
            'test-project',
            'test_dataset',
            mock_client
        )
        
        # Should return 0 rows
        self.assertEqual(result, 0)


class TestIntegration(unittest.TestCase):
    """Integration tests for the sync process."""
    
    def test_imports(self):
        """Test that all required modules can be imported."""
        try:
            import pandas as pd
            from pandas_gbq import to_gbq
            from google.cloud import bigquery
            from google.api_core import exceptions as google_exceptions
        except ImportError as e:
            self.fail(f"Failed to import required module: {e}")
    
    def test_schema_consistency(self):
        """Test that schema definitions are consistent."""
        # All expected tables should have schemas defined
        # Using the actual TABLE_SCHEMAS keys to stay synchronized
        actual_tables = set(TABLE_SCHEMAS.keys())
        
        # Verify we have at least the core tables
        core_tables = {'daily_summary', 'activities', 'sleep'}
        self.assertTrue(core_tables.issubset(actual_tables),
                        f"Missing core table schemas. Expected at least {core_tables}, got {actual_tables}")


def main():
    """Run the test suite."""
    # Change to the repository directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Run tests
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(sys.modules[__name__])
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Exit with appropriate code
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
