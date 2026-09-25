# Job Searching Agent V2

V2 removes the hard-coded vacancies from V1 and attempts to discover real vacancies from company career pages.

## What it does
- Requests real career pages
- Reads JSON-LD `JobPosting` data where available
- Discovers likely individual vacancy links
- Extracts real titles, descriptions, locations and URLs where available
- Never invents salary information
- Filters obvious internships, finance roles and unrelated job families
- Deduplicates on individual vacancy URL
- Writes `job_market_matches.csv`

## Run

```bash
python -m pip install -r requirements.txt
python run_job_scraper.py --verbose
```

## Important
Career websites use different ATS platforms and JavaScript frameworks. A generic HTML scraper will not support every company. V2 deliberately skips unsupported sources instead of creating fake vacancies.

Once this base is verified, dedicated adapters can be added for sites that require APIs, Workday, SmartRecruiters, etc.
