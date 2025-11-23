# garmin-bigquery-sync

Automatically sync your Garmin Connect data to Google BigQuery using GitHub Actions.

This project uses [GarminDB](https://github.com/tcgoetz/GarminDB) to download your Garmin Connect data into a SQLite database, then syncs it to BigQuery for analysis and visualization.

## Features

- 🔄 Automatic daily sync of Garmin data to BigQuery
- 📊 Syncs daily summaries and activities
- 🔐 Secure credential management via GitHub Secrets
- 💾 Caches Garmin data between runs for efficiency
- ⚡ Manual trigger support via workflow_dispatch

## Setup

### 1. Google Cloud Platform Setup

#### Create a GCP Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Note your Project ID (e.g., `my-garmin-project`)

#### Enable BigQuery API

1. In your GCP project, go to **APIs & Services > Library**
2. Search for "BigQuery API"
3. Click **Enable**

#### Create a BigQuery Dataset

1. Go to [BigQuery Console](https://console.cloud.google.com/bigquery)
2. Click your project name
3. Click **Create Dataset**
4. Dataset ID: `garmin_data` (or your preferred name)
5. Location: Choose your preferred region
6. Click **Create Dataset**

#### Create a Service Account

1. Go to **IAM & Admin > Service Accounts**
2. Click **Create Service Account**
3. Name: `garmin-sync` (or your preferred name)
4. Click **Create and Continue**
5. Grant the following roles:
   - **BigQuery Data Editor**
   - **BigQuery Job User**
6. Click **Continue**, then **Done**

#### Generate Service Account Key

1. Click on the service account you just created
2. Go to the **Keys** tab
3. Click **Add Key > Create New Key**
4. Choose **JSON** format
5. Click **Create** - a JSON file will be downloaded
6. **Keep this file secure** - you'll use it in GitHub Secrets

### 2. GitHub Repository Setup

#### Fork or Clone This Repository

Fork this repository to your GitHub account or create a new repository with these files.

#### Configure GitHub Secrets

Go to your repository's **Settings > Secrets and variables > Actions** and add the following secrets:

| Secret Name | Description | Example |
|-------------|-------------|---------|
| `GARMIN_USER` | Your Garmin Connect email/username | `user@example.com` |
| `GARMIN_PASSWORD` | Your Garmin Connect password | `your-password` |
| `GCP_PROJECT_ID` | Your Google Cloud Project ID | `my-garmin-project` |
| `GCP_SA_KEY` | Contents of the service account JSON key file | Paste entire JSON contents |

**To add a secret:**
1. Click **New repository secret**
2. Enter the **Name** and **Secret** value
3. Click **Add secret**

### 3. Running the Sync

#### Automatic Schedule

The workflow runs automatically every day at 2 AM UTC. You can modify the schedule in `.github/workflows/sync.yml`:

```yaml
schedule:
  - cron: '0 2 * * *'  # Daily at 2 AM UTC
```

#### Manual Trigger

1. Go to **Actions** tab in your repository
2. Select **Sync Garmin Data to BigQuery** workflow
3. Click **Run workflow**
4. Select the branch and click **Run workflow**

### 4. Viewing Your Data in BigQuery

1. Go to [BigQuery Console](https://console.cloud.google.com/bigquery)
2. Expand your project
3. Expand the `garmin_data` dataset
4. You should see tables like:
   - `daily_summary`
   - `activities`

#### Example Query

```sql
SELECT 
  day,
  hr_avg,
  hr_max,
  steps,
  distance
FROM `your-project-id.garmin_data.daily_summary`
WHERE day >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
ORDER BY day DESC
```

## Configuration

### Environment Variables

The `sync_bq.py` script accepts the following environment variables:

- `GCP_PROJECT_ID` (required): Your Google Cloud Project ID
- `DATASET_ID` (optional): BigQuery dataset name (default: `garmin_data`)

### Adding More Tables

To sync additional tables from GarminDB, edit `sync_bq.py` and add table names to the `tables_to_sync` list:

```python
tables_to_sync = [
    'daily_summary',
    'activities',
    'sleep',           # Add more tables
    'monitoring_hr',   # as needed
]
```

To see all available tables, you can explore the GarminDB SQLite database:

```bash
sqlite3 ~/.GarminDb/garmin.db ".tables"
```

## Technical Details

### GarminDB Wrapper

This project includes a wrapper script (`garmindb_wrapper.py`) that prevents a TypeError that can occur when calling `garmindb_cli.py` without statistics arguments. The wrapper ensures that operations requiring statistics (download, import, copy) always have appropriate flags set.

The wrapper automatically adds the `--all` flag when:
- Operations like `--download`, `--import`, or `--copy` are specified
- No statistics flags (`--activities`, `--monitoring`, `--sleep`, etc.) are provided

This prevents the internal `stats` parameter from being `None`, which would cause a TypeError when the code tries to check `if Statistics.activities in stats:`.

## Troubleshooting

### Workflow Fails with "GarminDB database not found"

The first run might fail if Garmin data hasn't been downloaded yet. The workflow is configured to continue even if the import step fails. After the first successful import, subsequent runs should work.

### TypeError with stats parameter

If you see errors related to `TypeError: argument of type 'NoneType' is not iterable`, ensure you're using the wrapper script:
```bash
# Instead of:
garmindb_cli.py --download --import --analyze --latest

# Use:
python garmindb_wrapper.py --download --import --analyze --latest
```

The GitHub Actions workflow already uses the wrapper script automatically.

### Authentication Issues

- **Garmin**: Verify your `GARMIN_USER` and `GARMIN_PASSWORD` secrets are correct
- **Google Cloud**: Ensure your service account has the necessary BigQuery permissions
- **GCP_SA_KEY**: Make sure you pasted the entire JSON file contents, including the curly braces

### No Data in BigQuery

- Check the workflow logs in the **Actions** tab
- Ensure the Garmin import step completed successfully
- Verify that your GarminDB database has data in the tables being synced

## Local Development

### Prerequisites

- Python 3.8+
- Google Cloud SDK (optional, for local testing)

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/garmin-bigquery-sync.git
cd garmin-bigquery-sync

# Install dependencies
pip install -r requirements.txt
```

### Running Locally

1. Download Garmin data:
   ```bash
   # Configure credentials
   garmindb_cli.py --config
   
   # Import data using the wrapper to prevent TypeError
   python garmindb_wrapper.py --download --import --analyze --latest
   
   # Or with specific statistics
   garmindb_cli.py --download --import --analyze --latest --all
   ```

2. Set up Google Cloud credentials:
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
   export GCP_PROJECT_ID=your-project-id
   export DATASET_ID=garmin_data
   ```

3. Run the sync:
   ```bash
   python sync_bq.py
   ```

## Architecture

```
┌─────────────────┐
│  Garmin Connect │
└────────┬────────┘
         │ garmindb_cli.py
         ▼
┌─────────────────┐
│ SQLite Database │ ~/.GarminDb/garmin.db
└────────┬────────┘
         │ sync_bq.py
         ▼
┌─────────────────┐
│   BigQuery      │ your-project.garmin_data.*
└─────────────────┘
```

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Acknowledgments

- [GarminDB](https://github.com/tcgoetz/GarminDB) - For the excellent Garmin data download and processing tool