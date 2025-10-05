# Dura Highscores Tracker

Automated tracking and comparison of player experience on Dura Online Classic.

## Features

- 🔍 **Web Scraping**: Automatically scrapes player experience data
- 📊 **Comparison Reports**: Generates HTML reports comparing daily changes
- 🤖 **GitHub Actions**: Fully automated with scheduled runs
- 📈 **GitHub Pages**: Hosts comparison reports

## Setup Instructions

### 1. Fork/Clone this Repository

Fork this repository to your GitHub account or clone it locally.

### 2. Configure GitHub Repository

No additional secrets are required. The workflow uses the built-in `GITHUB_TOKEN` for repository operations.

### 3. Enable GitHub Pages

1. Go to repository Settings → Pages
2. Set Source to "Deploy from a branch"
3. Select branch: `main` or `gh-pages`
4. Select folder: `/ (root)`

### 4. Workflow Scheduling

The workflow is configured to run daily at 6 AM UTC. You can modify the cron schedule in `.github/workflows/highscores.yml`:

```yaml
schedule:
  - cron: '0 6 * * *'  # 6 AM UTC daily
```

### 5. Manual Execution

You can also trigger the workflow manually:

1. Go to Actions tab in your repository
2. Select "Dura Highscores Tracker" workflow
3. Click "Run workflow"
4. Choose execution mode:
   - **Full**: Complete scrape + comparison
   - **Compare Only**: Just compare existing snapshots

## File Structure

```
├── .github/workflows/
│   └── highscores.yml          # GitHub Actions workflow
├── snapshots/                  # CSV snapshots directory
│   ├── highscores_2025-10-02.csv
│   ├── highscores_2025-10-03.csv
│   └── highscores_2025-10-04.csv
├── highscore.py               # Main Python script
├── index.html                 # Generated comparison report
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## Usage

### Command Line (Local)

```bash
# Full scrape and compare
python highscore.py

# Compare existing snapshots only
python highscore.py --compare-only

# Compare specific dates
python highscore.py --compare-only 2025-10-03 2025-10-02

# Show help
python highscore.py --help
```

### GitHub Actions

The workflow runs automatically on schedule, but you can also:

1. Trigger manually from the Actions tab
2. Push changes to trigger a run
3. Use the workflow_dispatch inputs for custom parameters

## Output

- **CSV Files**: Stored in `snapshots/` directory
- **HTML Report**: Generated as `index.html` (viewable via GitHub Pages)
- **Console Output**: Status updates and statistics printed to workflow logs

## Troubleshooting

### Common Issues

1. **GitHub Pages not updating**: Check if workflow completed successfully
2. **Scraping failures**: May be due to website changes or rate limiting
3. **Missing snapshots**: Ensure previous day's CSV file exists for comparison

### Logs

Check the Actions tab for detailed execution logs and error messages.