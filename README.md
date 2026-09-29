# Job Searching Agent

A Python-based job discovery, filtering, scoring, and monitoring pipeline built for a focused Belgian data/BI job search.

The project started as a relatively simple multi-company scraper and has evolved through **48 named development versions** into a source-aware job-search agent with company-specific discovery strategies, profile-based filtering, Belgian location intelligence, source-health diagnostics, regression checks, deduplication, and automated CSV output.

> **Current development version:** `V5.8.9`  
> **Primary output:** `job_market_matches.csv`  
> **Primary market:** Belgium, with Brussels as the preferred location

---

## Overview

The Job Searching Agent automates the repetitive part of a targeted job search:

1. Visit selected employer career sites.
2. Discover vacancy inventory.
3. Identify potentially relevant data/BI/HR-data roles.
4. Open and extract vacancy detail pages.
5. Normalize job metadata.
6. Apply hard profile filters.
7. Resolve country and location.
8. Calculate distance from Brussels where possible.
9. Score surviving vacancies against the target profile.
10. Deduplicate vacancies conservatively.
11. Save verified matches to CSV.
12. Report source health and discovery problems for future recovery work.

The project deliberately does **not** assume that every career site behaves the same way. Over time it has gained dedicated handling for different ATS and career-site patterns, including HTML inventories, SuccessFactors-style sites, RSS feeds, embedded structured data, indexed recovery, and Lever.

---

## Architecture

```text
┌──────────────────────────────┐
│ Company career sites / ATS   │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Source-specific discovery    │
│ + generic recovery adapters  │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Vacancy URL inventory        │
│ + target-role prefilter      │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Detail-page extraction       │
│ title / location / text / ID │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Normalization                │
│ metadata / URLs / location   │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Hard filters                 │
│ degree / role / internship / │
│ country / profile constraints│
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Location intelligence        │
│ Belgium validation +         │
│ Brussels-distance reporting  │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Match scoring                │
│ skills / experience / role   │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ Conservative deduplication   │
│ job reference → URL          │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ job_market_matches.csv       │
│ + source-health diagnostics  │
└──────────────────────────────┘
```

### Design principle

The core flow is:

**discover → validate → extract → normalize → filter → locate → score → deduplicate → export**

Company-specific code should mainly solve **discovery and extraction**. Profile rules, country validation, scoring, and final output should remain centralized wherever possible.

---

## Features

### Multi-source vacancy discovery

The agent can use multiple discovery strategies depending on the employer:

- normal HTML vacancy links;
- inventory-first crawling;
- ATS-specific URL patterns;
- SuccessFactors recovery;
- RSS discovery;
- embedded JSON / structured data;
- internal-link analysis;
- indexed-search fallback where appropriate;
- Lever vacancy discovery;
- company-specific recovery adapters.

### Profile-aware filtering

Vacancies are evaluated against a defined target profile instead of being accepted simply because the title contains “data”.

The agent can evaluate:

- job family;
- required experience;
- degree requirements;
- required languages;
- relevant technical skills;
- internship/student status;
- country;
- location;
- work mode;
- profile match score.

### Location intelligence

The V5 generation introduced increasingly strict Belgian location handling.

The current pipeline can:

- distinguish Belgian and foreign vacancies;
- normalize Belgian locations;
- collect location evidence;
- apply company-specific location fallbacks;
- calculate approximate distance from Brussels for recognized locations;
- classify vacancies as within/outside the preferred radius;
- preserve Belgium-flexible opportunities;
- reject strong foreign-location signals;
- report unresolved locations separately.

> `OUTSIDE_30KM` is currently **report-only** in V5.8.9. It is not automatically rejected.

### Conservative deduplication

The agent avoids merging jobs merely because titles look similar.

Identity is based primarily on:

1. stable job reference, when available;
2. canonical vacancy URL otherwise.

This reduces the risk of accidentally merging two legitimate vacancies with similar titles.

### Source health

Every run reports source health so discovery failures are visible instead of silently producing an empty result.

Typical states include:

- `HEALTHY`
- `PARTIAL`
- `DEGRADED`
- `RECOVERY_NEEDED`
- `BLOCKED`
- `UNSUPPORTED`
- `IGNORED`

### Regression self-checks

Later versions include startup self-checks for previously fixed problems. These are designed to stop a new source patch from silently reintroducing older bugs in areas such as:

- country classification;
- location normalization;
- decision contracts;
- RSS parsing;
- SD Worx handling;
- SuccessFactors recovery;
- expansion-source schema;
- AE/Lever handling;
- internship filtering.

---

## Matching Rules

The agent is currently tuned for a specific Belgian job-search profile.

### Target roles

Highest priority:

- HR Data Analyst
- People Analytics
- HR Analytics
- HR BI
- HRIS Analyst
- HR Data Governance
- HR Data / Process roles
- BI Analyst
- Data Analyst
- Reporting Analyst
- Power BI roles
- BI Developer
- selected Data Governance roles

The project is also being expanded toward relevant **Data Engineering** opportunities where the required seniority and stack remain realistic.

### Domain preference

Preferred:

- HR / People / workforce data
- BI and analytics
- data governance
- healthcare
- public sector
- utilities
- transport / rail
- consulting where the assignment matches the target profile

Generally excluded or deprioritized:

- finance-only analyst/reporting roles;
- unrelated software-development roles;
- internships/student jobs;
- vacancies clearly outside Belgium.

### Experience

The profile combines approximately:

- 3.5 years of hands-on BI Developer experience;
- earlier HR / recruitment / payroll-related experience.

Roles asking for somewhat more experience can still be considered when the rest of the fit is strong. Very senior roles should be treated cautiously.

### Education

The profile has one Bachelor's degree in **Arabic and Islamic Studies**.

Matching rules therefore should:

- accept general Bachelor's requirements;
- reject a mandatory Master's requirement when no equivalent-experience alternative exists;
- reject mandatory specific engineering/technical degrees when equivalent experience or qualifications are not accepted;
- never represent the profile as holding an engineering degree.

### Languages

Current profile setting:

- English: **Advanced**
- Dutch/French: considered according to the vacancy requirements and actual profile evidence.

### Location

Preferred:

- Brussels
- approximately 30 km around Brussels

Hybrid and on-site opportunities can both be considered.

Jobs outside the preferred radius can remain visible for review instead of being automatically discarded when they are otherwise relevant.

### Contract / work preference

Current targeting is oriented toward:

- full-time work;
- contract/consulting opportunities;
- hybrid or on-site work.

### Salary target

Reference target:

**approximately €4,000 gross/month**

Salary is not always available in vacancy pages, so it is stored when extractable rather than used as a universal hard filter.

---

## Supported / Monitored Companies

V5.8.9 contains **28 configured company sources** across the stable/core and expansion layers.

### Core sources

- `Cegeka`
- `Capgemini`
- `Akkodis`
- `Pauwels Consulting`
- `Smals`
- `Infrabel`
- `HR Rail`
- `Sopra Steria`
- `Keyrus`
- `Datashift`
- `Sibelga`
- `LACO`
- `Data Wizards`

### Expansion sources

- `CM`
- `Orange Belgium`
- `Partena Professional`
- `SD Worx`
- `Securex`
- `Elia`
- `Fluvius`
- `PwC Belgium`
- `Delaware Belgium`
- `AE`
- `Inetum Belgium`
- `NRB`
- `Cronos Group`
- `Belfius`
- `Proximus`

### Important source-status notes

Not every configured source is currently healthy.

Some employers periodically change ATS platforms, block automated requests, expose vacancies only through JavaScript, or change URL structures. The source-health layer is therefore part of the product rather than an afterthought.

At the V5.8.9 stage:

- **Proximus** is intentionally parked because current relevant inventory is low.
- **Inetum Belgium** is temporarily parked pending a better current careers endpoint.
- **Belfius** is intentionally ignored.
- **Ordina** was removed because it is part of another company structure and should not be treated as an independent target source.
- **AE** is being recovered through its Lever inventory.
- **Delaware Belgium** has dedicated recovery logic.
- **Akkodis**, **Infrabel**, and **HR Rail** have received dedicated recovery/diagnostic work because their discovery behavior has been unstable across runs.

Source status should always be taken from the **latest run diagnostics**, not assumed from this README.

---

## CSV Output Schema

The current script writes:

```text
job_market_matches.csv
```

The V5.8.9 output schema contains **33 columns**:

| Column | Purpose |
|---|---|
| `title` | Vacancy title |
| `job_family` | Normalized target job family |
| `company` | Employer |
| `location` | Extracted/resolved vacancy location |
| `region` | Region where available |
| `normalized_location` | Standardized location value |
| `location_place` | Resolved place used by location logic |
| `distance_from_brussels_km` | Approximate distance from Brussels |
| `location_status` | Preferred-radius/location classification |
| `work_mode` | Remote/hybrid/on-site evidence where available |
| `country_status` | Belgium / outside Belgium / unknown classification |
| `country` | Resolved country |
| `location_status_v50` | Additional V5 location classification |
| `location_resolution_source` | How the final location was resolved |
| `location_evidence` | Evidence collected during location extraction |
| `job_reference` | Stable vacancy/job ID where available |
| `canonical_url` | Canonical vacancy URL |
| `salary` | Extracted salary when available |
| `employment_type` | Employment/contract type when available |
| `url` | Vacancy URL |
| `description` | Extracted vacancy description |
| `source` | Discovery/extraction source |
| `date_found` | UTC timestamp when discovered |
| `active` | Current active flag |
| `required_experience` | Parsed experience requirement |
| `degree_requirement` | Parsed education requirement |
| `required_languages` | Parsed language requirements |
| `matched_skills` | Skills matching the target profile |
| `missing_skills` | Relevant missing skills |
| `match_score` | Calculated profile-match score |
| `match_reason` | Human-readable score explanation |
| `hard_filter_status` | Hard-filter result |
| `hard_filter_reason` | Reason for hard rejection where applicable |

---

## Installation

### Requirements

- Python 3.10+ recommended
- internet access to the monitored career sites
- Git, when running through GitHub/GitHub Actions

### Python dependencies

The current script directly uses:

```text
pandas
requests
beautifulsoup4
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it.

Linux/macOS:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install pandas requests beautifulsoup4
```

A minimal `requirements.txt` can therefore contain:

```text
pandas
requests
beautifulsoup4
```

---

## Running Locally

Run the current version:

```bash
python run_job_scraper_v5_8_9.py
```

A successful run will:

1. execute regression/self-checks;
2. scrape configured sources;
3. print per-company discovery diagnostics;
4. evaluate and score matching vacancies;
5. perform final deduplication;
6. apply the final country guard;
7. report location/source health;
8. write `job_market_matches.csv`.

The existing CSV is deliberately left unchanged when a run produces no verified matches.

---

## GitHub Actions

The scraper is designed to run automatically from GitHub Actions.

A basic workflow can be stored at:

```text
.github/workflows/job-scraper.yml
```

Example:

```yaml
name: Job Searching Agent

on:
  workflow_dispatch:

  # GitHub cron expressions are UTC.
  # Adjust these if you want fixed Belgian wall-clock times across DST.
  schedule:
    - cron: "0 4 * * *"
    - cron: "0 8 * * *"
    - cron: "0 12 * * *"
    - cron: "0 16 * * *"

permissions:
  contents: write

jobs:
  scrape:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install pandas requests beautifulsoup4

      - name: Run scraper
        run: python run_job_scraper_v5_8_9.py

      - name: Commit updated results
        run: |
          git config user.name "job-searching-agent"
          git config user.email "actions@users.noreply.github.com"
          git add job_market_matches.csv
          git diff --cached --quiet || git commit -m "Update job market matches"
          git push
```

### Intended schedule

The target schedule for the project is:

- **06:00 Belgium time**
- **10:00 Belgium time**
- **14:00 Belgium time**
- **18:00 Belgium time**

#### CET/CEST warning

GitHub Actions cron schedules use UTC. Belgium changes between:

- CET = UTC+1
- CEST = UTC+2

A static cron schedule therefore cannot stay at exactly 06:00 / 10:00 / 14:00 / 18:00 Belgian local time throughout both winter and summer.

For production, V6 should make scheduling explicitly timezone-aware instead of relying on a permanently fixed UTC conversion.

---

## Development History

The repository contains a long iterative development history. Based on the preserved scraper files, the named sequence currently runs from **V3.1 through V5.8.9**, representing **48 named versions**, excluding same-version repair files such as `fixed`, `corrected`, or `repaired` variants.

### V3 — Foundation

Versions:

`V3.1` → `V3.2` → `V3.3` → `V3.4` → `V3.5` → `V3.6` → `V3.6.1`

The V3 generation established the original scraper architecture and progressively improved vacancy discovery, extraction, matching, and output.

### V4 — Discovery Reliability

Versions:

`V4` → `V4.1` → `V4.2` → `V4.3` → `V4.4` → `V4.5` → `V4.6` → `V4.7` → `V4.8` → `V4.9`

Important themes:

- discovery recovery;
- inventory-first discovery;
- source-specific handling;
- more reliable vacancy identification;
- stable job-reference extraction;
- conservative deduplication;
- improved diagnostics.

`V4.4` was an important inventory-first milestone: the scraper began treating discovery coverage as a measurable stage instead of relying only on already-targeted links.

### V5.0–V5.4 — Belgium-first Matching

Versions:

`V5.0` → `V5.1` → `V5.2` → `V5.3` → `V5.4` → `V5.4.1`

The V5 generation shifted the project from a scraper toward a job-search agent.

Major themes:

- Belgium-first location consolidation;
- location normalization;
- country classification;
- Brussels-distance intelligence;
- stronger profile filtering;
- source recovery and reliability;
- better handling of foreign jobs leaking through global career portals;
- regression protection for location fixes.

### V5.5 — Source Recovery

Versions:

`V5.5` → `V5.5.1`

Focus:

- source recovery;
- location-regression guardrails;
- RSS recovery;
- better resilience when career sites changed.

### V5.6 — Expansion Architecture

Versions:

`V5.6` → `V5.6.1` → `V5.6.2` → `V5.6.3`

Focus:

- reusable expansion-source architecture;
- adding more Belgian employers;
- common discovery adapters;
- expansion schema;
- preserving the stable core while experimenting with new sources.

### V5.7 — Expansion Stabilization

Versions:

`V5.7` → `V5.7.1` → `V5.7.2` → `V5.7.3` → `V5.7.4` → `V5.7.5` → `V5.7.6` → `V5.7.7` → `V5.7.8`

Focus:

- company-expansion integration;
- source-specific diagnostics;
- decision-contract normalization;
- SD Worx recovery work;
- safe accepted/rejected-row handling;
- source-health reporting;
- exclusion/parking logic for unsuitable sources.

### V5.8 — Advanced Recovery & Quality

Versions:

`V5.8.0` → `V5.8.1` → `V5.8.2` → `V5.8.3` → `V5.8.4` → `V5.8.5` → `V5.8.6` → `V5.8.7` → `V5.8.8` → **`V5.8.9`**

Major themes:

- stronger country guard;
- RSS/parser regression checks;
- SuccessFactors recovery;
- Infrabel / HR Rail diagnostics;
- SD Worx contract fixes;
- Akkodis dedicated recovery;
- safer mixed source-health schemas;
- AE / Delaware / Inetum recovery work;
- deliberate parking of low-priority or unstable sources;
- internship-filter corrections;
- decision-normalization fixes;
- AE Lever ATS discovery.

### Current development point: V5.8.9

V5.8.9 is primarily a quality/recovery release.

Its main goals are:

- integrate AE through Lever;
- prevent false internship rejection;
- normalize expansion decisions correctly;
- preserve Delaware discovery;
- park Inetum temporarily;
- keep Proximus parked;
- preserve earlier Akkodis, SD Worx, location, country, and source-health fixes.

---

## Development Philosophy

This project has intentionally evolved through many small versions rather than large rewrites.

The reason is simple: career sites are heterogeneous and unstable.

A fix for one source can easily break another if discovery, extraction, filtering, and scoring are tightly coupled. Later versions therefore increasingly follow these rules:

1. **Preserve working sources.**
2. **Make source-specific recovery surgical.**
3. **Keep matching rules centralized.**
4. **Add regression checks for important fixes.**
5. **Treat zero results as a diagnostic state, not automatically as “no jobs”.**
6. **Prefer official vacancy inventory over search-engine discovery.**
7. **Keep foreign-location protection conservative but explicit.**
8. **Do not merge vacancies based only on similar titles.**
9. **Park low-value sources instead of wasting requests indefinitely.**
10. **Use source-health output to decide what the next version should fix.**

---

## Roadmap to V6.0

The goal of V6.0 should not simply be “more companies”. It should turn the accumulated V5 logic into a cleaner, maintainable job-search platform.

### V5.9 — Consolidation

Planned focus:

- freeze proven source adapters;
- remove obsolete recovery code;
- consolidate duplicated discovery functions;
- formalize source states;
- improve structured logging;
- move configuration out of the main Python file;
- stabilize the four-times-daily automation;
- review CSV compatibility and historical tracking.

### V5.9.x — Data Engineering expansion

The target profile is broadening toward realistic Data Engineering opportunities.

Planned work:

- separate Data Analyst / BI / HR Data / Data Engineer scoring;
- distinguish required vs optional cloud skills;
- recognize Azure Data Factory, Databricks, PySpark, Snowflake and related stack terms;
- avoid over-scoring senior engineering positions;
- retain HR/Data/BI roles as a primary matching path.

### V6.0 — Modular architecture

Proposed structure:

```text
jobscraper/
├── config/
│   ├── profile.yaml
│   ├── sources.yaml
│   └── settings.yaml
├── discovery/
│   ├── generic.py
│   ├── successfactors.py
│   ├── lever.py
│   ├── rss.py
│   └── company_adapters/
├── extraction/
│   ├── vacancy.py
│   └── location.py
├── matching/
│   ├── filters.py
│   ├── scoring.py
│   └── skills.py
├── validation/
│   ├── country.py
│   ├── location.py
│   └── regression.py
├── storage/
│   ├── csv_store.py
│   └── history.py
├── reporting/
│   └── health.py
└── main.py
```

V6.0 objectives:

- modular source adapters;
- YAML/JSON source configuration;
- profile configuration outside code;
- persistent vacancy history;
- `first_seen` / `last_seen` tracking;
- new/changed/closed vacancy detection;
- cleaner source-health metrics;
- retry/backoff strategy;
- structured logging;
- automated tests;
- timezone-aware scheduling;
- clearer separation between discovery and matching;
- easier onboarding of new companies;
- optional SQLite storage alongside CSV;
- cleaner GitHub Actions integration.

---

## Future Ideas

Possible later additions:

- notification only for newly discovered high-score jobs;
- applied / response / interview status tracking;
- company/recruiter tracking;
- historical vacancy trends;
- dashboard over scraper results;
- automatic “why this job matches” summary;
- skill-gap reporting;
- Data Engineering readiness scoring;
- stale-vacancy detection;
- source success-rate statistics;
- configurable radius rather than hard-coded Brussels logic.

---

## Repository Hygiene

Recommended Git layout:

```text
.
├── README.md
├── requirements.txt
├── run_job_scraper_v5_8_9.py
├── job_market_matches.csv
├── .github/
│   └── workflows/
│       └── job-scraper.yml
└── archive/
    ├── v3/
    ├── v4/
    └── v5/
```

Old versions are valuable as development history, but the repository root should ideally contain only the current production candidate and files required to run it.

---

## Disclaimer

This project is a personal job-search automation tool.

Career websites can change without notice, block automated requests, or expose incomplete information. A vacancy being absent from the output does **not** necessarily mean that the employer has no relevant vacancies.

Match scores are decision-support signals, not objective assessments of candidate suitability. Important vacancies should still be reviewed manually before applying.

The scraper should be operated responsibly and with reasonable request frequency.

---

## Current Status

**Current version:** `V5.8.9`  
**Output:** `job_market_matches.csv`  
**Configured sources:** 28  
**Named development versions preserved/identified:** 48  
**Primary target market:** Belgium / Brussels region  
**Next milestone:** V5.9 consolidation → V6.0 modular architecture
