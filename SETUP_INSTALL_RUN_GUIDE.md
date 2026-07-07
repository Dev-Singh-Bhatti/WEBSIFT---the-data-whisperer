# Complete Setup, Install, and Run Guide

## 1. Prerequisites
- Windows + PowerShell
- Python 3.13+
- Google Chrome installed
- Internet access (needed for scraping/model downloads)

## 2. Open Project Folder
```powershell
cd C:\Projects\myntra_review_project-main
```

## 3. Create and Activate Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If script execution is blocked:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

## 4. Upgrade pip
```powershell
python -m pip install --upgrade pip
```

## 5. Install Dependencies
```powershell
python -m pip install -r requirements.txt
```

This project currently expects:
- `transformers==5.5.4`
- `torch==2.11.0`
- `statsmodels==0.14.4`

## 6. Environment Configuration (Optional but Recommended)
Create a `.env` file in project root (or export variables in PowerShell):

```env
DATABASE_URL=sqlite:///./app.db
BROWSER_HEADLESS=False
REQUESTS_PER_MINUTE=10
DELAY_SCALE=0.5
```

PowerShell one-time session example:
```powershell
$env:DATABASE_URL="sqlite:///./app.db"
$env:BROWSER_HEADLESS="False"
$env:REQUESTS_PER_MINUTE="10"
$env:DELAY_SCALE="0.5"
```

## 7. Run the App
```powershell
python -m streamlit run app.py --server.port 8502 --server.headless true
```

Open in browser:
- `http://localhost:8502`

## 7.1 One-Command Startup (Windows)
Use the new script:
```powershell
powershell -ExecutionPolicy Bypass -File .\start_app.ps1
```

Useful options:
```powershell
# Custom port
powershell -ExecutionPolicy Bypass -File .\start_app.ps1 -Port 8503

# Force dependency install before start
powershell -ExecutionPolicy Bypass -File .\start_app.ps1 -InstallDependencies

# Run non-headless browser automation
powershell -ExecutionPolicy Bypass -File .\start_app.ps1 -Headless:$false
```

## 8. How to Use
1. Enter product keyword (e.g., `soap`).
2. Pick mode:
   - `Single Platform` (Myntra / Flipkart / Amazon)
   - `Compare All Platforms`
3. Choose number of products.
4. Click scrape/compare.
5. Open `Generate Analysis` page to view charts and summary.

## 9. Data Storage
- Reviews + summaries are stored in local SQLite (default):
  - `app.db`
- CSV export written by scraping pipeline:
  - `data.csv`

## 10. Stop the App
If running in terminal:
- Press `Ctrl + C`

If running in background:
```powershell
Get-Process python | Stop-Process -Force
```

## 11. Troubleshooting
### `No module named 'transformers'` / `statsmodels` / `torch`
```powershell
python -m pip install transformers==5.5.4 statsmodels==0.14.4 torch==2.11.0
```

### Selenium/ChromeDriver issues
If Selenium cache path permission is restricted:
```powershell
New-Item -ItemType Directory -Force -Path .tmp\selenium-cache | Out-Null
$env:SE_CACHE_PATH=(Resolve-Path .tmp\selenium-cache).Path
```
Then rerun Streamlit.

### Amazon review page redirect/sign-in
This can happen due anti-bot checks. Retry after a short delay, lower scrape rate, or use a stable proxy.

## 12. Current Live Run (from this session)
- Streamlit started successfully.
- Local URL responding with HTTP 200:
  - `http://127.0.0.1:8502`
