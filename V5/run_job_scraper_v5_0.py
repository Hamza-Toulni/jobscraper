# -*- coding: utf-8 -*-

from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, urldefrag, quote_plus, parse_qs
import json
import re
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup


# ============================================================
# CONFIG
# ============================================================

OUTPUT = "job_market_matches.csv"

SOURCES = [
    {
        "company": "Cegeka",
        "url": "https://www.cegeka.com/en/be/jobs/all-jobs",
        "domain": "cegeka.com",
        "type": "cegeka",
    },
    {
        "company": "Capgemini",
        "url": (
            "https://www.capgemini.com/careers/join-capgemini/"
            "job-search/?country_code=en-be&country_name=Belgium&size=100"
        ),
        "domain": "capgemini.com",
        "type": "capgemini",
    },
    {
        "company": "Akkodis",
        "url": "https://www.akkodis.com/en-be/careers",
        "domain": "akkodis.com",
        "type": "akkodis",
    },
    {
        "company": "Pauwels Consulting",
        "url": "https://www.pauwelsconsulting.com/jobs",
        "domain": "pauwelsconsulting.com",
        "type": "pauwels",
    },
    {
        "company": "Smals",
        "url": "https://www.smals.be/nl/jobs/list",
        "domain": "smals.be",
        "type": "smals",
    },
    {
        "company": "Infrabel",
        "url": "https://jobs.infrabel.be/viewalljobs/",
        "domain": "jobs.infrabel.be",
        "type": "successfactors",
        "job_url_regex": r"/job/[^/]+/\d+(?:-[a-z_]+)?/?$",
    },
    {
        "company": "HR Rail",
        "url": "https://jobs.hr-rail.be/HRRail/go/Alle-vacatures-HR-Rail/957202/",
        "domain": "jobs.hr-rail.be",
        "type": "successfactors",
        "job_url_regex": r"/job/[^/]+/\d+(?:-[a-z_]+)?/?$",
    },
    {
        "company": "Sopra Steria",
        "url": "https://careers.soprasteria.be/jobs",
        "domain": "careers.soprasteria.be",
        "type": "ats_html",
        "job_url_regex": r"/job/[^/]+-jid-\d+/?$",
    },
    {
        "company": "Keyrus",
        "url": "https://jobs.keyrus.be/jobs",
        "domain": "jobs.keyrus.be",
        "type": "teamtailor",
        "job_url_regex": r"/jobs/\d+-[^/]+/?$",
    },
    {
        "company": "Datashift",
        "url": "https://careers.datashift.eu/",
        "domain": "careers.datashift.eu",
        "type": "recruitee",
        "job_url_regex": r"/o/[^/]+/?$",
    },
    {
        "company": "Sibelga",
        "url": "https://jobs.sibelga.be/offre-de-emploi/liste-offres.aspx?mode=list",
        "domain": "jobs.sibelga.be",
        "type": "talentsoft",
        "job_url_regex": r"/offre-de-emploi/[^?#]+(?:\.aspx)?$",
    },
    {
        "company": "LACO",
        "url": "https://www.laco.be/vacancy/",
        "domain": "laco.be",
        "type": "wordpress_jobs",
        "job_url_regex": r"/(?!vacancy/?$)[a-z0-9][a-z0-9-]+/?$",
    },
    {
        "company": "Data Wizards",
        "url": "https://jobs.datawizards.io/job-openings",
        "domain": "jobs.datawizards.io",
        "type": "recruitee",
        "job_url_regex": r"/o/[^/]+/?$",
    },
]


# ============================================================
# TARGET JOB FAMILIES
# ============================================================

FAMILIES = {
    "HR Data / People Analytics": [
        "hr data analyst",
        "hr data analist",
        "hr analytics",
        "people analytics",
        "workforce analytics",
        "hris analyst",
        "hr reporting",
        "people data",
    ],

    "Data Analyst": [
        "data analyst",
        "data analist",
        "data analytics analyst",
        "analytics analyst",
        "data pipeline analyst",
    ],

    "BI / Power BI": [
        "bi analyst",
        "bi analist",
        "bi developer",
        "business intelligence analyst",
        "business intelligence developer",
        "power bi analyst",
        "power bi developer",
    ],

    "Data Governance / Quality": [
        "data governance",
        "data quality",
        "data steward",
        "master data",
    ],

    "Reporting": [
        "reporting analyst",
        "reporting analist",
        "reporting developer",
        "reporting specialist",
    ],

    "Data / Analytics Consulting": [
        "data consultant",
        "analytics consultant",
        "bi consultant",
        "business intelligence consultant",
    ],

    "Functional / Business Data Analysis": [
        "data functional analyst",
        "functional data analyst",
        "functional analyst data",
        "functional analyst - data",
        "functional analyst – data",
        "business data analyst",
        "business analyst data",
        "business analyst - data",
        "business analyst – data",
        "business analyst data & analytics",
        "business analyst – data & analytics",
        "business analyst - data & analytics",
    ],
}


STRETCH = [
    "data engineer",
    "data engineering",
    "etl developer",
    "etl engineer",
    "data warehouse developer",
    "datawarehouse developer",
]


# ============================================================
# USER PROFILE / SCORING
# ============================================================

SKILLS = {
    "sql": 12,
    "power bi": 12,
    "etl": 10,
    "data warehouse": 9,
    "datawarehouse": 9,
    "data quality": 8,
    "data governance": 8,
    "python": 5,
    "cognos": 4,
    "wherescape": 5,
    "reporting": 5,
    "hr analytics": 7,
    "people analytics": 7,
    "data modeling": 6,
    "data modelling": 6,
}


GAP_SKILLS = [
    "databricks",
    "dbt",
    "microsoft fabric",
    "snowflake",
    "tableau",
    "collibra",
    "informatica",
    "purview",
    "spark",
    "scala",
]


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/149.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9,nl;q=0.8,fr;q=0.7",
}


SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# ============================================================
# HELPERS
# ============================================================

def clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_url(url, base):
    url = urljoin(base, url)
    url, _ = urldefrag(url)
    return url.rstrip("/")


def host_matches(url, domain):
    host = urlparse(url).netloc.lower()

    return (
        host == domain
        or host.endswith("." + domain)
    )


def fetch(url, retries=3):

    for attempt in range(retries):

        try:
            response = SESSION.get(
                url,
                timeout=30,
                allow_redirects=True,
            )

            if response.status_code == 429:

                wait = 5 * (attempt + 1)

                print(
                    f"  rate limited; waiting {wait}s"
                )

                time.sleep(wait)
                continue

            response.raise_for_status()

            content_type = response.headers.get(
                "content-type",
                "",
            ).lower()

            if (
                "html" not in content_type
                and "text" not in content_type
            ):
                return ""

            return response.text

        except requests.RequestException:

            if attempt == retries - 1:
                raise

            time.sleep(2 * (attempt + 1))

    return ""


def search_discovery(query, domains=None, max_results=30):
    """Discover candidate vacancy URLs through DuckDuckGo HTML results."""
    search_url = "https://html.duckduckgo.com/html/?q=" + quote_plus(query)

    response = SESSION.get(
        search_url,
        timeout=30,
        allow_redirects=True,
        headers={**HEADERS, "Referer": "https://duckduckgo.com/"},
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    results = []

    for anchor in soup.select("a.result__a"):
        href = anchor.get("href", "")
        title = clean(anchor.get_text(" ", strip=True))

        if "uddg=" in href:
            parsed = urlparse(href)
            target = parse_qs(parsed.query).get("uddg", [])
            if target:
                href = target[0]

        if not href.startswith("http"):
            continue

        host = urlparse(href).netloc.lower()

        if domains and not any(
            host == domain or host.endswith("." + domain)
            for domain in domains
        ):
            continue

        results.append((normalize_url(href, href), title))

        if len(results) >= max_results:
            break

    unique = {}
    for result_url, title in results:
        unique[result_url] = title

    return list(unique.items())


def search_discovery_bing(query, domains=None, max_results=30):
    """
    Secondary indexed-web discovery path.
    Used when a career site is partially client-rendered and its normal
    requests HTML does not contain all vacancies.
    """
    search_url = "https://www.bing.com/search?q=" + quote_plus(query)

    response = SESSION.get(
        search_url,
        timeout=30,
        allow_redirects=True,
        headers={**HEADERS, "Referer": "https://www.bing.com/"},
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    results = []

    for anchor in soup.select("li.b_algo h2 a[href]"):
        href = anchor.get("href", "")
        title = clean(anchor.get_text(" ", strip=True))

        if not href.startswith("http"):
            continue

        host = urlparse(href).netloc.lower()

        if domains and not any(
            host == domain or host.endswith("." + domain)
            for domain in domains
        ):
            continue

        results.append((normalize_url(href, href), title))

        if len(results) >= max_results:
            break

    unique = {}
    for result_url, title in results:
        unique[result_url] = title

    return list(unique.items())


# ============================================================
# JOB FAMILY
# ============================================================

def family(title):

    text = clean(title).lower()

    for fam, terms in FAMILIES.items():

        if any(term in text for term in terms):
            return fam

    if any(term in text for term in STRETCH):
        return "Data Engineering (stretch)"

    return ""


def looks_targeted(text):

    return bool(
        family(clean(text))
    )


# ============================================================
# COMPANY-SPECIFIC URL DETECTION
# ============================================================

def is_job_url(url, source):

    path = urlparse(url).path.lower()

    source_type = source["type"]

    # CEGEKA
    if source_type == "cegeka":
        return bool(
            re.search(
                r"/jobs/all-jobs/[^/]+-\d+$",
                path,
            )
        )

    # SMALS
    if source_type == "smals":
        return bool(
            re.search(
                r"/(?:nl|fr)/jobs/apply/\d+/[^/]+$",
                path,
            )
        )

    # AKKODIS
    if source_type == "akkodis":
        return bool(
            re.search(
                r"/en-be/careers/jobs/[^/]+/[^/]+$",
                path,
            )
        )

    # PAUWELS
    if source_type == "pauwels":
        return bool(
            re.search(
                r"/(?:[a-z]{2}-[a-z]{2}/)?job/"
                r"[^/]+/[^/]+$",
                path,
            )
        )

    # CAPGEMINI
    if source_type == "capgemini":
        return bool(
            re.search(r"/job/[^/]+", path)
            or re.search(r"/(?:be-en/)?jobs/[^/]+", path)
        )

    if source_type in {
        "generic",
        "ats_html",
        "successfactors",
        "teamtailor",
        "recruitee",
        "talentsoft",
        "wordpress_jobs",
    }:
        pattern = source.get("job_url_regex")
        return bool(pattern and re.search(pattern, path))

    return False


# ============================================================
# JSON-LD
# ============================================================

def jsonld_objects(soup):

    for script in soup.find_all(
        "script",
        type="application/ld+json",
    ):

        raw = (
            script.string
            or script.get_text()
        )

        try:
            data = json.loads(raw)

        except Exception:
            continue

        objects = (
            data
            if isinstance(data, list)
            else [data]
        )

        for obj in objects:

            if not isinstance(obj, dict):
                continue

            graph = obj.get("@graph")

            if isinstance(graph, list):

                for item in graph:

                    if isinstance(item, dict):
                        yield item

            else:
                yield obj


def extract_jsonld_job(html, source, page_url):

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    for obj in jsonld_objects(soup):

        job_type = obj.get("@type", [])

        if isinstance(job_type, str):
            job_type = [job_type]

        if "JobPosting" not in job_type:
            continue

        title = clean(
            obj.get("title")
        )

        if not family(title):
            continue

        description = clean(
            BeautifulSoup(
                str(
                    obj.get(
                        "description",
                        "",
                    )
                ),
                "html.parser",
            ).get_text(" ")
        )

        location = extract_jsonld_location(
            obj
        )
        if not location:
            location, _ = resolve_location_v49(
                soup,
                description,
                existing="",
            )

        employment = obj.get(
            "employmentType",
            "",
        )

        if isinstance(employment, list):
            employment = ", ".join(employment)

        url = normalize_url(
            obj.get("url") or page_url,
            page_url,
        )

        job = make_job(
            source,
            title,
            description,
            url,
            location,
            clean(employment),
        )
        job["location_resolution_source"] = "jsonld" if location else "unknown"
        job["location_evidence"] = json.dumps(
            [{"source": "jsonld", "raw": location, "resolved": _location_from_text(location)}]
            if location else [],
            ensure_ascii=False,
        )
        return job

    return None


def extract_jsonld_location(obj):

    raw_locations = (
        obj.get("jobLocation")
        or []
    )

    if not isinstance(
        raw_locations,
        list,
    ):
        raw_locations = [raw_locations]

    locations = []

    for item in raw_locations:

        if not isinstance(item, dict):
            continue

        address = item.get(
            "address",
            {},
        )

        if not isinstance(address, dict):
            continue

        pieces = []

        for key in [
            "postalCode",
            "addressLocality",
            "addressRegion",
            "addressCountry",
        ]:

            value = clean(
                address.get(key)
            )

            if value:
                pieces.append(value)

        if pieces:
            locations.append(
                ", ".join(pieces)
            )

    return " / ".join(
        dict.fromkeys(locations)
    )


# ============================================================
# GENERIC DETAIL-PAGE EXTRACTION
# ============================================================

def page_title(soup):

    h1 = soup.find("h1")

    if h1:
        return clean(
            h1.get_text(
                " ",
                strip=True,
            )
        )

    og = soup.find(
        "meta",
        property="og:title",
    )

    if og:
        return clean(
            og.get("content")
        )

    title_tag = soup.find("title")

    if title_tag:

        title = clean(
            title_tag.get_text(
                " ",
                strip=True,
            )
        )

        title = re.split(
            r"\s+[|\-]\s+",
            title,
        )[0]

        return clean(title)

    return ""


def page_description(soup):

    # Remove obvious navigation/noise.

    for tag in soup(
        [
            "script",
            "style",
            "noscript",
            "nav",
            "footer",
        ]
    ):
        tag.decompose()

    main = (
        soup.find("main")
        or soup.find("article")
        or soup.body
    )

    if not main:
        return ""

    return clean(
        main.get_text(
            " ",
            strip=True,
        )
    )


def guess_location(
    soup,
    description,
):

    candidates = []

    selectors = [
        "[class*='location']",
        "[class*='Location']",
        "[data-testid*='location']",
    ]

    for selector in selectors:

        try:
            elements = soup.select(
                selector
            )

        except Exception:
            elements = []

        for element in elements[:5]:

            value = clean(
                element.get_text(
                    " ",
                    strip=True,
                )
            )

            if (
                value
                and len(value) < 100
            ):
                candidates.append(value)

    if candidates:
        return candidates[0]

    # Conservative fallback for common Belgian locations.

    locations = [
        "Brussels",
        "Bruxelles",
        "Brussel",
        "Diegem",
        "Machelen",
        "Hasselt",
        "Ghent",
        "Gent",
        "Antwerp",
        "Antwerpen",
        "Leuven",
        "Mechelen",
        "West Flanders",
        "West-Vlaanderen",
        "Walloon Brabant",
        "Braine-l'Alleud",
        "Schaerbeek",
        "Schaarbeek",
    ]

    for location in locations:

        if re.search(
            r"\b"
            + re.escape(location)
            + r"\b",
            description,
            flags=re.I,
        ):
            return location

    return ""



# ============================================================
# V5.0 LOCATION RESOLUTION + COUNTRY VALIDATION
# ============================================================

BELGIAN_LOCATION_ALIASES = {
    "brussels": "Brussels",
    "bruxelles": "Brussels",
    "brussel": "Brussels",
    "schaerbeek": "Schaerbeek",
    "schaarbeek": "Schaerbeek",
    "anderlecht": "Anderlecht",
    "etterbeek": "Etterbeek",
    "ixelles": "Ixelles",
    "elsene": "Ixelles",
    "auderghem": "Auderghem",
    "oudergem": "Auderghem",
    "woluwe-saint-lambert": "Woluwe-Saint-Lambert",
    "sint-lambrechts-woluwe": "Woluwe-Saint-Lambert",
    "woluwe-saint-pierre": "Woluwe-Saint-Pierre",
    "sint-pieters-woluwe": "Woluwe-Saint-Pierre",
    "zaventem": "Zaventem",
    "diegem": "Diegem",
    "machelen": "Machelen",
    "vilvoorde": "Vilvoorde",
    "leuven": "Leuven",
    "louvain": "Leuven",
    "mechelen": "Mechelen",
    "malines": "Mechelen",
    "antwerp": "Antwerp",
    "antwerpen": "Antwerp",
    "anvers": "Antwerp",
    "ghent": "Ghent",
    "gent": "Ghent",
    "gand": "Ghent",
    "hasselt": "Hasselt",
    "aalst": "Aalst",
    "alost": "Aalst",
    "wavre": "Wavre",
    "waver": "Wavre",
    "waterloo": "Waterloo",
    "braine-l'alleud": "Braine-l'Alleud",
    "braine-l’alleud": "Braine-l'Alleud",
    "eigenbrakel": "Braine-l'Alleud",
    "nivelles": "Nivelles",
    "nijvel": "Nivelles",
    "charleroi": "Charleroi",
    "namur": "Namur",
    "namen": "Namur",
    "liège": "Liège",
    "liege": "Liège",
    "luik": "Liège",
    "mons": "Mons",
    "bergen": "Mons",
    "kortrijk": "Kortrijk",
    "courtrai": "Kortrijk",
    "bruges": "Bruges",
    "brugge": "Bruges",
    "ostend": "Ostend",
    "oostende": "Ostend",
    "roeselare": "Roeselare",
    "sint-niklaas": "Sint-Niklaas",
    "genk": "Genk",
}

BELGIAN_POSTCODE_CITY = {
    "1000": "Brussels", "1030": "Schaerbeek", "1040": "Etterbeek",
    "1050": "Ixelles", "1070": "Anderlecht", "1160": "Auderghem",
    "1200": "Woluwe-Saint-Lambert", "1150": "Woluwe-Saint-Pierre",
    "1800": "Vilvoorde", "1830": "Machelen", "1930": "Zaventem",
    "3000": "Leuven", "2800": "Mechelen", "2000": "Antwerp",
    "9000": "Ghent", "3500": "Hasselt", "9300": "Aalst",
    "1300": "Wavre", "1410": "Waterloo", "1420": "Braine-l'Alleud",
    "1400": "Nivelles", "6000": "Charleroi", "5000": "Namur",
    "4000": "Liège", "7000": "Mons", "8500": "Kortrijk",
    "8000": "Bruges", "8400": "Ostend", "8800": "Roeselare",
    "9100": "Sint-Niklaas", "3600": "Genk",
}

def _location_from_text(text):
    """Return a conservative Belgian city match from bounded vacancy text."""
    value = clean(text)
    if not value:
        return ""

    # Belgian postcode is stronger evidence than a loose city mention.
    for postcode, city in BELGIAN_POSTCODE_CITY.items():
        if re.search(rf"(?<!\d){re.escape(postcode)}(?!\d)", value):
            return city

    low = value.lower()
    # Prefer longer aliases first so compound municipality names win.
    for alias in sorted(BELGIAN_LOCATION_ALIASES, key=len, reverse=True):
        if re.search(r"(?<![\w-])" + re.escape(alias) + r"(?![\w-])", low, re.I):
            return BELGIAN_LOCATION_ALIASES[alias]
    return ""

def _meta_location(soup):
    candidates = []
    for tag in soup.find_all("meta"):
        key = clean(
            tag.get("name")
            or tag.get("property")
            or tag.get("itemprop")
            or ""
        ).lower()
        if any(token in key for token in ("location", "locality", "address", "city")):
            content = clean(tag.get("content"))
            if content:
                candidates.append(content)
    for candidate in candidates:
        resolved = _location_from_text(candidate)
        if resolved:
            return resolved
    return ""

def _structured_location(soup):
    """Inspect data attributes and JSON/application state for location fields."""
    # ATS HTML often exposes the city in data-* attributes.
    for tag in soup.find_all(True):
        for key, value in tag.attrs.items():
            if "location" not in str(key).lower() and "city" not in str(key).lower():
                continue
            if isinstance(value, list):
                value = " ".join(map(str, value))
            resolved = _location_from_text(value)
            if resolved:
                return resolved

    # Inspect scripts, but only around explicit location/address keys to avoid
    # accidentally taking a city from unrelated navigation/footer content.
    for script in soup.find_all("script"):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        for match in re.finditer(
            r'(?i)(?:jobLocation|location|addressLocality|city)'
            r'["\']?\s*[:=]\s*["\']([^"\']{2,120})',
            raw,
        ):
            resolved = _location_from_text(match.group(1))
            if resolved:
                return resolved
    return ""

def _location_candidates_v49(soup, description="", existing=""):
    """Collect bounded location evidence for V4.9 diagnostics."""
    evidence = []

    def add(source_name, raw):
        raw = clean(raw)
        if not raw:
            return
        resolved = _location_from_text(raw)
        evidence.append({
            "source": source_name,
            "raw": raw[:220],
            "resolved": resolved,
        })

    add("existing", existing)

    selectors = [
        "[class*='location']", "[class*='Location']",
        "[id*='location']", "[id*='Location']",
        "[data-testid*='location']", "[data-test*='location']",
        "[itemprop='jobLocation']", "[itemprop='addressLocality']",
        "[class*='city']", "[id*='city']",
    ]
    for selector in selectors:
        try:
            elements = soup.select(selector)
        except Exception:
            elements = []
        for element in elements[:12]:
            add("dom", element.get_text(" ", strip=True))

    for tag in soup.find_all("meta"):
        key = clean(
            tag.get("name") or tag.get("property") or tag.get("itemprop") or ""
        ).lower()
        if any(token in key for token in ("location", "locality", "address", "city")):
            add("meta", tag.get("content"))

    for tag in soup.find_all(True):
        for key, value in tag.attrs.items():
            key_low = str(key).lower()
            if "location" not in key_low and "city" not in key_low and "address" not in key_low:
                continue
            if isinstance(value, list):
                value = " ".join(map(str, value))
            add("attribute", value)

    for script in soup.find_all("script"):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        for match in re.finditer(
            r'(?i)(?:jobLocation|location|addressLocality|addressRegion|city)'
            r'["\']?\s*[:=]\s*["\']([^"\']{2,160})',
            raw,
        ):
            add("structured", match.group(1))

    page_text = clean(soup.get_text(" ", strip=True))
    for match in re.finditer(
        r"(?i)\b(?:location|locatie|lieu|standplaats|werkplaats|workplace|office|site)"
        r"\s*[:\-]\s*([^|•;\n]{2,120})",
        page_text,
    ):
        add("label", match.group(1))

    add("description", description)

    # De-duplicate evidence while preserving order.
    unique = []
    seen = set()
    for item in evidence:
        key = (item["source"], item["raw"].lower(), item["resolved"].lower())
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique


def resolve_location_v49(soup, description="", existing="", return_diagnostics=False):
    """
    V4.9 resolver. Keeps V4.8's conservative behavior but records where
    location evidence came from and what unresolved candidates were visible.
    """
    evidence = _location_candidates_v49(soup, description, existing)

    priority = {
        "existing": 0, "dom": 1, "meta": 2, "attribute": 3,
        "structured": 4, "label": 5, "description": 6,
    }
    resolved_items = [x for x in evidence if x["resolved"]]
    resolved_items.sort(key=lambda x: priority.get(x["source"], 99))

    if resolved_items:
        best = resolved_items[0]
        result = (best["resolved"], best["source"])
    else:
        result = ("", "unknown")

    if return_diagnostics:
        return result[0], result[1], evidence
    return result




# ============================================================
# V5.0 BELGIUM-FIRST COUNTRY / FLEXIBLE LOCATION VALIDATION
# ============================================================

FOREIGN_COUNTRY_MARKERS = {
    "NL": "Netherlands",
    "PT": "Portugal",
    "CA": "Canada",
    "US": "United States",
    "RO": "Romania",
    "LU": "Luxembourg",
    "FR": "France",
    "DE": "Germany",
    "GB": "United Kingdom",
    "UK": "United Kingdom",
    "ES": "Spain",
    "IT": "Italy",
}

FOREIGN_CITY_MARKERS = {
    "utrecht": "Netherlands",
    "rotterdam": "Netherlands",
    "amsterdam": "Netherlands",
    "lisboa": "Portugal",
    "lisbon": "Portugal",
    "vancouver": "Canada",
    "new york": "United States",
    "bucharest": "Romania",
    "bertrange": "Luxembourg",
    "luxembourg": "Luxembourg",
}

def classify_country_v50(location="", evidence="", url=""):
    """
    Conservative country classification.
    Explicit foreign location evidence wins. Unknown stays unknown.
    """
    raw = " | ".join([clean(location), clean(evidence), clean(url)])
    low = raw.lower()

    # Explicit Belgium indicators.
    if re.search(r"(?<![A-Z])BE(?![A-Z])", raw, re.I) or "belgium" in low or "belgië" in low or "belgique" in low:
        # Do not let a generic BE site path override an explicit foreign vacancy city.
        for city, country in FOREIGN_CITY_MARKERS.items():
            if city in low:
                return "OUTSIDE_BELGIUM", country
        return "BELGIUM", "Belgium"

    # Strong country-code patterns from ATS location strings.
    for code, country in FOREIGN_COUNTRY_MARKERS.items():
        if re.search(rf"(?:,\s*|\b){re.escape(code)}(?:\b|,)", raw, re.I):
            return "OUTSIDE_BELGIUM", country

    for city, country in FOREIGN_CITY_MARKERS.items():
        if city in low:
            return "OUTSIDE_BELGIUM", country

    return "COUNTRY_UNKNOWN", ""

def is_belgium_flexible_v50(location="", work_mode=""):
    low = f"{clean(location)} {clean(work_mode)}".lower()
    belgium_hint = bool(
        re.search(r"(?<![a-z])be(?![a-z])", low)
        or "belgium" in low
        or "belgië" in low
        or "belgique" in low
    )
    flexible_hint = any(
        token in low
        for token in (
            "flexible", "customer site", "customer-site",
            "client site", "client-site", "multiple locations",
        )
    )
    return belgium_hint and flexible_hint

def normalize_resolved_location_v50(location="", evidence=""):
    """
    Fixes the V4.9 propagation issue: if JSON-LD/raw location contains a
    Belgian postcode/city that our resolver recognizes, return the resolved city.
    """
    raw = clean(location)
    resolved = _location_from_text(raw)
    if resolved:
        return resolved

    try:
        items = json.loads(evidence) if evidence else []
    except Exception:
        items = []

    for item in items:
        resolved = clean(item.get("resolved", ""))
        if resolved:
            return resolved
        resolved = _location_from_text(item.get("raw", ""))
        if resolved:
            return resolved

    return raw

def company_location_fallback_v50(company, location="", description=""):
    """
    Conservative company fallback. V5.0 deliberately does not invent a city
    for consultancies or customer-site assignments.
    """
    if clean(location):
        return clean(location), ""

    company_low = clean(company).lower()

    # Smals vacancies are handled as Brussels only when the vacancy text itself
    # contains a Brussels indicator. Otherwise remain unknown.
    if company_low == "smals":
        resolved = _location_from_text(description)
        if resolved:
            return resolved, "smals_description"

    return "", ""


def make_job(
    source,
    title,
    description,
    url,
    location="",
    employment_type="",
):

    return {
        "title": clean(title),
        "job_family": family(title),
        "company": source["company"],
        "location": clean(location),
        "region": "",
        "salary": "",
        "employment_type": clean(
            employment_type
        ),
        "url": url,
        "description": clean(
            description
        ),
        "source": (
            source["company"]
            .lower()
            .replace(" ", "_")
            + "_web"
        ),
        "location_resolution_source": "",
        "location_evidence": "",
        "canonical_url": canonical_job_url(url) if "canonical_job_url" in globals() else clean(url),
        "job_reference": "",
        "country_status": "COUNTRY_UNKNOWN",
        "country": "",
        "location_status_v50": "",
    }



def vacancy_page_evidence(soup, source, url):
    """
    V4.2 guard against blog/service/navigation pages becoming vacancies.

    JSON-LD JobPosting pages bypass this check because that is already strong
    structured vacancy evidence. Visible-page fallback must provide multiple
    independent job signals.
    """
    page_text = clean(soup.get_text(" ", strip=True)).lower()
    title = page_title(soup).lower()
    path = urlparse(url).path.lower()

    expired_signals = [
        "this vacancy has now expired",
        "this job has expired",
        "vacature is verlopen",
        "offre d'emploi a expiré",
        "offre d’emploi a expiré",
    ]
    if any(signal in page_text for signal in expired_signals):
        return False, "expired vacancy"

    # Strong negative signals for editorial/service content.
    editorial_title = re.search(
        r"\b(how|why|what|insight|insights|blog|news|webinar|whitepaper|"
        r"case study|makes data|our services|solution|solutions)\b",
        title,
        flags=re.I,
    )

    apply_signal = bool(re.search(
        r"\b(apply|apply now|application|solliciteer|solliciteren|"
        r"postulez|postuler|candidature)\b",
        page_text,
        flags=re.I,
    ))
    vacancy_signal = bool(re.search(
        r"\b(job description|job details|qualifications|requirements|"
        r"vacancy|vacature|functie-eisen|functieomschrijving|"
        r"offre d['’]emploi|description du poste|profil recherché)\b",
        page_text,
        flags=re.I,
    ))
    employment_signal = bool(re.search(
        r"\b(full[- ]time|part[- ]time|permanent|contract|employment type|"
        r"voltijds|deeltijds|onbepaalde duur|temps plein|cdi)\b",
        page_text,
        flags=re.I,
    ))
    career_url_signal = bool(re.search(
        r"/(job|jobs|career|careers|vacanc|vacature|offre)",
        path,
        flags=re.I,
    ))

    score = sum([
        apply_signal,
        vacancy_signal,
        employment_signal,
        career_url_signal,
    ])

    # WordPress/company sites are particularly prone to matching articles and
    # service pages, so require an explicit application/vacancy signal.
    if source.get("type") == "wordpress_jobs":
        if editorial_title and not apply_signal:
            return False, "editorial/service page"
        if not apply_signal:
            return False, "no application signal"
        if score < 2:
            return False, "insufficient vacancy evidence"
        return True, "validated"

    if editorial_title and score < 3:
        return False, "editorial/service page"

    if score < 2:
        return False, "insufficient vacancy evidence"

    return True, "validated"


def extract_detail_job(
    html,
    source,
    url,
):

    # First try JobPosting JSON-LD.

    job = extract_jsonld_job(
        html,
        source,
        url,
    )

    if job:
        return job

    # Then parse visible page content.

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    title = page_title(soup)

    fam = family(title)

    if not fam:
        return None

    valid_page, validation_reason = vacancy_page_evidence(
        soup,
        source,
        url,
    )

    if not valid_page:
        print(
            "  rejected non-vacancy page:",
            title or url,
            "->",
            validation_reason,
        )
        return None

    description = page_description(
        soup
    )

    if len(description) < 150:
        return None

    location, location_source, location_evidence = resolve_location_v49(
        soup,
        description,
        existing=guess_location(soup, description),
        return_diagnostics=True,
    )

    job = make_job(
        source,
        title,
        description,
        url,
        location,
    )
    job["location_resolution_source"] = location_source
    job["location_evidence"] = json.dumps(location_evidence, ensure_ascii=False)
    return job


# ============================================================
# LINK DISCOVERY
# ============================================================

def discover_from_listing(
    html,
    source,
):

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    candidates = []

    for anchor in soup.find_all(
        "a",
        href=True,
    ):

        href = anchor.get("href")

        url = normalize_url(
            href,
            source["url"],
        )

        if not host_matches(
            url,
            source["domain"],
        ):
            continue

        if not is_job_url(
            url,
            source,
        ):
            continue

        text = clean(
            anchor.get_text(
                " ",
                strip=True,
            )
        )

        slug = (
            urlparse(url)
            .path
            .split("/")[-1]
            .replace("-", " ")
            .replace("_", " ")
        )

        combined = clean(
            text + " " + slug
        )

        # This is the important anti-rate-limit change.
        #
        # We only open details when either the visible title
        # or URL slug looks relevant to our target families.

        if looks_targeted(combined):
            candidates.append(
                (url, text)
            )

    unique = {}

    for url, text in candidates:
        unique[url] = text

    return [
        (url, text)
        for url, text
        in unique.items()
    ]


# ============================================================
# PAGINATION
# ============================================================

def pagination_links(
    html,
    source,
):

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    pages = []

    for anchor in soup.find_all(
        "a",
        href=True,
    ):

        href = anchor["href"]

        url = normalize_url(
            href,
            source["url"],
        )

        if not host_matches(
            url,
            source["domain"],
        ):
            continue

        if re.search(
            r"[?&]page=\d+",
            url,
            re.I,
        ):
            pages.append(url)

    return list(
        dict.fromkeys(pages)
    )


# ============================================================
# CEGEKA
# ============================================================

def discover_cegeka(source):
    print("  strategy: Cegeka automatic rendered-listing discovery")

    listing = source["url"]
    candidates = []

    try:
        html = fetch(listing)
        soup = BeautifulSoup(html, "html.parser")

        all_job_links = {}
        for a in soup.find_all("a", href=True):
            url = normalize_url(a["href"], listing)
            if not host_matches(url, source["domain"]):
                continue
            if not is_job_url(url, source):
                continue
            title = clean(a.get_text(" ", strip=True))
            all_job_links[url] = title

        print("  discovered vacancy links:", len(all_job_links))

        for url, title in all_job_links.items():
            parts = [p for p in urlparse(url).path.split("/") if p]
            slug = parts[-1].replace("-", " ") if parts else ""
            if looks_targeted(clean(title + " " + slug)):
                candidates.append((url, title))

    except Exception as exc:
        print("  Cegeka listing skipped:", exc)

    # Search fallback only; no live seeds.
    if not candidates:
        queries = [
            'site:cegeka.com/en/be/jobs/all-jobs/ "Data Analyst"',
            'site:cegeka.com/en/be/jobs/all-jobs/ "BI" OR "Business Intelligence"',
            'site:cegeka.com/en/be/jobs/all-jobs/ "Data Engineer"',
            'site:cegeka.com/en/be/jobs/all-jobs/ "Data Governance"',
            'site:cegeka.com/en/be/jobs/all-jobs/ "Data Quality"',
            'site:cegeka.com/en/be/jobs/all-jobs/ "Power BI"',
        ]
        for query in queries:
            for finder in (search_discovery, search_discovery_bing):
                try:
                    found = finder(query, domains=["cegeka.com"], max_results=25)
                    for url, title in found:
                        if is_job_url(url, source) and looks_targeted(
                            clean(title + " " + urlparse(url).path.replace("-", " "))
                        ):
                            candidates.append((url, title))
                except Exception as exc:
                    print("  Cegeka indexed fallback skipped:", exc)

    unique = {}
    for url, title in candidates:
        unique[url] = title
    result = list(unique.items())
    print("  relevant vacancy links:", len(result))
    return result



def discover_smals(source):

    print(
        "  strategy: Smals title listing"
    )

    html = fetch(
        source["url"]
    )

    candidates = discover_from_listing(
        html,
        source,
    )

    print(
        "  relevant vacancy links:",
        len(candidates),
    )

    return candidates


# ============================================================
# PAUWELS
# ============================================================

def discover_pauwels(source):

    print(
        "  strategy: Pauwels filtered pagination"
    )

    queue = [
        source["url"]
    ]

    visited = set()

    candidates = []

    while (
        queue
        and len(visited) < 25
    ):

        url = queue.pop(0)

        if url in visited:
            continue

        visited.add(url)

        try:
            html = fetch(url)

        except Exception as exc:

            print(
                "  listing skipped:",
                exc,
            )

            continue

        candidates.extend(
            discover_from_listing(
                html,
                source,
            )
        )

        for page in pagination_links(
            html,
            source,
        ):

            if (
                page not in visited
                and page not in queue
            ):
                queue.append(page)

        # Pauwels was rate-limiting the previous scraper.
        time.sleep(1.0)

    unique = {}

    for url, text in candidates:
        unique[url] = text

    result = list(
        unique.items()
    )

    print(
        "  listing pages:",
        len(visited),
    )

    print(
        "  relevant vacancy links:",
        len(result),
    )

    return result


# ============================================================
# CAPGEMINI
# ============================================================

def discover_capgemini(source):
    print("  strategy: Capgemini automatic careers discovery")

    candidates = []
    entry_pages = [
        source["url"],
        "https://careers.capgemini.com/search/",
        "https://careers.capgemini.com/go/Belgium/3774601/",
    ]

    direct = 0
    for entry in entry_pages:
        try:
            html = fetch(entry)
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a", href=True):
                url = normalize_url(a["href"], entry)
                host = urlparse(url).netloc.lower()
                if "capgemini.com" not in host:
                    continue
                path = urlparse(url).path.lower()
                if "/job/" not in path:
                    continue
                title = clean(a.get_text(" ", strip=True))
                slug = path.replace("-", " ")
                if looks_targeted(clean(title + " " + slug)):
                    candidates.append((url, title))
                    direct += 1
        except Exception as exc:
            print("  Capgemini entry skipped:", entry, "->", exc)
        time.sleep(0.35)

    print("  direct target candidates:", direct)

    queries = [
        'site:careers.capgemini.com/job/ Belgium "Data Analyst"',
        'site:careers.capgemini.com/job/ Belgium "BI Engineer"',
        'site:careers.capgemini.com/job/ Belgium "Power BI"',
        'site:careers.capgemini.com/job/ Belgium "Business Intelligence"',
        'site:careers.capgemini.com/job/ Belgium "Data Engineer"',
        'site:careers.capgemini.com/job/ Belgium "Data Governance"',
        'site:careers.capgemini.com/job/ Belgium "Data Quality"',
        'site:careers.capgemini.com/job/ Belgium "Reporting"',
    ]
    indexed = 0
    for query in queries:
        for finder in (search_discovery, search_discovery_bing):
            try:
                found = finder(query, domains=["careers.capgemini.com"], max_results=25)
                for url, title in found:
                    if "/job/" not in urlparse(url).path.lower():
                        continue
                    if looks_targeted(clean(title + " " + urlparse(url).path.replace("-", " "))):
                        candidates.append((url, title))
                        indexed += 1
            except Exception as exc:
                print("  Capgemini indexed discovery skipped:", exc)
        time.sleep(0.35)

    print("  indexed target candidates:", indexed)

    unique = {}
    for url, title in candidates:
        # strip common tracking fragments/query params for URL-level dedupe
        p = urlparse(url)
        canonical = p._replace(query="", fragment="").geturl()
        unique[canonical] = title

    result = list(unique.items())
    print("  relevant vacancy links:", len(result))
    return result



def discover_akkodis(source):
    print("  strategy: Akkodis automatic indexed vacancy discovery")

    candidates = []

    entry_pages = [
        "https://www.akkodis.com/en-be/careers",
        "https://www.akkodis.com/en-be/careers/jobs",
        "https://www.akkodis.com/en/careers/job-results-global",
    ]

    direct = 0
    for entry in entry_pages:
        try:
            html = fetch(entry)
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a", href=True):
                url = normalize_url(a["href"], entry)
                if "akkodis.com" not in urlparse(url).netloc.lower():
                    continue
                path = urlparse(url).path.lower()
                if "/careers/jobs/" not in path:
                    continue
                title = clean(a.get_text(" ", strip=True))
                slug = path.replace("-", " ")
                if looks_targeted(clean(title + " " + slug)):
                    candidates.append((url, title))
                    direct += 1
        except Exception as exc:
            print("  Akkodis entry skipped:", entry, "->", exc)
        time.sleep(0.35)

    print("  direct target candidates:", direct)

    queries = [
        'site:akkodis.com/en-be/careers/jobs/ "Data Analyst"',
        'site:akkodis.com/en-be/careers/jobs/ "Data Analist"',
        'site:akkodis.com/en-be/careers/jobs/ "Business Intelligence"',
        'site:akkodis.com/en-be/careers/jobs/ "Power BI"',
        'site:akkodis.com/en-be/careers/jobs/ "Data Engineer"',
        'site:akkodis.com/en-be/careers/jobs/ "Data Governance"',
        'site:akkodis.com/en-be/careers/jobs/ "Data Quality"',
        'site:akkodis.com/en-be/careers/jobs/ "Reporting Analyst"',
        'site:akkodis.com/en-be/careers/jobs/ "Functional Analyst" data',
        'site:akkodis.com/en/careers/jobs/ Belgium "Data Analyst"',
        'site:akkodis.com/en/careers/jobs/ Belgium "Data Engineer"',
    ]

    indexed = 0
    for query in queries:
        for finder in (search_discovery, search_discovery_bing):
            try:
                found = finder(query, domains=["akkodis.com"], max_results=30)
                for url, title in found:
                    path = urlparse(url).path.lower()
                    if "/careers/jobs/" not in path:
                        continue
                    hay = clean(title + " " + path.replace("-", " "))
                    if looks_targeted(hay):
                        candidates.append((url, title))
                        indexed += 1
            except Exception as exc:
                print("  Akkodis indexed discovery skipped:", exc)
        time.sleep(0.35)

    print("  indexed target candidates:", indexed)

    unique = {}
    for url, title in candidates:
        p = urlparse(url)
        canonical = p._replace(query="", fragment="").geturl()
        unique[canonical] = title

    result = list(unique.items())
    print("  relevant vacancy links:", len(result))
    return result




def discover_generic(source):
    print("  strategy: V4 generic listing adapter")
    candidates = []
    total_job_links = 0
    try:
        html = fetch(source["url"])
        soup = BeautifulSoup(html, "html.parser")
        for anchor in soup.find_all("a", href=True):
            url = normalize_url(anchor.get("href"), source["url"])
            if not host_matches(url, source["domain"]) or not is_job_url(url, source):
                continue
            total_job_links += 1
            title = clean(anchor.get_text(" ", strip=True))
            slug = urlparse(url).path.replace("-", " ").replace("_", " ")
            if looks_targeted(clean(title + " " + slug)):
                candidates.append((url, title))
    except Exception as exc:
        print("  generic listing error:", exc)

    print("  discovered vacancy links:", total_job_links)

    if not candidates:
        company = source["company"]
        queries = [
            f'site:{source["domain"]} "{company}" "Data Analyst"',
            f'site:{source["domain"]} "{company}" "Power BI"',
            f'site:{source["domain"]} "{company}" "Business Intelligence"',
            f'site:{source["domain"]} "{company}" "Data Governance"',
            f'site:{source["domain"]} "{company}" "Data Engineer"',
        ]
        for query in queries:
            for finder in (search_discovery, search_discovery_bing):
                try:
                    for url, title in finder(query, domains=[source["domain"]], max_results=20):
                        if host_matches(url, source["domain"]) and is_job_url(url, source):
                            hay = clean(title + " " + urlparse(url).path.replace("-", " "))
                            if looks_targeted(hay):
                                candidates.append((url, title))
                except Exception as exc:
                    print("  indexed fallback skipped:", exc)

    unique = {}
    for url, title in candidates:
        p = urlparse(url)
        unique[p._replace(query="", fragment="").geturl()] = title
    result = list(unique.items())
    print("  relevant vacancy links:", len(result))
    return result



DISCOVERY_HEALTH = {}


def discover_ats(source):
    """
    V4.1 reusable ATS/listing adapter.
    It scans the configured listing first and only falls back to indexed
    discovery when the listing does not expose target roles.
    """
    platform = source["type"]
    company = source["company"]
    print(f"  strategy: V4.3 {platform} adapter")

    inventory = []
    targeted = []
    listing_ok = False
    fallback_used = False
    error_text = ""

    try:
        html = fetch(source["url"])
        listing_ok = True
        soup = BeautifulSoup(html, "html.parser")

        for anchor in soup.find_all("a", href=True):
            url = normalize_url(anchor.get("href"), source["url"])

            if not host_matches(url, source["domain"]):
                continue
            if not is_job_url(url, source):
                continue

            title = clean(anchor.get_text(" ", strip=True))
            slug = clean(urlparse(url).path.replace("-", " ").replace("_", " "))

            # Many ATS cards use generic anchor labels such as "Read more".
            # Inspect a bounded parent-card context so the actual vacancy
            # title can still drive targeting.
            parent_text = ""
            parent = anchor.find_parent(
                ["article", "li", "div", "section"]
            )
            if parent:
                parent_text = clean(
                    parent.get_text(" ", strip=True)
                )[:600]

            inventory.append((url, title))

            discovery_text = clean(
                " ".join([
                    title,
                    slug,
                    parent_text,
                ])
            )

            if looks_targeted(discovery_text):
                # Preserve a useful listing title when the anchor itself is
                # only "Read more", "View job", etc.
                useful_title = title
                if (
                    not useful_title
                    or useful_title.lower() in {
                        "read more", "view job", "view vacancy",
                        "learn more", "details", "apply",
                    }
                ):
                    useful_title = parent_text[:180]
                targeted.append((url, useful_title))

    except Exception as exc:
        error_text = str(exc)
        print("  listing error:", exc)

    # De-duplicate inventory before reporting health.
    inv_unique = {}
    for url, title in inventory:
        p = urlparse(url)
        inv_unique[p._replace(query="", fragment="").geturl()] = title
    inventory = list(inv_unique.items())

    print("  vacancy inventory links:", len(inventory))
    print("  direct target candidates:", len(targeted))

    # Indexed fallback is a resilience layer, not the primary scraper.
    if not targeted:
        fallback_used = True
        queries = [
            f'site:{source["domain"]} "{company}" "Data Analyst"',
            f'site:{source["domain"]} "{company}" "Power BI"',
            f'site:{source["domain"]} "{company}" "Business Intelligence"',
            f'site:{source["domain"]} "{company}" "Data Governance"',
            f'site:{source["domain"]} "{company}" "Data Quality"',
            f'site:{source["domain"]} "{company}" "Data Engineer"',
        ]

        for query in queries:
            for finder in (search_discovery, search_discovery_bing):
                try:
                    for url, title in finder(
                        query,
                        domains=[source["domain"]],
                        max_results=20,
                    ):
                        if not host_matches(url, source["domain"]):
                            continue
                        if not is_job_url(url, source):
                            continue

                        hay = clean(
                            title + " "
                            + urlparse(url).path.replace("-", " ").replace("_", " ")
                        )
                        if looks_targeted(hay):
                            targeted.append((url, title))
                except Exception:
                    # Search engines can throttle CI runners; this must not
                    # turn a healthy direct listing into a source failure.
                    pass

    unique = {}
    for url, title in targeted:
        p = urlparse(url)
        canonical = p._replace(query="", fragment="").geturl()
        unique[canonical] = title
    result = list(unique.items())

    if not listing_ok:
        status = "BROKEN"
    elif inventory and result:
        status = "HEALTHY"
    elif inventory and not result:
        # Only claim NO_MATCHES when most inventory links expose meaningful
        # titles. Generic labels/blank titles mean discovery is incomplete.
        meaningful_titles = sum(
            1
            for _, title in inventory
            if title
            and title.lower() not in {
                "read more", "view job", "view vacancy",
                "learn more", "details", "apply",
            }
            and len(title) >= 4
        )
        coverage = meaningful_titles / max(1, len(inventory))
        status = "NO_MATCHES" if coverage >= 0.70 else "PARTIAL"
    elif result:
        status = "PARTIAL"
    else:
        status = "UNKNOWN"

    DISCOVERY_HEALTH[company] = {
        "status": status,
        "inventory": len(inventory),
        "targets": len(result),
        "fallback": fallback_used,
        "error": error_text,
    }

    print("  relevant vacancy links:", len(result))
    return result



def discover_recovery_v43(source):
    """Recovery layer for sources that remained incomplete in V4.2."""
    company = source["company"]
    inventory, candidates = [], []
    pages_ok = 0

    if company == "Cegeka":
        entries = [source["url"]]
        patterns = [r"/(?:en/be/jobs/all-jobs|nl-be/jobs/vacatures)/[^/?#]+-\d+/?$"]
        queries = [
            'site:cegeka.com/en/be/jobs/all-jobs "Data Analyst"',
            'site:cegeka.com/en/be/jobs/all-jobs "Data Engineer"',
            'site:cegeka.com/en/be/jobs/all-jobs "Data Governance"',
            'site:cegeka.com/nl-be/jobs/vacatures "Data Platform Analyst"',
            'site:cegeka.com/nl-be/jobs/vacatures "Power BI"',
        ]
        domains = ["cegeka.com"]

    elif company == "Akkodis":
        entries = [
            "https://www.akkodis.com/en/careers",
            "https://www.akkodis.com/en/career-overview",
        ]
        patterns = [r"/en-be/careers/jobs/[^/]+/\d{4}-\d+/?$"]
        queries = [
            'site:akkodis.com/en-be/careers/jobs "Data Engineer"',
            'site:akkodis.com/en-be/careers/jobs "Data Analyst"',
            'site:akkodis.com/en-be/careers/jobs "Business Analyst" data',
            'site:akkodis.com/en-be/careers/jobs "Power BI"',
            'site:akkodis.com/en-be/careers/jobs "Data Governance"',
        ]
        domains = ["akkodis.com"]

    elif company in {"Infrabel", "HR Rail"}:
        entries = [source["url"]]
        if company == "Infrabel":
            entries += [
                "https://jobs.infrabel.be/go/ICT-FR/959402/",
                "https://jobs.infrabel.be/go/ICT-NL/959502/",
            ]
        expanded=[]
        for base in entries:
            expanded.append(base)
            for offset in (25,50,75,100):
                expanded.append(base+("&" if "?" in base else "?")+f"startrow={offset}")
        entries=expanded
        patterns=[r"/job/[^/]+/\d+(?:-[A-Za-z_]+)?/?$"]
        queries=[
            f'site:{source["domain"]} "{company}" "{term}"'
            for term in ("Data Analyst","Data Engineer","Power BI","Business Intelligence","Data Governance")
        ]
        domains=[source["domain"]]

    elif company == "Sopra Steria":
        entries=[source["url"]]
        patterns=[r"/job/[^/?#]+-jid-\d+/?$"]
        queries=[
            f'site:careers.soprasteria.be/job "{term}"'
            for term in ("Data Analyst","Data Governance","Power BI","Business Intelligence","Data Engineer")
        ]
        domains=[source["domain"]]
    else:
        return None

    for entry in entries:
        try:
            html=fetch(entry); pages_ok += 1
            soup=BeautifulSoup(html,"html.parser")
            for a in soup.find_all("a",href=True):
                url=normalize_url(a["href"],entry)
                path=urlparse(url).path
                if not any(re.search(p,path,re.I) for p in patterns):
                    continue
                title=clean(a.get_text(" ",strip=True))
                parent=a.find_parent(["article","li","div","section","tr"])
                context=clean(parent.get_text(" ",strip=True))[:800] if parent else ""
                inventory.append((url,title))
                if looks_targeted(clean(title+" "+context+" "+path.replace("-"," "))):
                    candidates.append((url,title or context[:180]))
        except Exception:
            pass

    # Search-index recovery supplements direct discovery.
    for q in queries:
        for finder in (search_discovery,search_discovery_bing):
            try:
                for url,title in finder(q,domains=domains,max_results=20):
                    path=urlparse(url).path
                    if any(re.search(p,path,re.I) for p in patterns):
                        candidates.append((url,title))
            except Exception:
                pass

    inv={urlparse(u)._replace(query="",fragment="").geturl():x for u,x in inventory}
    res={urlparse(u)._replace(query="",fragment="").geturl():x for u,x in candidates}
    result=list(res.items())

    if inv and result:
        status="HEALTHY"
    elif result or inv:
        status="PARTIAL"
    elif pages_ok:
        status="UNKNOWN"
    else:
        status="BROKEN"

    DISCOVERY_HEALTH[company]={
        "status":status,
        "inventory":len(inv),
        "targets":len(result),
        "fallback":True,
        "error":"",
    }
    print(f"  strategy: {company} V4.3 discovery recovery")
    print("  listing pages opened:",pages_ok)
    print("  vacancy inventory links:",len(inv))
    print("  relevant vacancy links:",len(result))
    return result



def _dedup_url_pairs(pairs):
    unique = {}
    for url, title in pairs:
        p = urlparse(url)
        clean_url = p._replace(query="", fragment="").geturl()
        if clean_url not in unique or len(clean(title)) > len(clean(unique[clean_url])):
            unique[clean_url] = title
    return list(unique.items())


def discover_inventory_first_v44(source):
    """
    V4.4 discovery principle:
    discover real vacancy detail URLs first, then let extract_detail_job()
    decide whether each vacancy belongs to one of Hamza's target families.

    This avoids the V4.3 failure mode where Cegeka/Sopra exposed real job URLs
    but generic anchor labels prevented them from reaching detail validation.
    """
    company = source["company"]
    inventory = []
    pages_ok = 0

    if company == "Cegeka":
        print("  strategy: Cegeka V4.4 inventory-first detail validation")
        pages = [
            source["url"],
            "https://www.cegeka.com/nl-be/jobs/vacatures",
        ]
        patterns = [
            r"/en/be/jobs/all-jobs/[^/?#]+-\d+/?$",
            r"/nl-be/jobs/vacatures/[^/?#]+-\d+/?$",
        ]

    elif company == "Sopra Steria":
        print("  strategy: Sopra Steria V4.4 paginated inventory-first discovery")
        # The careers site exposes 12 jobs/page. Scan enough pages to cover the
        # current Belgian catalogue rather than trusting the first six anchors.
        pages = [
            f"https://careers.soprasteria.be/jobs?page={page}"
            for page in range(1, 16)
        ]
        patterns = [r"/job/[^/?#]+-jid-\d+/?$"]

    elif company == "Infrabel":
        print("  strategy: Infrabel V4.4 SuccessFactors inventory-first discovery")
        bases = [
            source["url"],
            "https://jobs.infrabel.be/go/ICT-FR/959402/",
            "https://jobs.infrabel.be/go/ICT-NL/959502/",
        ]
        pages = []
        for base in bases:
            pages.append(base)
            for offset in range(25, 251, 25):
                pages.append(
                    base + ("&" if "?" in base else "?") + f"startrow={offset}"
                )
        patterns = [
            r"/job/[^/?#]+/\d+(?:-[A-Za-z_]+)?/?$",
            r"/job/[^/?#]+/\d+/?$",
        ]

    elif company == "HR Rail":
        print("  strategy: HR Rail V4.4 corrected-domain SuccessFactors discovery")
        bases = [
            source["url"],
            "https://jobs.hr-rail.be/HRRail/go/Tous-les-vacatures-HR-Rail/957302/",
        ]
        pages = []
        for base in bases:
            pages.append(base)
            for offset in range(25, 151, 25):
                pages.append(
                    base + ("&" if "?" in base else "?") + f"startrow={offset}"
                )
        patterns = [
            r"/HRRail/job/[^/?#]+/\d+(?:-[A-Za-z_]+)?/?$",
            r"/HRRail/job/[^/?#]+/\d+/?$",
            r"/job/[^/?#]+/\d+(?:-[A-Za-z_]+)?/?$",
        ]
    else:
        return None

    for page_url in pages:
        try:
            html = fetch(page_url)
            pages_ok += 1
            soup = BeautifulSoup(html, "html.parser")

            for a in soup.find_all("a", href=True):
                url = normalize_url(a.get("href"), page_url)
                path = urlparse(url).path

                if not host_matches(url, source["domain"]):
                    continue
                if not any(re.search(p, path, flags=re.I) for p in patterns):
                    continue

                title = clean(a.get_text(" ", strip=True))
                inventory.append((url, title))

            # Recover detail URLs serialized in script/application state.
            # This is intentionally URL-only: detail parsing remains the
            # authority for title, description and target-family validation.
            for raw in re.findall(
                r'https?://[^"\'<>\s\\]+',
                html,
                flags=re.I,
            ):
                raw = raw.replace("\\/", "/")
                if not host_matches(raw, source["domain"]):
                    continue
                path = urlparse(raw).path
                if any(re.search(p, path, flags=re.I) for p in patterns):
                    inventory.append((raw, ""))

        except Exception:
            pass

    inventory = _dedup_url_pairs(inventory)

    # Critical V4.4 change: DO NOT pre-filter inventory by listing title.
    # Every discovered real vacancy detail page is opened. The existing
    # family(), vacancy validation, degree and experience rules then decide.
    result = inventory

    if inventory:
        status = "HEALTHY"
    elif pages_ok:
        status = "UNKNOWN"
    else:
        status = "BROKEN"

    DISCOVERY_HEALTH[company] = {
        "status": status,
        "inventory": len(inventory),
        "targets": len(result),
        "fallback": False,
        "error": "",
    }

    print("  listing pages opened:", pages_ok)
    print("  real vacancy detail URLs:", len(inventory))
    print("  detail pages queued for target validation:", len(result))
    return result


# ============================================================
# DISCOVERY ROUTER
# ============================================================

def discover(source):
    if source["company"] in {"Cegeka", "Sopra Steria", "Infrabel", "HR Rail"}:
        recovered = discover_inventory_first_v44(source)
        if recovered is not None:
            return recovered

    if source["company"] in {"Akkodis"}:
        recovered = discover_recovery_v43(source)
        if recovered is not None:
            return recovered


    source_type = source["type"]

    if source_type == "cegeka":
        return discover_cegeka(source)

    if source_type == "smals":
        return discover_smals(source)

    if source_type == "pauwels":
        return discover_pauwels(source)

    if source_type == "capgemini":
        return discover_capgemini(source)

    if source_type == "akkodis":
        return discover_akkodis(source)

    if source_type in {
        "generic",
        "ats_html",
        "successfactors",
        "teamtailor",
        "recruitee",
        "talentsoft",
        "wordpress_jobs",
    }:
        return discover_ats(source)

    return []


# ============================================================
# EXPERIENCE
# ============================================================

def extract_experience(text):
    """
    V4.2 conservative experience parser.

    A number is only treated as years of experience when the number and an
    explicit experience expression occur in the same local sentence/segment.
    This prevents unrelated values such as "30 countries", "30 years as a
    company", cookie durations, employee counts, etc. from becoming a job
    requirement.
    """
    lower = clean(text).lower()

    # Break long scraped pages into small requirement-like segments.
    segments = re.split(
        r"(?<=[.!?;:])\s+|\n+|\s+[•·]\s+",
        lower,
    )

    patterns = [
        # English
        r"\b(?:at\s+least|minimum(?:\s+of)?|min\.?)\s+(\d{1,2})\s*\+?\s+years?\s+(?:of\s+)?(?:relevant\s+|professional\s+|work\s+)?experience\b",
        r"\b(\d{1,2})\s*\+\s*years?\s+(?:of\s+)?(?:relevant\s+|professional\s+|work\s+)?experience\b",
        r"\b(\d{1,2})\s+years?['’]?\s+(?:of\s+)?(?:relevant\s+|professional\s+|work\s+)?experience\b",
        r"\bexperience\s+(?:of\s+)?(?:at\s+least\s+|minimum\s+)?(\d{1,2})\s*\+?\s+years?\b",

        # Dutch
        r"\b(?:minstens|minimaal|minimum)\s+(\d{1,2})\s*\+?\s+jaar\s+(?:relevante\s+|professionele\s+|werk)?ervaring\b",
        r"\b(\d{1,2})\s*\+?\s+jaar\s+(?:relevante\s+|professionele\s+|werk)?ervaring\b",
        r"\b(?:relevante\s+|professionele\s+|werk)?ervaring\s+van\s+(?:minstens\s+|minimaal\s+)?(\d{1,2})\s+jaar\b",

        # French
        r"\b(?:au\s+moins|minimum|min\.?)\s+(\d{1,2})\s*\+?\s+ans?\s+d['’e]?(?:expérience|experience)\b",
        r"\b(\d{1,2})\s*\+?\s+ans?\s+d['’e]?(?:expérience|experience)\b",
        r"\b(?:expérience|experience)\s+(?:professionnelle\s+|pertinente\s+)?(?:d['’]au\s+moins\s+|de\s+minimum\s+)?(\d{1,2})\s+ans?\b",
    ]

    years = []

    for segment in segments:
        # Experience requirements should be local and concise enough that an
        # unrelated number elsewhere on the page cannot leak into the match.
        if not re.search(
            r"\b(experience|expérience|ervaring)\b",
            segment,
            flags=re.I,
        ):
            continue

        for pattern in patterns:
            for match in re.findall(pattern, segment, flags=re.I):
                try:
                    value = int(match)
                except (TypeError, ValueError):
                    continue

                # Values above 20 are overwhelmingly page/company metadata,
                # not realistic minimum experience requirements.
                if 0 < value <= 20:
                    years.append(value)

    return max(years) if years else None


# ============================================================
# DEGREE REQUIREMENTS
# ============================================================

def degree_requirement(text):
    """Conservative education-requirement parser for V3.4."""
    lower = clean(text).lower()
    sentences = re.split(r"(?<=[.!?;:])\s+|\s+[•·]\s+|\n+", lower)

    degree_terms = re.compile(
        r"\b(bachelor(?:'s)?|master(?:'s)?|bachelordiploma|masterdiploma|"
        r"degree|diploma|diplôme|diplome)\b", re.I
    )
    technical_terms = re.compile(
        r"\b(computer science|business engineering|engineering|informatics|"
        r"information technology|business it|data science|mathematics|"
        r"statistics|ict|informatica|ingenieur|technical degree)\b", re.I
    )
    mandatory_terms = re.compile(
        r"\b(required|mandatory|must have|must possess|you have|you hold|"
        r"you possess|minimum requirement|minimum qualification|vereist|"
        r"verplicht|je hebt|u hebt|doit avoir|obligatoire|requis|requise|"
        r"vous avez|vous êtes titulaire)\b", re.I
    )
    preferred_terms = re.compile(
        r"\b(preferred|preferably|ideally|nice to have|a plus|bij voorkeur|"
        r"idealiter|de préférence|préférablement|idealement|idéalement)\b",
        re.I
    )
    equivalent_terms = re.compile(
        r"or equivalent(?: experience| qualification| background)?|"
        r"equivalent experience|equivalent qualification|"
        r"equivalent professional experience|or comparable experience|"
        r"or relevant experience|gelijkwaardige ervaring|"
        r"gelijkwaardig door ervaring|ervaring gelijkwaardig|"
        r"of gelijkwaardig|of gelijkwaardige ervaring|"
        r"expérience équivalente|experience équivalente|"
        r"ou expérience équivalente|ou équivalent", re.I
    )

    contexts = []
    for sentence in sentences:
        sentence = clean(sentence)
        if not degree_terms.search(sentence):
            continue

        if "master data" in sentence:
            academic_master = re.search(
                r"\bmaster(?:'s)?\s+(?:degree|diploma)\b|"
                r"\b(?:degree|diploma)\b.{0,50}\bmaster\b|"
                r"\bmaster\b.{0,60}\b(?:university|academic|education)\b",
                sentence, re.I
            )
            if not academic_master and not re.search(
                r"\bbachelor(?:'s)?\b|\bbachelordiploma\b", sentence, re.I
            ):
                continue

        contexts.append(sentence)

    if not contexts:
        return "not specified"

    classifications = []

    for context in contexts:
        equivalent = bool(equivalent_terms.search(context))
        preferred = bool(preferred_terms.search(context))
        mandatory = bool(mandatory_terms.search(context))
        bachelor = bool(re.search(
            r"\bbachelor(?:'s)?\b|\bbachelordiploma\b", context, re.I
        ))
        master = bool(re.search(
            r"\bmaster(?:'s)?\b|\bmasterdiploma\b", context, re.I
        ))
        bachelor_or_master = bool(re.search(
            r"\bbachelor.{0,45}(?:or|of|ou|/).{0,45}master\b|"
            r"\bmaster.{0,45}(?:or|of|ou|/).{0,45}bachelor\b",
            context, re.I
        ))
        technical = bool(technical_terms.search(context))

        if bachelor_or_master:
            if equivalent:
                classifications.append("Bachelor's/Master's or equivalent experience")
            elif preferred:
                classifications.append("Bachelor's/Master's preferred")
            elif technical and mandatory:
                classifications.append("mandatory Bachelor/Master in technical field")
            elif technical:
                classifications.append("Bachelor's/Master's in technical field")
            else:
                classifications.append("Bachelor's or Master's degree")
            continue

        if master:
            if equivalent:
                classifications.append("Master's or equivalent experience")
            elif preferred:
                classifications.append("Master's preferred")
            elif technical and mandatory:
                classifications.append("mandatory Master's in technical field")
            elif mandatory:
                classifications.append("mandatory Master's")
            elif technical:
                classifications.append("Master's in technical field")
            else:
                classifications.append("Master's degree mentioned")
            continue

        if bachelor:
            if equivalent:
                classifications.append("Bachelor's or equivalent experience")
            elif preferred:
                classifications.append("Bachelor's preferred")
            elif technical and mandatory:
                classifications.append("mandatory Bachelor's in technical field")
            elif technical:
                classifications.append("Bachelor's in technical field")
            else:
                classifications.append("Bachelor's degree")
            continue

        if technical:
            if equivalent:
                classifications.append("technical degree or equivalent experience")
            elif preferred:
                classifications.append("technical degree preferred")
            elif mandatory:
                classifications.append("mandatory specific technical degree")
            else:
                classifications.append("technical degree mentioned")

    if not classifications:
        return "not specified"

    priority = [
        "mandatory Master's in technical field",
        "mandatory Master's",
        "mandatory Bachelor/Master in technical field",
        "mandatory Bachelor's in technical field",
        "mandatory specific technical degree",
        "Master's or equivalent experience",
        "Bachelor's/Master's or equivalent experience",
        "technical degree or equivalent experience",
        "Bachelor's or equivalent experience",
        "Master's preferred",
        "Bachelor's/Master's preferred",
        "technical degree preferred",
        "Bachelor's preferred",
        "Master's in technical field",
        "Bachelor's/Master's in technical field",
        "Bachelor's in technical field",
        "technical degree mentioned",
        "Master's degree mentioned",
        "Bachelor's or Master's degree",
        "Bachelor's degree",
    ]

    for label in priority:
        if label in classifications:
            return label

    return classifications[0]

# ============================================================
# LANGUAGES
# ============================================================

def extract_languages(text):

    text = text.lower()

    result = []

    language_terms = {
        "Dutch": [
            "dutch",
            "nederlands",
            "néerlandais",
            "landstalen",
        ],
        "French": [
            "french",
            "français",
            "francais",
            "frans",
            "landstalen",
        ],
        "English": [
            "english",
            "engels",
            "anglais",
        ],
    }

    for language, terms in (
        language_terms.items()
    ):

        if any(
            term in text
            for term in terms
        ):
            result.append(language)

    return ", ".join(result)


# ============================================================
# SKILLS
# ============================================================

def skill_information(job):

    text = (
        job["title"]
        + " "
        + job["description"]
    ).lower()

    matched = []

    for skill in SKILLS:

        if skill in text:
            matched.append(skill)

    gaps = []

    for skill in GAP_SKILLS:

        if skill in text:
            gaps.append(skill)

    return matched, gaps


# ============================================================
# HARD FILTERS
# ============================================================

def hard_filter(job):
    title = job["title"].lower()
    text = (job["title"] + " " + job["description"]).lower()

    if any(term in text for term in ["internship", "traineeship", "stage "]):
        return False, "internship"

    if any(term in title for term in [
        "financial analyst", "finance analyst",
        "financial controller", "treasury analyst",
    ]):
        return False, "finance-focused role"

    degree = degree_requirement(text)

    if degree in [
        "mandatory Master's",
        "mandatory Master's in technical field",
    ]:
        return False, "mandatory Master's degree"

    if degree in [
        "mandatory specific technical degree",
        "mandatory Bachelor/Master in technical field",
        "mandatory Bachelor's in technical field",
    ]:
        return False, "mandatory specific technical/ICT degree"

    years = extract_experience(text)
    if years is not None and years >= 8:
        return False, f"requires {years}+ years relevant experience"

    return True, "passed"

# ============================================================
# MATCH SCORE
# ============================================================

def score(job):
    text = (job["title"] + " " + job["description"]).lower()
    title = job["title"].lower()
    fam = job["job_family"]
    reasons = [fam]

    family_base = {
        "HR Data / People Analytics": 78,
        "Data Analyst": 76,
        "BI / Power BI": 74,
        "Reporting": 68,
        "Data Governance / Quality": 66,
        "Functional / Business Data Analysis": 66,
        "Data / Analytics Consulting": 62,
        "Data Engineering (stretch)": 50,
    }

    value = family_base.get(fam, 50)

    if (
        ("data analyst" in title or "data analist" in title)
        and ("bi " in title or "business intelligence" in title or "power bi" in title)
    ):
        value += 6
        reasons.append("core BI/Data Analyst title")

    if any(term in title for term in [
        "hr data", "hr analytics", "people analytics",
        "workforce analytics", "hris",
    ]):
        value += 5
        reasons.append("HR/People Data priority")

    matched, gaps = skill_information(job)

    bonuses = {
        "sql": 5, "power bi": 6, "etl": 4,
        "data warehouse": 3, "datawarehouse": 0,
        "data quality": 3, "data governance": 3,
        "python": 2, "cognos": 3, "wherescape": 3,
        "reporting": 3, "hr analytics": 4,
        "people analytics": 4, "data modeling": 2,
        "data modelling": 0,
    }

    value += min(16, sum(bonuses.get(skill, 0) for skill in matched))

    if matched:
        reasons.append("matched: " + ", ".join(matched[:6]))

    if gaps:
        value -= min(10, len(gaps) * 2)
        reasons.append("potential gaps: " + ", ".join(gaps[:5]))

    if "sap" in title and "master data" in title:
        value -= 24
        reasons.append("SAP Master Data specialization")
    elif "master data" in title:
        value -= 10
        reasons.append("Master Data specialization")

    years = extract_experience(text)

    if years is not None:
        reasons.append(f"requires {years}+ years")
        if years >= 6:
            value -= 20
        elif years == 5:
            value -= 12
        elif years == 4:
            value -= 6
        elif years <= 3:
            value += 4

    if "senior" in title:
        value -= 8
        reasons.append("senior title")
    if "expert" in title:
        value -= 10
        reasons.append("expert title")
    if "manager" in title:
        value -= 16
        reasons.append("manager title")
    if "lead" in title:
        value -= 16
        reasons.append("leadership title")
    if "architect" in title:
        value -= 16
        reasons.append("architect title")

    degree = degree_requirement(text)

    if "equivalent experience" in degree.lower():
        value -= 1
        reasons.append(degree)
    elif degree in ["Bachelor's degree", "Bachelor's or Master's degree"]:
        value -= 2
        reasons.append(degree)
    elif degree in [
        "Bachelor's in technical field",
        "Bachelor's/Master's in technical field",
        "Master's in technical field",
        "technical degree mentioned",
        "Master's degree mentioned",
    ]:
        value -= 8
        reasons.append(degree)
    elif "preferred" in degree.lower():
        value -= 1
        reasons.append(degree)

    location = job.get("location", "").lower()

    if any(place in location for place in [
        "brussels", "bruxelles", "brussel", "anderlecht",
        "schaerbeek", "schaarbeek", "diegem", "machelen",
    ]):
        value += 5
        reasons.append("Brussels area")
    elif any(place in location for place in [
        "antwerp", "antwerpen", "brugge", "bruges",
        "west flanders", "west-vlaanderen",
    ]):
        value -= 7
        reasons.append("outside preferred Brussels area")

    return max(0, min(95, round(value))), "; ".join(reasons)


# ============================================================
# V5.0 BRUSSELS 30 KM LOCATION INTELLIGENCE
# ============================================================

BRUSSELS_RADIUS_KM = 30.0
BRUSSELS_CENTER = (50.8503, 4.3517)

# Approximate municipality/city centroids for job-market classification.
# Unknown locations are reported, never rejected in V4.8.
BELGIUM_LOCATION_COORDS = {
    "brussels": (50.8503, 4.3517), "bruxelles": (50.8503, 4.3517),
    "brussel": (50.8503, 4.3517), "anderlecht": (50.8362, 4.3082),
    "schaerbeek": (50.8676, 4.3737), "schaarbeek": (50.8676, 4.3737),
    "ixelles": (50.8333, 4.3667), "elsene": (50.8333, 4.3667),
    "etterbeek": (50.8369, 4.3895), "evere": (50.8744, 4.4034),
    "uccle": (50.8018, 4.3372), "ukkel": (50.8018, 4.3372),
    "jette": (50.8731, 4.3340), "forest": (50.8115, 4.3178),
    "vorst": (50.8115, 4.3178), "molenbeek": (50.8547, 4.3228),
    "saint-gilles": (50.8276, 4.3457), "sint-gillis": (50.8276, 4.3457),
    "woluwe-saint-lambert": (50.8439, 4.4291),
    "sint-lambrechts-woluwe": (50.8439, 4.4291),
    "woluwe-saint-pierre": (50.8292, 4.4433),
    "sint-pieters-woluwe": (50.8292, 4.4433),
    "diegem": (50.8972, 4.4330), "machelen": (50.9106, 4.4417),
    "zaventem": (50.8837, 4.4729), "vilvoorde": (50.9281, 4.4294),
    "grimbergen": (50.9342, 4.3721), "asse": (50.9101, 4.1984),
    "zellik": (50.8844, 4.2736), "dilbeek": (50.8479, 4.2597),
    "groot-bijgaarden": (50.8714, 4.2630),
    "sint-pieters-leeuw": (50.7793, 4.2436), "halle": (50.7339, 4.2345),
    "beersel": (50.7659, 4.3002), "drogenbos": (50.7873, 4.3147),
    "kraainem": (50.8610, 4.4691), "wezembeek-oppem": (50.8396, 4.4944),
    "tervuren": (50.8237, 4.5142), "overijse": (50.7744, 4.5346),
    "hoeilaart": (50.7673, 4.4683), "waterloo": (50.7147, 4.3991),
    "braine-l'alleud": (50.6836, 4.3678), "eigenbrakel": (50.6836, 4.3678),
    "wavre": (50.7167, 4.6167), "waver": (50.7167, 4.6167),
    "mechelen": (51.0259, 4.4776), "malines": (51.0259, 4.4776),
    "leuven": (50.8798, 4.7005), "louvain": (50.8798, 4.7005),
    "aalst": (50.9360, 4.0355), "alost": (50.9360, 4.0355),
    "antwerp": (51.2194, 4.4025), "antwerpen": (51.2194, 4.4025),
    "ghent": (51.0543, 3.7174), "gent": (51.0543, 3.7174),
    "brugge": (51.2093, 3.2247), "bruges": (51.2093, 3.2247),
    "charleroi": (50.4108, 4.4446), "hasselt": (50.9307, 5.3325),
    "liège": (50.6326, 5.5797), "liege": (50.6326, 5.5797),
    "namur": (50.4674, 4.8718), "namen": (50.4674, 4.8718),
}


def haversine_km(lat1, lon1, lat2, lon2):
    from math import radians, sin, cos, asin, sqrt
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 6371.0088 * 2 * asin(sqrt(a))


def detect_work_mode(text):
    value = clean(text).lower()
    if any(x in value for x in ["fully remote", "full remote", "100% remote", "remote only"]):
        return "REMOTE"
    if any(x in value for x in ["hybrid", "hybride", "télétravail", "telework", "thuiswerk", "work from home"]):
        return "HYBRID"
    return "ONSITE_OR_UNKNOWN"


def match_known_location(location):
    value = clean(location).lower()
    for place in sorted(BELGIUM_LOCATION_COORDS, key=len, reverse=True):
        if re.search(r"(?<![a-z0-9])" + re.escape(place) + r"(?![a-z0-9])", value):
            return place, BELGIUM_LOCATION_COORDS[place]
    return "", None


def classify_brussels_distance(location, description=""):
    raw_location = normalize_location_for_output(location)
    work_mode = detect_work_mode(raw_location + " " + clean(description))
    place, coords = match_known_location(raw_location)

    if coords:
        distance = haversine_km(
            BRUSSELS_CENTER[0], BRUSSELS_CENTER[1], coords[0], coords[1]
        )
        return {
            "normalized_location": raw_location,
            "location_place": place,
            "distance_from_brussels_km": round(distance, 1),
            "location_status": "WITHIN_30KM" if distance <= BRUSSELS_RADIUS_KM else "OUTSIDE_30KM",
            "work_mode": work_mode,
        }

    status = (
        "REMOTE" if work_mode == "REMOTE"
        else "HYBRID_LOCATION_UNKNOWN" if work_mode == "HYBRID"
        else "LOCATION_UNKNOWN"
    )
    return {
        "normalized_location": raw_location,
        "location_place": "",
        "distance_from_brussels_km": "",
        "location_status": status,
        "work_mode": work_mode,
    }


# ============================================================
# V5.0 VACANCY IDENTITY / CONSERVATIVE DEDUPLICATION
# ============================================================

def canonical_job_url(url):
    """
    Canonicalize a vacancy URL without making assumptions about title/location.
    Tracking parameters and fragments are removed, while the vacancy path is kept.
    """
    value = clean(url)
    if not value:
        return ""

    p = urlparse(value)
    path = re.sub(r"/+$", "", p.path or "")
    return p._replace(
        scheme=(p.scheme or "https").lower(),
        netloc=p.netloc.lower(),
        path=path,
        params="",
        query="",
        fragment="",
    ).geturl()


def vacancy_reference(company, url, text=""):
    """
    Extract a stable vacancy/job reference when there is strong evidence.

    Important V4.6 rule:
    a title is NOT an identity key. Two jobs may legitimately share the same
    company, title and even city. If different job references exist, keep both.
    """
    company_key = clean(company).lower()
    path = urlparse(clean(url)).path.rstrip("/")
    body = clean(text)

    url_patterns = {
        "cegeka": [
            r"-(\d+)$",
        ],
        "sopra steria": [
            r"-jid-(\d+)$",
        ],
        "keyrus": [
            r"/jobs/(\d+)-",
        ],
        "infrabel": [
            r"/(\d+)(?:-[A-Za-z_]+)?$",
        ],
        "hr rail": [
            r"/(\d+)(?:-[A-Za-z_]+)?$",
        ],
        # Capgemini detail URLs expose a stable numeric requisition ID.
        "capgemini": [
            r"/(\d+)/?$",
        ],
    }

    for pattern in url_patterns.get(company_key, []):
        match = re.search(pattern, path, flags=re.I)
        if match:
            return match.group(1)

    # Text-based references are intentionally conservative and only use
    # explicit labels commonly found on ATS vacancy pages.
    text_patterns = [
        r"\bref(?:erence)?\.?\s*(?:code|id|number|no\.?)?\s*[:#-]?\s*([A-Z0-9_-]{4,})\b",
        r"\bjob\s*(?:id|reference|ref|number|no\.?)\s*[:#-]?\s*([A-Z0-9_-]{4,})\b",
        r"\brequisition\s*(?:id|number|no\.?)\s*[:#-]?\s*([A-Z0-9_-]{4,})\b",
    ]
    for pattern in text_patterns:
        match = re.search(pattern, body, flags=re.I)
        if match:
            return match.group(1).upper()

    return ""


def normalize_location_for_output(location):
    """
    Clean location text for readability only.

    This does NOT calculate distance and does NOT filter jobs. The planned
    Brussels <=50 km geographic filter remains a later feature.
    """
    value = clean(location)
    if not value:
        return ""

    value = re.sub(r"\s*,\s*", ", ", value)
    value = re.sub(r"\s+", " ", value).strip(" ,;-")

    # Collapse accidental repeated adjacent chunks such as:
    # "Diegem, BE Diegem, BE" -> "Diegem, BE"
    parts = value.split()
    if len(parts) >= 4 and len(parts) % 2 == 0:
        half = len(parts) // 2
        if [x.lower() for x in parts[:half]] == [x.lower() for x in parts[half:]]:
            value = " ".join(parts[:half])

    return value


def conservative_deduplicate_dataframe(df):
    """
    V4.6 deduplication policy.

    1. If a stable job reference exists:
       deduplicate only by company + reference.
    2. If no stable reference exists:
       deduplicate only by company + canonical URL.
    3. NEVER deduplicate solely by title or location.

    This means two 'Senior Data Analyst' vacancies in the same city survive
    when they have different job IDs/URLs.
    """
    if df.empty:
        return df

    work = df.copy()

    work["location"] = work["location"].fillna("").map(normalize_location_for_output)
    work["_company_key"] = work["company"].fillna("").astype(str).str.lower().str.strip()
    work["_canonical_url"] = work["url"].fillna("").map(canonical_job_url)

    refs = []
    for _, row in work.iterrows():
        refs.append(
            vacancy_reference(
                row.get("company", ""),
                row.get("url", ""),
                row.get("description", ""),
            )
        )
    work["_job_reference"] = refs

    # Highest-scoring representation wins only when identity is proven.
    work.sort_values(by="match_score", ascending=False, inplace=True)

    before = len(work)

    with_ref = work[work["_job_reference"] != ""].copy()
    without_ref = work[work["_job_reference"] == ""].copy()

    if not with_ref.empty:
        with_ref.drop_duplicates(
            subset=["_company_key", "_job_reference"],
            keep="first",
            inplace=True,
        )

    if not without_ref.empty:
        without_ref.drop_duplicates(
            subset=["_company_key", "_canonical_url"],
            keep="first",
            inplace=True,
        )

    work = pd.concat([with_ref, without_ref], ignore_index=True)
    work.sort_values(by="match_score", ascending=False, inplace=True)

    removed = before - len(work)
    ref_count = int((work["_job_reference"] != "").sum())
    url_only_count = len(work) - ref_count

    print(
        f"V5.0 conservative dedup removed {removed} proven duplicate representation(s)."
    )
    print(
        f"Vacancy identity coverage: {ref_count} stable job reference(s) | "
        f"{url_only_count} canonical-URL identity record(s)."
    )

    work.drop(
        columns=["_company_key", "_canonical_url", "_job_reference"],
        inplace=True,
        errors="ignore",
    )

    return work


# ============================================================
# SCRAPE ONE COMPANY
# ============================================================

def scrape_source(source):

    candidates = discover(
        source
    )

    jobs = []
    detail_failures = 0

    print(
        "  opening targeted detail pages:",
        len(candidates),
    )

    for index, (
        url,
        listing_title,
    ) in enumerate(
        candidates,
        start=1,
    ):

        try:

            html = fetch(url)

            job = extract_detail_job(
                html,
                source,
                url,
            )

            if job:
                jobs.append(job)
            else:
                detail_failures += 1

        except Exception as exc:
            detail_failures += 1

            print(
                "  detail skipped:",
                exc,
            )

        # Pauwels needs slower requests.
        if source["type"] == "pauwels":
            time.sleep(1.25)
        else:
            time.sleep(0.35)

    unique = {}

    for job in jobs:

        if not job["job_family"]:
            continue

        unique[job["url"]] = job

    return list(
        unique.values()
    )


# ============================================================
# MAIN
# ============================================================

def run():

    now = datetime.now(
        timezone.utc
    ).isoformat()

    accepted = []

    rejected = 0

    total_discovered = 0
    source_health = []

    print()
    print("=" * 50)
    print("JOB SEARCHING AGENT V5.0 - BELGIUM-FIRST LOCATION CONSOLIDATION")
    print("=" * 50)

    for source in SOURCES:

        print()
        print("-" * 50)
        print(
            "Scraping",
            source["company"],
        )
        print("-" * 50)

        try:

            jobs = scrape_source(
                source
            )

        except Exception as exc:

            print(
                "  SOURCE ERROR:",
                exc,
            )

            continue

        total_discovered += len(
            jobs
        )

        source_accepted = 0
        source_rejected = 0

        for job in jobs:

            full_text = (
                job["title"]
                + " "
                + job["description"]
            )

            experience = (
                extract_experience(
                    full_text
                )
            )

            degree = (
                degree_requirement(
                    full_text
                )
            )

            languages = (
                extract_languages(
                    full_text
                )
            )

            (
                matched_skills,
                missing_skills,
            ) = skill_information(job)

            ok, filter_reason = (
                hard_filter(job)
            )

            if not ok:

                print(
                    "  REJECT:",
                    job["title"],
                    "->",
                    filter_reason,
                )

                rejected += 1
                source_rejected += 1

                continue

            match_score, match_reason = (
                score(job)
            )

            job.update(
                {
                    "date_found": now,
                    "active": True,

                    "required_experience": (
                        experience
                        if experience
                        is not None
                        else ""
                    ),

                    "degree_requirement": degree,

                    "required_languages": (
                        languages
                    ),

                    "matched_skills": (
                        ", ".join(
                            matched_skills
                        )
                    ),

                    "missing_skills": (
                        ", ".join(
                            missing_skills
                        )
                    ),

                    "match_score": (
                        match_score
                    ),

                    "match_reason": (
                        match_reason
                    ),

                    "hard_filter_status": (
                        "passed"
                    ),

                    "hard_filter_reason": "",
                }
            )

            location_info = classify_brussels_distance(


                job.get("location", ""),


                job.get("description", ""),


            )


            job.update(location_info)

            # V5.0: normalize any city already present in JSON-LD/evidence.
            normalized_location = normalize_resolved_location_v50(
                job.get("location", ""),
                job.get("location_evidence", ""),
            )
            if normalized_location:
                job["location"] = normalized_location
                refreshed = classify_brussels_distance(
                    job.get("location", ""),
                    job.get("description", ""),
                )
                job.update(refreshed)

            # Conservative company-specific fallback.
            fallback_location, fallback_source = company_location_fallback_v50(
                job.get("company", ""),
                job.get("location", ""),
                job.get("description", ""),
            )
            if fallback_location and not clean(job.get("location", "")):
                job["location"] = fallback_location
                job["location_resolution_source"] = fallback_source
                refreshed = classify_brussels_distance(
                    fallback_location,
                    job.get("description", ""),
                )
                job.update(refreshed)

            country_status, country = classify_country_v50(
                job.get("location", ""),
                job.get("location_evidence", ""),
                job.get("url", ""),
            )
            job["country_status"] = country_status
            job["country"] = country

            if is_belgium_flexible_v50(
                job.get("location", ""),
                job.get("work_mode", ""),
            ):
                job["location_status"] = "BELGIUM_FLEXIBLE"
                job["location_status_v50"] = "BELGIUM_FLEXIBLE"
            else:
                job["location_status_v50"] = job.get("location_status", "")

            # V5.0 hard rule: explicit foreign vacancies must not enter the
            # Belgian shortlist. The 30 km rule itself remains report-only.
            if country_status == "OUTSIDE_BELGIUM":
                rejected += 1
                print(
                    f"  REJECT LOCATION: {job.get('title','')} -> "
                    f"outside Belgium ({country})"
                )
                continue

            job["canonical_url"] = canonical_job_url(job.get("url", ""))
            job["job_reference"] = vacancy_reference(
                job.get("company", ""),
                job.get("url", ""),
                job.get("description", ""),
            )

            accepted.append(job)

            source_accepted += 1

            print(
                "  ACCEPT:",
                job["title"],
                f"-> score {match_score}",
            )

        print(
            "  real target vacancies:",
            len(jobs),
        )

        print(
            "  accepted:",
            source_accepted,
            "| rejected:",
            source_rejected,
        )

        source_health.append(
            (source["company"], len(jobs), source_accepted, source_rejected)
        )

        diagnostic = DISCOVERY_HEALTH.get(source["company"])
        if diagnostic is not None:
            diagnostic["extracted"] = len(jobs)

    columns = [
        "title",
        "job_family",
        "company",
        "location",
        "region",
        "normalized_location",
        "location_place",
        "distance_from_brussels_km",
        "location_status",
        "work_mode",
        "country_status",
        "country",
        "location_status_v50",
        "location_resolution_source",
        "location_evidence",
        "job_reference",
        "canonical_url",
        "salary",
        "employment_type",
        "url",
        "description",
        "source",
        "date_found",
        "active",
        "required_experience",
        "degree_requirement",
        "required_languages",
        "matched_skills",
        "missing_skills",
        "match_score",
        "match_reason",
        "hard_filter_status",
        "hard_filter_reason",
    ]

    df = pd.DataFrame(
        accepted,
        columns=columns,
    )

    print()
    print("=" * 50)
    print("SOURCE HEALTH")
    print("=" * 50)
    for company, targets, ok_count, rejected_count in source_health:
        diagnostic = DISCOVERY_HEALTH.get(company)

        if diagnostic:
            status = diagnostic["status"]
            inventory = diagnostic["inventory"]
            extracted = diagnostic.get("extracted", targets)
            print(
                f"{status:10} | {company:<22} | scanned={inventory:<3} | "
                f"queued={diagnostic['targets']:<3} | extracted={extracted:<3} | "
                f"accepted={ok_count:<3} | rejected={rejected_count}"
            )
        else:
            # Legacy adapters do not yet expose full inventory counts.
            status = "HEALTHY" if targets > 0 else "PARTIAL"
            print(
                f"{status:10} | {company:<22} | scanned=?   | "
                f"targets={targets:<3} | accepted={ok_count:<3} | rejected={rejected_count}"
            )

    print()
    print("=" * 50)
    print("SCRAPER SUMMARY")
    print("=" * 50)

    print(
        "Target vacancies extracted:",
        total_discovered,
    )

    print(
        "Accepted:",
        len(df),
    )

    print(
        "Rejected:",
        rejected,
    )

    if df.empty:

        print(
            "No verified matching jobs found."
        )

        print(
            "Existing CSV left unchanged."
        )

        return

    # V4.8 conservative vacancy identity:
    # stable job reference first; canonical URL otherwise.
    # Never merge merely because title/location match.
    df = conservative_deduplicate_dataframe(df)

    print()
    print("=" * 50)
    print("V5.0 LOCATION INTELLIGENCE")
    print("=" * 50)
    location_counts = df["location_status"].fillna("LOCATION_UNKNOWN").value_counts()
    for status, count in location_counts.items():
        print(f"{status:<24} | {count}")

    known_distances = pd.to_numeric(df["distance_from_brussels_km"], errors="coerce")
    print(f"Distance resolved for {int(known_distances.notna().sum())}/{len(df)} accepted unique jobs.")
    print("REPORT-ONLY: OUTSIDE_30KM jobs are NOT rejected in V5.0.")

    print()
    print("=" * 50)
    print("V5.0 COUNTRY VALIDATION")
    print("=" * 50)
    if "country_status" in df.columns:
        for status, count in df["country_status"].fillna("COUNTRY_UNKNOWN").value_counts().items():
            print(f"{status:<24} | {count}")
    flexible_count = int((df.get("location_status_v50", pd.Series(dtype=str)) == "BELGIUM_FLEXIBLE").sum())
    print(f"{'BELGIUM_FLEXIBLE':<24} | {flexible_count}")

    print()
    print("=" * 50)
    print("V5.0 LOCATION RESOLUTION BY COMPANY")
    print("=" * 50)
    for company, group in df.groupby("company", sort=True):
        distances = pd.to_numeric(group["distance_from_brussels_km"], errors="coerce")
        resolved = int(distances.notna().sum())
        unknown = len(group) - resolved
        source_counts = (
            group["location_resolution_source"]
            .fillna("unknown")
            .replace("", "unknown")
            .value_counts()
            .to_dict()
        )
        print(
            f"{company:<22} | resolved={resolved:>2}/{len(group):<2} | "
            f"unknown={unknown:<2} | sources={source_counts}"
        )

    unresolved = df[pd.to_numeric(
        df["distance_from_brussels_km"], errors="coerce"
    ).isna()].copy()

    if not unresolved.empty:
        print()
        print("=" * 50)
        print("V5.0 UNRESOLVED LOCATION DIAGNOSTICS")
        print("=" * 50)
        for _, row in unresolved.iterrows():
            print(
                f"UNRESOLVED | {row['company']} | {row['title']} | "
                f"ref={row.get('job_reference','') or '-'} | "
                f"location={row.get('location','') or '-'} | "
                f"source={row.get('location_resolution_source','') or 'unknown'}"
            )
            evidence = clean(row.get("location_evidence", ""))
            if evidence:
                print("  evidence:", evidence[:700])
            print("  canonical:", row.get("canonical_url", row.get("url", "")))

    df.to_csv(
        OUTPUT,
        index=False,
    )

    print()
    print(
        "Saved",
        len(df),
        "verified targeted jobs to",
        OUTPUT,
    )

    print()
    print("TOP RESULTS")

    for _, row in df.head(10).iterrows():

        print(
            f"  {row['match_score']:>3} | "
            f"{row['company']} | "
            f"{row['title']}"
        )


if __name__ == "__main__":
    run()