# Filament Tracker Export

A static site that displays your [Bambu Tracker](https://bambutracker.com/) filament inventory as a searchable, sortable page with card and table views.

**Live site:** https://daftdoki.github.io/filament-tracker-export/

## How it works

The `generate.py` script reads the most recent JSON and CSV export files from the `data/` directory and produces a self-contained `index.html` with all the data embedded. A GitHub Actions workflow runs this on every push and deploys the result to GitHub Pages.

## Updating your data

1. Go to [Bambu Tracker](https://bambutracker.com/) and open your inventory.
2. Export your data:
   - **JSON backup:** Settings > Backup/Restore > Download Backup. This gives you a file like `BambuTrackerBackup_260412_224719.json`.
   - **CSV export:** Settings > Export > Download CSV. This gives you `BambuTrackerExport.csv`.
3. Drop both files into the `data/` directory in this repo.
4. Commit and push:
   ```
   git add data/
   git commit -m "Update inventory"
   git push
   ```

CI will regenerate the site and deploy it automatically. The script picks the latest files alphabetically, so timestamped filenames sort correctly — no need to delete old exports.
