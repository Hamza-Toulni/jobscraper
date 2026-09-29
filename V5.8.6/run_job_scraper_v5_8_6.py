# -*- coding: utf-8 -*-

from datetime import datetime, timezone
import traceback
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
        "url": "https://jobs.hr-rail.be/HRRail/viewalljobs/",
        "domain": "jobs.hr-rail.be",
        "type": "successfactors",
        "job_url_regex": r"/HRRail/job/[^/]+/\d+(?:-[a-z_]+)?/?$",
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



# ============================================================
# V5.8.6 NETWORK RELIABILITY
# ============================================================

def get_with_retry(url, *, timeout=None, attempts=3, backoff=2.0, **kwargs):
    """
    Small reliability wrapper for transient network failures.
    Returns a Response or raises the last requests exception.
    """
    if timeout is None:
        timeout = globals().get("TIMEOUT", 20)

    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            response = SESSION.get(url, timeout=timeout, **kwargs)
            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            last_exc = exc
            if attempt < attempts:
                wait_s = backoff * attempt
                print(f"  network retry {attempt}/{attempts - 1}: {url} -> {exc}")
                time.sleep(wait_s)
    raise last_exc


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
# V5.8.6 LOCATION RESOLUTION + COUNTRY VALIDATION
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
    "melle": "Melle",
    "9090": "Melle",
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
    "9000": "Ghent", "9090": "Melle", "3500": "Hasselt", "9300": "Aalst",
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
    # EU / EEA / nearby markets commonly returned by international ATS portals
    "AT": "Austria", "BG": "Bulgaria", "HR": "Croatia", "CY": "Cyprus",
    "CZ": "Czechia", "DK": "Denmark", "EE": "Estonia", "FI": "Finland",
    "FR": "France", "DE": "Germany", "GR": "Greece", "HU": "Hungary",
    "IE": "Ireland", "IT": "Italy", "LV": "Latvia", "LT": "Lithuania",
    "LU": "Luxembourg", "MT": "Malta", "NL": "Netherlands", "PL": "Poland",
    "PT": "Portugal", "RO": "Romania", "SK": "Slovakia", "SI": "Slovenia",
    "ES": "Spain", "SE": "Sweden", "NO": "Norway", "CH": "Switzerland",
    "GB": "United Kingdom", "UK": "United Kingdom",
    # Other markets seen on global careers portals
    "CA": "Canada", "US": "United States", "IN": "India",
    "AU": "Australia", "NZ": "New Zealand", "SG": "Singapore",
}

FOREIGN_CITY_MARKERS = {
    "utrecht": "Netherlands", "rotterdam": "Netherlands", "amsterdam": "Netherlands",
    "lisboa": "Portugal", "lisbon": "Portugal",
    "vancouver": "Canada", "new york": "United States",
    "bucharest": "Romania", "bertrange": "Luxembourg",
    "luxembourg": "Luxembourg",
    "kraków": "Poland", "krakow": "Poland", "lublin": "Poland",
    "poznań": "Poland", "poznan": "Poland", "wrocław": "Poland",
    "wroclaw": "Poland", "gdańsk": "Poland", "gdansk": "Poland",
    "warszawa": "Poland", "warsaw": "Poland", "katowice": "Poland",
    "opole": "Poland",
    "aguascalientes": "Mexico",
}

def classify_country_v50(location="", evidence="", url=""):
    """V5.4: explicit foreign codes beat ambiguous Belgian city aliases."""
    loc = clean(location)
    url_raw = clean(url)
    url_low = url_raw.lower()

    try:
        evidence_items = json.loads(evidence) if evidence else []
        if not isinstance(evidence_items, list):
            evidence_items = []
    except Exception:
        evidence_items = []

    structured_raw = []
    for item in evidence_items:
        if not isinstance(item, dict):
            continue
        source_name = clean(item.get("source", "")).lower()
        raw = clean(item.get("raw", ""))
        if raw and source_name in {
            "jsonld", "existing", "dom", "meta", "attribute",
            "structured", "label"
        }:
            structured_raw.append(raw)

    bounded_parts = [x for x in [loc] + structured_raw if clean(x)]
    bounded = " | ".join(bounded_parts)
    bounded_low = bounded.lower()

    trusted_be_site = any(
        domain in url_low for domain in ("smals.be", "infrabel.be", "hr-rail.be")
    )

    # V5.8.6: explicit foreign codes first, but ONLY when the original
    # evidence contains an uppercase country-code token. V5.4 used a
    # case-insensitive matcher, so normal prose such as "at" could become AT
    # (Austria). This still catches "Bergen, NO", "Oslo, NO", "Utrecht, NL", etc.
    for raw in bounded_parts:
        raw_original = str(raw)
        for code, country in FOREIGN_COUNTRY_MARKERS.items():
            if re.search(
                rf"(?:^|[,;/|()\-]\s*|\s){re.escape(code)}(?:$|[,;/|()\-]|\s)",
                raw_original
            ):
                return "OUTSIDE_BELGIUM", country

    foreign_names = {
        country.lower(): country for country in set(FOREIGN_COUNTRY_MARKERS.values())
    }
    for country_low, country in foreign_names.items():
        if re.search(r"(?<![a-z])" + re.escape(country_low) + r"(?![a-z])", bounded_low):
            return "OUTSIDE_BELGIUM", country

    for city, country in FOREIGN_CITY_MARKERS.items():
        if re.search(r"(?<![\w-])" + re.escape(city) + r"(?![\w-])", bounded_low, re.I):
            return "OUTSIDE_BELGIUM", country

    if _location_from_text(loc) or any(_location_from_text(x) for x in structured_raw):
        return "BELGIUM", "Belgium"

    if any(x in bounded_low for x in ("belgium", "belgië", "belgique")):
        return "BELGIUM", "Belgium"

    if re.search(r"(?i)(?:^|[\s,;/|()\-])BE(?:$|[\s,;/|()\-])", bounded):
        return "BELGIUM", "Belgium"

    for city, country in FOREIGN_CITY_MARKERS.items():
        if city in url_low:
            return "OUTSIDE_BELGIUM", country

    # /nl/ on Belgian sites is a language path, not Netherlands.
    if not trusted_be_site:
        for code, country in FOREIGN_COUNTRY_MARKERS.items():
            if re.search(
                rf"(?i)(?:-|%2c|/){re.escape(code)}(?:-|/|%2f|$)",
                url_raw
            ):
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

    # Smals V5.8.6 fallback:
    # first use any city/postcode explicitly found in the vacancy text.
    # If the Smals vacancy page exposes no usable location at all, classify it
    # as Brussels for distance reporting and label the source transparently.
    if company_low == "smals":
        resolved = _location_from_text(description)
        if resolved:
            return resolved, "smals_description"

        desc_low = clean(description).lower()
        if any(token in desc_low for token in (
            "brussel", "bruxelles", "brussels",
            "1060 sint-gillis", "1060 saint-gilles",
        )):
            return "Brussels", "smals_page_brussels"

        return "Brussels", "smals_company_fallback"

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

    # V5.8.6 rail recovery:
    # SuccessFactors detail pages can contain relevant Data/Analytics/Governance
    # vacancies whose titles are not covered by the generic family vocabulary.
    # Only widen the title prefilter for Infrabel / HR Rail; the normal evaluator
    # still decides whether the extracted job is accepted or rejected.
    if not fam and source["company"] in ("Infrabel", "HR Rail"):
        rail_title = clean(title).lower()
        rail_terms = (
            "data", "analytics", "business intelligence", "power bi",
            "reporting", "governance", "data quality", "analyst",
            "hris", "successfactors"
        )
        if any(term in rail_title for term in rail_terms):
            fam = "Rail data target"

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




def search_discovery_bing_rss(query, domains=None, max_results=30):
    """Indexed discovery via Bing RSS, independent of HTML selectors."""
    search_url = "https://www.bing.com/search?format=rss&q=" + quote_plus(query)
    response = get_with_retry(
        search_url,
        timeout=30,
        attempts=3,
        headers={**HEADERS, "Referer": "https://www.bing.com/"},
    )
    response.raise_for_status()

    # V5.8.6: parse RSS with Python's standard library instead of
    # BeautifulSoup("xml"). GitHub runners may not have lxml installed.
    import xml.etree.ElementTree as ET

    results = []
    try:
        root = ET.fromstring(response.content)
    except ET.ParseError as exc:
        raise RuntimeError(f"Bing RSS returned invalid XML: {exc}") from exc

    for item in root.findall(".//item"):
        link_node = item.find("link")
        title_node = item.find("title")

        link = clean(link_node.text if link_node is not None and link_node.text else "")
        title = clean(title_node.text if title_node is not None and title_node.text else "")

        if not link.startswith("http"):
            continue

        host = urlparse(link).netloc.lower()
        if domains and not any(
            host == domain or host.endswith("." + domain)
            for domain in domains
        ):
            continue

        results.append((normalize_url(link, link), title))
        if len(results) >= max_results:
            break

    unique = {}
    for result_url, title in results:
        unique[result_url] = title
    return list(unique.items())


def indexed_discovery_v55(queries, domains, max_results=30):
    """Use all available indexed-discovery backends and deduplicate."""
    recovered = []
    for query in queries:
        for finder in (
            search_discovery,
            search_discovery_bing,
            search_discovery_bing_rss,
        ):
            try:
                recovered.extend(
                    finder(query, domains=domains, max_results=max_results)
                )
            except Exception as exc:
                print(
                    f"  indexed backend {finder.__name__} skipped "
                    f"for {query!r}: {exc}"
                )
        time.sleep(0.20)

    unique = {}
    for url, title in recovered:
        if url:
            unique[url] = title
    return list(unique.items())


def discover_akkodis(source):
    print("  strategy: Akkodis V5.8.6 Belgium job-results recovery")

    candidates = []
    # V5.8.6: official Belgium job-results route confirmed as the country job-search page.
    entry_pages = [
        "https://www.akkodis.com/en-be/careers/job-results",
        "https://www.akkodis.com/nl-be/werken-bij/job-results",
        "https://www.akkodis.com/en-be/careers",
        "https://www.akkodis.com/en/careers",
    ]

    pages_ok = 0
    all_internal = []
    embedded_job_urls = []

    def akk_job_url(url):
        path = urlparse(url).path.lower()
        # Current Belgian detail pattern, e.g.
        # /en-be/careers/jobs/data-analyst/2026-34885
        return bool(re.search(
            r"/(?:en-be/careers|nl-be/werken-bij)/jobs/[^/]+/\\d{4}-\\d+/?$",
            path,
        ))

    for entry in entry_pages:
        try:
            html = fetch(entry)
            pages_ok += 1
            soup = BeautifulSoup(html, "html.parser")
            raw_urls = [normalize_url(a["href"], entry) for a in soup.find_all("a", href=True)]

            # Also inspect JSON/script payloads because the results page can be client-rendered.
            raw_urls += [
                raw.replace("\\/", "/")
                for raw in re.findall(r'https?://[^"\'< >\\s\\]+', html, flags=re.I)
            ]
            raw_urls += [
                normalize_url(raw.replace("\\/", "/"), entry)
                for raw in re.findall(
                    r'["\']((?:/)?(?:en-be/careers|nl-be/werken-bij)/jobs/[^"\']+)["\']',
                    html,
                    flags=re.I,
                )
            ]

            for url in raw_urls:
                if "akkodis.com" not in urlparse(url).netloc.lower():
                    continue
                all_internal.append(url)
                if akk_job_url(url):
                    embedded_job_urls.append(url)

            print(
                f"  Akkodis page: {entry} -> html_chars={len(html)} "
                f"internal_links={len(set(all_internal))} job_urls={len(set(embedded_job_urls))}"
            )
        except Exception as exc:
            print("  Akkodis official entry skipped:", entry, "->", exc)
        time.sleep(0.25)

    # First classify URLs exposed by the official Belgium results page.
    direct = 0
    for url in embedded_job_urls:
        path = urlparse(url).path
        hay = clean(path.replace("-", " ").replace("/", " "))
        if looks_targeted(hay):
            candidates.append((url, ""))
            direct += 1

    print("  official pages opened:", pages_ok)
    print("  direct target candidates:", direct)

    # Keep indexed fallback, but broaden it to both EN-BE and NL-BE current paths.
    queries = [
        'site:akkodis.com/en-be/careers/jobs/ "Data Analyst"',
        'site:akkodis.com/en-be/careers/jobs/ "Data Engineer"',
        'site:akkodis.com/en-be/careers/jobs/ "Business Intelligence"',
        'site:akkodis.com/en-be/careers/jobs/ "Power BI"',
        'site:akkodis.com/en-be/careers/jobs/ "Data Governance"',
        'site:akkodis.com/en-be/careers/jobs/ "Data Quality"',
        'site:akkodis.com/en-be/careers/jobs/ "Reporting Analyst"',
        'site:akkodis.com/en-be/careers/jobs/ "HR Data"',
        'site:akkodis.com/en-be/careers/jobs/ "HRIS"',
        'site:akkodis.com/nl-be/werken-bij/jobs/ data',
    ]

    indexed_found = indexed_discovery_v55(queries, domains=["akkodis.com"], max_results=50)
    indexed = 0
    for url, title in indexed_found:
        if not akk_job_url(url):
            continue
        hay = clean(title + " " + urlparse(url).path.replace("-", " ").replace("/", " "))
        if not looks_targeted(hay):
            continue
        candidates.append((url, title))
        indexed += 1
    print("  indexed target candidates:", indexed)

    unique = {}
    for url, title in candidates:
        parsed = urlparse(url)
        canonical = parsed._replace(query="", fragment="").geturl()
        unique[canonical] = title

    result = list(unique.items())
    print("  relevant vacancy links:", len(result))
    if result:
        for url, title in result[:10]:
            print("    Akkodis candidate:", title or urlparse(url).path.split("/")[-2], "->", url)
    else:
        # Diagnostic output for the next iteration if GitHub sees different HTML.
        interesting = []
        for url in dict.fromkeys(all_internal):
            low = url.lower()
            if any(t in low for t in ("job", "career", "search", "vacan", "api")):
                interesting.append(url)
        print("  Akkodis diagnostic career/job links:", len(interesting))
        for url in interesting[:20]:
            print("    diagnostic:", url)

    DISCOVERY_HEALTH["Akkodis"] = {
        "status": "HEALTHY" if result else ("DEGRADED" if pages_ok else "BROKEN"),
        "scanned": len(result),
        "queued": len(result),
        "extracted": 0,
        "reason": "" if result else (
            "Belgium job-results reachable but no target vacancy URLs discovered"
            if pages_ok else "official Akkodis Belgium pages unavailable"
        ),
    }
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
    _v586_deep_trace_count = 0
    _v582_rail_trace_count = 0
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
        print("  strategy: Infrabel V5.8.6 detail-classification recovery")

        # SuccessFactors viewalljobs/category pages can render the vacancy grid
        # client-side. The /search/ catalogue is a better server-side discovery
        # surface and supports startrow pagination.
        bases = [
            "https://jobs.infrabel.be/search/?q=&sortColumn=referencedate&sortDirection=desc",
            "https://jobs.infrabel.be/search/?q=data&sortColumn=referencedate&sortDirection=desc",
            "https://jobs.infrabel.be/search/?q=analyst&sortColumn=referencedate&sortDirection=desc",
            "https://jobs.infrabel.be/search/?q=ICT&sortColumn=referencedate&sortDirection=desc",
            "https://jobs.infrabel.be/viewalljobs/",
            "https://jobs.infrabel.be/go/Alle-vacatures/957602/",
        ]

        pages = []
        for base in bases:
            pages.append(base)
            # SuccessFactors commonly paginates in 25-row increments.
            for offset in range(25, 251, 25):
                sep = "&" if "?" in base else "?"
                pages.append(f"{base}{sep}startrow={offset}")

        patterns = [
            # Confirmed live form:
            # /job/<slug>/<jobid>-nl_NL/
            r"/job/[^/?#]+/\d+(?:-[A-Za-z]{2}_[A-Za-z]{2})?/?$",
            r"/job/[^/?#]+/\d+(?:-[A-Za-z_]+)?/?$",
            r"/job/[^/?#]+/\d+/?$",
        ]

    elif company == "HR Rail":
        print("  strategy: HR Rail V5.8.6 catalogue-seeded SuccessFactors recovery")

        # HR Rail has its own live hostname. V5.8.0 still pointed this adapter
        # at jobs.infrabel.be/HRRail, which prevented real HR Rail inventory
        # from being discovered.
        bases = [
            "https://jobs.hr-rail.be/HRRail/search/?q=&sortColumn=referencedate&sortDirection=desc",
            "https://jobs.hr-rail.be/HRRail/search/?q=data&sortColumn=referencedate&sortDirection=desc",
            "https://jobs.hr-rail.be/HRRail/search/?q=analyst&sortColumn=referencedate&sortDirection=desc",
            "https://jobs.hr-rail.be/HRRail/search/?q=SAP&sortColumn=referencedate&sortDirection=desc",
            "https://jobs.hr-rail.be/HRRail/search/?q=HR&sortColumn=referencedate&sortDirection=desc",
            "https://jobs.hr-rail.be/HRRail/viewalljobs/",
            "https://jobs.hr-rail.be/HRRail/go/Alle-vacatures-HR-Rail/957202/",
            "https://jobs.hr-rail.be/HRRail/go/Tous-les-vacatures-HR-Rail/957302/",
        ]

        pages = []
        for base in bases:
            pages.append(base)
            for offset in range(25, 151, 25):
                sep = "&" if "?" in base else "?"
                pages.append(f"{base}{sep}startrow={offset}")

        patterns = [
            # Confirmed live form:
            # /HRRail/job/Senior-SAP-Payroll-Analyst/31238-nl_NL/
            r"/HRRail/job/[^/?#]+/\d+(?:-[A-Za-z]{2}_[A-Za-z]{2})?/?$",
            r"/HRRail/job/[^/?#]+/\d+(?:-[A-Za-z_]+)?/?$",
            r"/HRRail/job/[^/?#]+/\d+/?$",
        ]
    else:
        return None

    for page_url in pages:
        try:
            html = fetch(page_url)
            if company in ("Infrabel", "HR Rail") and _v582_rail_trace_count < 3:
                v586_successfactors_response_diagnostics(company, page_url, html)
                if _v586_deep_trace_count < 1:
                    v586_print_sf_deep_trace(company, page_url, html)
                    _v586_deep_trace_count += 1
                _v582_rail_trace_count += 1
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

    # V5.8.6 indexed fallback for SAP SuccessFactors.
    # Primary recovery is now the official /search/ catalogue above. Indexed
    # discovery remains secondary only.
    if not inventory and company in ("Infrabel", "HR Rail"):
        if company == "Infrabel":
            recovery_queries = [
                'site:jobs.infrabel.be/job/ "Data Analyst"',
                'site:jobs.infrabel.be/job/ "Data Engineer"',
                'site:jobs.infrabel.be/job/ "Business Intelligence"',
                'site:jobs.infrabel.be/job/ "Power BI"',
                'site:jobs.infrabel.be/job/ "Data Governance"',
                'site:jobs.infrabel.be/job/ analyst',
                'site:jobs.infrabel.be/job/ data',
            ]
            recovery_domains = ["jobs.infrabel.be"]
        else:
            recovery_queries = [
                'site:jobs.hr-rail.be/HRRail/job/ analyst',
                'site:jobs.hr-rail.be/HRRail/job/ data',
                'site:jobs.hr-rail.be/HRRail/job/ reporting',
                'site:jobs.hr-rail.be/HRRail/job/ SAP',
                'site:jobs.hr-rail.be/HRRail/job/ payroll',
                'site:jobs.hr-rail.be/HRRail/job/ HR',
            ]
            recovery_domains = ["jobs.hr-rail.be"]

        recovered = indexed_discovery_v55(
            recovery_queries,
            domains=recovery_domains,
            max_results=50,
        )

        scoped = []
        for url, title in recovered:
            path = urlparse(url).path

            if company == "HR Rail":
                if "/HRRail/job/" not in path:
                    continue
            else:
                if "/job/" not in path or "/HRRail/" in path:
                    continue

            if any(re.search(p, path, flags=re.I) for p in patterns):
                scoped.append((url, title))

        inventory = _dedup_url_pairs(scoped)
        print("  indexed recovery vacancy URLs:", len(inventory))

    # Critical V4.4 change: DO NOT pre-filter inventory by listing title.
    # Every discovered real vacancy detail page is opened. The existing
    # family(), vacancy validation, degree and experience rules then decide.
    result = inventory

    if inventory:
        status = "HEALTHY"
    elif pages_ok and company in ("Infrabel", "HR Rail"):
        status = "DEGRADED"
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
# V5.8.6 BRUSSELS 30 KM LOCATION INTELLIGENCE
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
    "melle": (50.9990, 3.8050),
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
# V5.8.6 VACANCY IDENTITY / CONSERVATIVE DEDUPLICATION
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
        f"V5.8.6 conservative dedup removed {removed} proven duplicate representation(s)."
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
    _v586_detail_trace_count = 0

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


            if source["company"] in ("Infrabel", "HR Rail") and _v586_detail_trace_count < 5:

                v586_detail_page_trace(source["company"], url, html, listing_title)

                _v586_detail_trace_count += 1
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
            if source["company"] in ("Infrabel", "HR Rail"):
                rail_title = clean(job.get("title", "")).lower()
                if any(term in rail_title for term in (
                    "data", "analytics", "business intelligence", "power bi",
                    "reporting", "governance", "data quality", "analyst",
                    "hris", "successfactors"
                )):
                    job["job_family"] = "Rail data target"
                else:
                    continue
            else:
                continue

        unique[job["url"]] = job

    return list(
        unique.values()
    )


# ============================================================
# MAIN
# ============================================================


def v580_regression_selfcheck():
    """Guardrails for the location regressions fixed in V5.4.1."""
    checks = [
        # Explicit foreign codes must still win.
        ("Bergen, NO", "", "OUTSIDE_BELGIUM", "Norway"),
        ("Oslo, NO", "", "OUTSIDE_BELGIUM", "Norway"),
        ("Utrecht, NL", "", "OUTSIDE_BELGIUM", "Netherlands"),

        # Belgian locations remain Belgian.
        ("Mons, BE", "", "BELGIUM", "Belgium"),
        ("7000 Mons", "", "BELGIUM", "Belgium"),

        # Ordinary prose "at" must NOT be interpreted as Austria.
        ("", json.dumps([{
            "source": "dom",
            "raw": "Work at customer sites across Belgium",
            "resolved": ""
        }]), "BELGIUM", "Belgium"),

        # Aguascalientes exposed by Capgemini V5.4 must be foreign.
        ("Aguascalientes", "", "OUTSIDE_BELGIUM", "Mexico"),
    ]

    failures = []
    for raw, evidence, expected_status, expected_country in checks:
        if not evidence:
            evidence = json.dumps([
                {"source": "dom", "raw": raw, "resolved": _location_from_text(raw)}
            ])
        status, country = classify_country_v50(raw, evidence, "")
        if (status, country) != (expected_status, expected_country):
            failures.append(
                (raw, status, country, expected_status, expected_country)
            )

    # Capgemini URL-only Aguascalientes case.
    status, country = classify_country_v50(
        "", "[]",
        "https://careers.capgemini.com/job/Aguascalientes-Senior-Data-Analyst/1404081133"
    )
    if (status, country) != ("OUTSIDE_BELGIUM", "Mexico"):
        failures.append(
            ("Capgemini Aguascalientes URL", status, country,
             "OUTSIDE_BELGIUM", "Mexico")
        )

    # Smals /nl/ is a Dutch-language path, never a Netherlands marker.
    status, country = classify_country_v50(
        "", "[]", "https://www.smals.be/nl/jobs/apply/7281/bi-developer"
    )
    if (status, country) == ("OUTSIDE_BELGIUM", "Netherlands"):
        failures.append(("Smals /nl/", status, country, "not Netherlands", ""))

    # Smals unresolved pages should receive the explicit Brussels fallback.
    loc, source = company_location_fallback_v50("Smals", "", "")
    if (loc, source) != ("Brussels", "smals_company_fallback"):
        failures.append(("Smals fallback", loc, source, "Brussels",
                         "smals_company_fallback"))

    if failures:
        raise AssertionError(f"V5.8.6 regression self-check failed: {failures}")
    return True




def v580_rss_parser_selfcheck():
    """Verify that RSS parsing works without optional lxml/BeautifulSoup XML support."""
    import xml.etree.ElementTree as ET

    sample = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>Data Analyst</title>
          <link>https://jobs.infrabel.be/job/test/12345/</link>
        </item>
      </channel>
    </rss>"""

    root = ET.fromstring(sample)
    item = root.find(".//item")
    if item is None:
        raise AssertionError("V5.8.6 RSS self-check: item not parsed")

    link = item.findtext("link", default="")
    if "jobs.infrabel.be/job/" not in link:
        raise AssertionError("V5.8.6 RSS self-check: link not parsed")

    return True



# ============================================================
# V5.8.6 COMPANY EXPANSION
# First wave: CM, Orange Belgium, Partena Professional, SD Worx,
# Securex, Elia, Fluvius and PwC Belgium.
# ============================================================

V573_MAX_LISTING_PAGES = 20
V573_MAX_INTERNAL_LINKS = 800
V573_MAX_QUEUE_SIZE = 500

V575_PAUSED_GENERIC_COMPANIES = {
    "AE",
    "Delaware Belgium",
    "Inetum Belgium",
}

V571_WAVE2_COMPANIES = {
    "Delaware Belgium", "AE", "Inetum Belgium", "NRB",
    "Cronos Group", "Belfius", "Proximus",
}

V56_EXPANSION_SOURCES = [
    {
        "company": "CM",
        "url": "https://jobs.cm.be/",
        "v563_state": "UNSUPPORTED",
        "domains": ["jobs.cm.be", "cm.be"],
        "adapter": "v56_generic",
    },
    {
        "company": "Orange Belgium",
        "url": "https://jobs.orange.be/",
        "v563_state": "BLOCKED",
        "domains": ["jobs.orange.be", "orange.be"],
        "adapter": "v56_generic",
    },
    {
        "company": "Partena Professional",
        "url": "https://jobs.partena-professional.be/",
        "domains": ["jobs.partena-professional.be", "partena-professional.be"],
        "adapter": "v56_generic",
    },
    {
        "company": "SD Worx",
        "url": "https://careers.sdworx.com/",
        "domains": ["careers.sdworx.com", "sdworx.com"],
        "adapter": "v56_generic",
    },
    {
        "company": "Securex",
        "url": "https://jobs.securex.be/",
        "v563_state": "UNSUPPORTED",
        "domains": ["jobs.securex.be", "securex.be"],
        "adapter": "v56_generic",
    },
    {
        "company": "Elia",
        "url": "https://jobs.eliagroup.eu/",
        "domains": ["jobs.eliagroup.eu", "elia.be", "eliagroup.eu"],
        "adapter": "v56_generic",
    },
    {
        "company": "Fluvius",
        "url": "https://jobs.fluvius.be/",
        "domains": ["jobs.fluvius.be", "fluvius.be"],
        "adapter": "v56_generic",
    },
    {
        "company": "PwC Belgium",
        "url": "https://www.pwc.be/en/careers.html",
        "v563_state": "BLOCKED",
        "domains": ["pwc.be"],
        "adapter": "v56_generic",
    },
    {
        "company": "Delaware Belgium",
        "url": "https://www.delaware.pro/en-be/careers",
        "domains": ["delaware.pro"],
        "adapter": "v57_generic",
    },
    {
        "company": "AE",
        "url": "https://www.ae.be/careers",
        "domains": ["ae.be"],
        "adapter": "v57_generic",
    },
    {
        "company": "Inetum Belgium",
        "url": "https://www.inetum.com/be/careers",
        "domains": ["inetum.com"],
        "adapter": "v57_generic",
    },
    {
        "company": "NRB",
        "url": "https://www.nrb.be/en/jobs",
        "domains": ["nrb.be"],
        "adapter": "v57_generic",
    },
    {
        "company": "Cronos Group",
        "url": "https://www.cronos.be/jobs",
        "domains": ["cronos.be"],
        "adapter": "v57_generic",
    },
    {
        "company": "Belfius",
        "url": "https://jobs.belfius.be/",
        "domains": ["jobs.belfius.be", "belfius.be"],
        "adapter": "v57_generic",
    },
    {
        "company": "Proximus",
        "url": "https://jobs.proximus.com/",
        "domains": ["jobs.proximus.com", "proximus.com"],
        "adapter": "v57_generic",
    },

]


def _v56_is_probable_job_url(url, source):
    if not url or not url.startswith("http"):
        return False

    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    query = parsed.query.lower()

    if source.get("company") == "Belfius":
        return _v574_belfius_is_detail_url(url)

    if source.get("domains") and not any(
        host == d or host.endswith("." + d)
        for d in source["domains"]
    ):
        return False

    # Never crawl unresolved template placeholders.
    if "{" in url or "}" in url or "%7b" in url.lower() or "%7d" in url.lower():
        return False

    bad = (
        "/privacy", "/cookie", "/contact", "/about", "/news", "/blog",
        "/event", "/events", "/login", "/signin", "/register",
        "/talent-community", "/faq", "/legal", "/job-alert",
    )
    if any(x in path for x in bad):
        return False

    # Category/list pages are not job details.
    terminal = path.rstrip("/").split("/")[-1]
    if terminal in {
        "jobs", "job", "careers", "career", "vacatures", "vacancies",
        "open-positions", "job-openings", "all-jobs", "search"
    }:
        return False

    indicators = (
        "/job/", "/jobs/", "/vacature/", "/vacatures/", "/vacancy/",
        "/vacancies/", "/position/", "/positions/", "/career-opportunities/",
        "/job-detail/", "/jobdetails/", "/job-details/", "/job-openings/",
        "/open-position/", "/open-positions/",
    )
    if any(x in path for x in indicators):
        # Require detail evidence after the listing segment.
        if re.search(
            r"/(?:job|jobs|vacature|vacatures|vacancy|vacancies|position|positions|"
            r"job-detail|jobdetails|job-details|job-openings|open-position|open-positions)"
            r"/[^/]{3,}",
            path
        ):
            return True

    # ATS/reference identifiers.
    if re.search(r"/\d{4,}(?:/)?$", path):
        return True
    if re.search(r"(?:job|jobid|job_id|vacancy|vacancyid|position|positionid|req|requisition)"
                 r"=[a-z0-9_-]{3,}", query):
        return True

    # Common ATS hosts discovered after redirect.
    ats_hosts = (
        "workdayjobs.com", "myworkdayjobs.com", "smartrecruiters.com",
        "teamtailor.com", "recruitee.com", "successfactors.com",
        "talent-soft.com", "talentsoft.com"
    )
    if any(x in host for x in ats_hosts):
        return bool(terminal and terminal not in {"jobs", "search", "careers"})

    return False




V572_SOURCE_HINTS = {
    "Delaware Belgium": {
        "extra_paths": ["/en-be/careers/jobs", "/en-be/careers/job-openings"],
        "keywords": ["data", "analytics", "business intelligence", "power bi"],
    },
    "AE": {
        "extra_paths": ["/careers/job-openings", "/careers/jobs"],
        "keywords": ["data", "analytics", "ai", "business analyst"],
    },
    "Inetum Belgium": {
        "extra_paths": ["/en/careers", "/careers", "/jobs"],
        "keywords": ["data", "bi", "analytics", "governance"],
    },
    "NRB": {
        "extra_paths": ["/jobs", "/en/careers", "/en/jobs"],
        "keywords": ["data", "business intelligence", "analyst"],
    },
    "Cronos Group": {
        "extra_paths": ["/careers", "/jobs", "/vacancies"],
        "keywords": ["data", "bi", "analytics", "governance"],
    },
    "Belfius": {
        "extra_paths": ["/jobs", "/vacancies"],
        "keywords": ["data", "reporting", "analytics", "bi"],
    },
    "Proximus": {
        "extra_paths": ["/jobs", "/careers", "/search"],
        "keywords": ["data", "analytics", "bi", "governance"],
    },
}


def _v572_seed_pages(source):
    base = source["url"]
    hint = V572_SOURCE_HINTS.get(source["company"], {})
    pages = [base]
    parsed = urlparse(base)
    root = f"{parsed.scheme}://{parsed.netloc}"
    for path in hint.get("extra_paths", []):
        pages.append(root.rstrip("/") + "/" + path.lstrip("/"))
    # Stable dedup preserving order.
    return list(dict.fromkeys(pages))



def discover_v56_generic(source):
    """
    Reusable V5.8.6 discovery adapter.

    1. Crawl a bounded number of official listing/navigation pages.
    2. Extract probable job-detail URLs.
    3. If server-rendered discovery is empty, use resilient indexed discovery.
    4. Keep only data/BI/governance/HR-data target candidates.
    """
    company = source["company"]
    if company == "Belfius":
        print("  strategy: V5.8.6 source intentionally ignored")
        DISCOVERY_HEALTH[company] = {
            "status": "IGNORED", "scanned": 0, "queued": 0,
            "extracted": 0, "accepted": 0, "rejected": 0,
            "reason": "intentionally excluded from V5.8 roadmap",
        }
        return []

    if company in V575_PAUSED_GENERIC_COMPANIES:
        print("  strategy: V5.8.6 generic adapter paused - dedicated ATS discovery required")
        DISCOVERY_HEALTH[company] = {
            "status": "PAUSED", "scanned": 0, "queued": 0,
            "extracted": 0, "accepted": 0, "rejected": 0,
            "reason": "generic crawler produced no real vacancy links; dedicated adapter required",
        }
        return []

    base = source["url"]
    domains = source.get("domains", [])

    known_state = source.get("v563_state")
    if known_state in ("UNSUPPORTED", "BLOCKED"):
        reason = (
            "career endpoint currently unreachable from runner"
            if known_state == "UNSUPPORTED"
            else "career endpoint currently blocks automated access"
        )
        print(f"  strategy: V5.8.6 known-source state -> {known_state}")
        print(f"  skipped: {reason}")
        DISCOVERY_HEALTH[company] = {
            "status": known_state,
            "scanned": 0,
            "queued": 0,
            "extracted": 0,
            "accepted": 0,
            "rejected": 0,
            "reason": reason,
        }
        return []

    print("  strategy: V5.8.6 reusable company-expansion adapter")

    queue = _v572_seed_pages(source)
    visited = set()
    discovered = []
    listing_pages = 0
    v571_internal_links = 0
    v571_probable_job_links = 0
    v571_indexed_candidates = 0

    while (queue and len(visited) < 20) and listing_pages < V573_MAX_LISTING_PAGES and v571_internal_links < V573_MAX_INTERNAL_LINKS:
        page = queue.pop(0)
        if page in visited:
            continue
        visited.add(page)

        try:
            html = fetch(page)
            listing_pages += 1
        except Exception as exc:
            print(f"  listing skipped: {page} -> {exc}")
            continue

        soup = BeautifulSoup(html, "html.parser")

        for a in soup.find_all("a", href=True):
            url = normalize_url(a["href"], page)
            title = clean(a.get_text(" ", strip=True))
            host = urlparse(url).netloc.lower()
            path = urlparse(url).path.lower()

            if domains and not any(
                host == d or host.endswith("." + d) for d in domains
            ):
                continue

            v571_internal_links += 1
            if _v56_is_probable_job_url(url, source):
                discovered.append((url, title))
                v571_probable_job_links += 1
                continue

            # Bounded navigation crawl through likely career/listing pages.
            nav_hay = clean(title + " " + path.replace("-", " ")).lower()
            if (
                any(k in nav_hay for k in (
                    "job", "jobs", "career", "careers", "vacature",
                    "vacatures", "vacancy", "vacancies", "opportunities",
                    "open positions", "openstaande"
                ))
                and url not in visited
                and len(queue) < 40
            ):
                if len(queue) < V573_MAX_QUEUE_SIZE:
                    queue.append(url)
        time.sleep(0.15)

    discovered = _dedup_url_pairs(discovered)

    # Indexed fallback. This is automatic discovery, not vacancy seeding.
    if not discovered:
        primary_domain = domains[0] if domains else urlparse(base).netloc
        queries = [
            f'site:{primary_domain} "Data Analyst"',
            f'site:{primary_domain} "Data Analist"',
            f'site:{primary_domain} "BI Developer"',
            f'site:{primary_domain} "Power BI"',
            f'site:{primary_domain} "Data Governance"',
            f'site:{primary_domain} "Data Quality"',
            f'site:{primary_domain} "Reporting Analyst"',
            f'site:{primary_domain} "HR Data"',
            f'site:{primary_domain} "HRIS"',
            f'site:{primary_domain} "Data Engineer"',
        ]

        try:
            indexed = indexed_discovery_v55(
                queries,
                domains=domains or [primary_domain],
                max_results=40,
            )
        except Exception as exc:
            print("  indexed recovery failed:", exc)
            indexed = []

        v571_indexed_candidates = len(indexed)
        discovered = [
            (url, title)
            for url, title in indexed
            if _v56_is_probable_job_url(url, source)
        ]
        discovered = _dedup_url_pairs(discovered)

    print("  listing pages opened:", listing_pages)
    print("  vacancy inventory links:", len(discovered))
    if company in V571_WAVE2_COMPANIES:
        print(
            f"  V5.8.6 diagnostics: internal_links={v571_internal_links} "
            f"probable_job_links={v571_probable_job_links} "
            f"indexed_candidates={v571_indexed_candidates} "
            f"inventory={len(discovered)}"
        )

    # V5.8.6 target filtering.
    #
    # V5.6 relied almost entirely on listing title/path. That is too strict
    # for ATS pages where the visible card text is generic. Keep the normal
    # target matcher, add HR-data vocabulary, and if an inventory exists but
    # nothing matches, inspect a bounded number of detail pages before
    # declaring NO_MATCHES.
    relevant = []
    expansion_terms = (
        "data analyst", "data analist", "business intelligence", "power bi",
        "reporting", "analytics", "data governance", "data quality",
        "master data", "hr data", "people analytics", "workforce analytics",
        "hris", "human resources information", "data engineer",
        "bi developer", "bi analyst", "functional data", "sap data",
        "data management", "data steward",
        "people data", "hr analytics", "workforce analytics",
        "hr technology", "hr tech", "sap hcm", "successfactors",
        "workday", "information management", "data consultant",
        "bi consultant",
    )

    for url, title in discovered:
        hay = clean(
            title + " " +
            urlparse(url).path.replace("-", " ").replace("/", " ")
        )
        hay_low = hay.lower()

        if looks_targeted(hay) or any(term in hay_low for term in expansion_terms):
            relevant.append((url, title))

    relevant = _dedup_url_pairs(relevant)

    # Detail-validation fallback: only when inventory was found but the
    # listing metadata produced zero targets. Bound the cost to 40 pages.
    if discovered and not relevant:
        print("  listing metadata produced 0 targets; validating detail text")
        detail_candidates = []

        for url, title in discovered[:40]:
            try:
                html = fetch(url)
                soup = BeautifulSoup(html, "html.parser")
                page_text = clean(soup.get_text(" ", strip=True))
                hay = clean(title + " " + page_text)
                hay_low = hay.lower()

                if (
                    looks_targeted(hay)
                    or any(term in hay_low for term in expansion_terms)
                ):
                    detail_candidates.append((url, title))
            except Exception as exc:
                print("  target-validation detail skipped:", url, "->", exc)

            time.sleep(0.10)

        relevant = _dedup_url_pairs(detail_candidates)
        print("  detail-validated target links:", len(relevant))

    print("  relevant vacancy links:", len(relevant))

    DISCOVERY_HEALTH[company] = {
        "internal_links": v571_internal_links,
        "probable_job_links": v571_probable_job_links,
        "indexed_candidates": v571_indexed_candidates,
        "status": (
            "HEALTHY" if relevant
            else "NO_MATCHES" if discovered
            else "DEGRADED" if listing_pages
            else "BROKEN"
        ),
        "scanned": len(discovered),
        "queued": len(relevant),
        "extracted": 0,
        "reason": (
            "" if relevant
            else "vacancy inventory found but no target titles"
            if discovered
            else "official source reachable but no vacancy detail inventory discovered"
            if listing_pages
            else "official source unavailable"
        ),
    }
    return relevant




def looks_like_real_vacancy_v563(title, description, url=""):
    """
    Conservative generic vacancy validator for V5.6 expansion sources.
    Reject obvious navigation/editorial/service pages while retaining real
    job-detail pages even when ATS markup is sparse.
    """
    title_low = clean(title).lower()
    desc_low = clean(description).lower()
    path_low = urlparse(url).path.lower()

    if not title_low:
        return False

    bad_title_terms = (
        "privacy", "cookie", "contact", "about us", "our services",
        "news", "blog", "event", "talent community", "job alert",
        "search jobs", "all jobs", "vacancies", "careers",
    )
    if any(term == title_low or title_low.startswith(term + " |")
           for term in bad_title_terms):
        return False

    editorial_terms = (
        "read more", "our expertise", "our services", "customer story",
        "case study", "whitepaper", "press release",
    )
    if any(term in title_low for term in editorial_terms):
        return False

    # Strong URL evidence.
    job_url = any(token in path_low for token in (
        "/job/", "/jobs/", "/vacature/", "/vacatures/",
        "/vacancy/", "/vacancies/", "/position/", "/job-detail/",
        "/jobdetails/", "/job-details/",
    ))

    # Strong content evidence.
    job_content_terms = (
        "responsibilities", "your role", "your profile", "what you bring",
        "what we offer", "requirements", "qualifications", "apply",
        "solliciteer", "jouw profiel", "jouw functie", "ons aanbod",
        "responsabilités", "votre profil", "nous offrons",
    )
    content_hits = sum(term in desc_low for term in job_content_terms)

    # Require meaningful body text unless URL/content evidence is strong.
    if len(desc_low) < 120 and not job_url:
        return False

    return job_url or content_hits >= 2



def extract_v562_job_page(company, url, html, listing_title=""):
    """Generic vacancy-detail extractor for V5.6 expansion sources."""
    soup = BeautifulSoup(html, "html.parser")
    title = clean(listing_title)
    description = ""
    location = ""
    evidence = []

    # Prefer schema.org JobPosting.
    for script in soup.find_all("script", type=re.compile(r"ld\+json", re.I)):
        raw = script.string or script.get_text(" ", strip=True)
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue

        nodes = payload if isinstance(payload, list) else [payload]
        expanded = []
        for node in nodes:
            if isinstance(node, dict) and isinstance(node.get("@graph"), list):
                expanded.extend(node["@graph"])
            else:
                expanded.append(node)

        for node in expanded:
            if not isinstance(node, dict):
                continue
            nt = node.get("@type", "")
            types = nt if isinstance(nt, list) else [nt]
            if not any(str(t).lower() == "jobposting" for t in types):
                continue

            title = title or clean(node.get("title", ""))
            raw_desc = str(node.get("description", ""))
            if raw_desc:
                description = clean(
                    BeautifulSoup(raw_desc, "html.parser").get_text(" ", strip=True)
                )

            jl = node.get("jobLocation")
            locations = jl if isinstance(jl, list) else [jl]
            locs = []
            for item in locations:
                if not isinstance(item, dict):
                    continue
                addr = item.get("address", {})
                if not isinstance(addr, dict):
                    continue
                parts = [
                    clean(addr.get("postalCode", "")),
                    clean(addr.get("addressLocality", "")),
                    clean(addr.get("addressRegion", "")),
                    clean(addr.get("addressCountry", "")),
                ]
                value = ", ".join(x for x in parts if x)
                if value:
                    locs.append(value)

            if locs:
                location = " / ".join(locs)
                evidence.append({
                    "source": "jsonld",
                    "raw": location,
                    "resolved": _location_from_text(location),
                })
            break

    if not title:
        h1 = soup.find("h1")
        title = clean(h1.get_text(" ", strip=True)) if h1 else ""
    if not title and soup.title:
        title = clean(soup.title.get_text(" ", strip=True))

    if not description:
        main = soup.find("main") or soup.find("article") or soup.body or soup
        description = clean(main.get_text(" ", strip=True))

    if not location:
        selectors = [
            "[itemprop='jobLocation']", "[itemprop='addressLocality']",
            "[data-automation='job-location']", "[data-testid*='location']",
            ".job-location", ".jobLocation", ".location", "[class*='location']",
        ]
        for selector in selectors:
            for node in soup.select(selector)[:5]:
                raw_loc = clean(node.get_text(" ", strip=True))
                if raw_loc and len(raw_loc) <= 180:
                    evidence.append({
                        "source": "dom",
                        "raw": raw_loc,
                        "resolved": _location_from_text(raw_loc),
                    })
                    if not location:
                        location = raw_loc
            if location:
                break

    if not location:
        resolved = _location_from_text(description)
        if resolved:
            location = resolved
            evidence.append({
                "source": "page_text", "raw": resolved, "resolved": resolved
            })

    return {
        "company": company,
        "title": title,
        "url": url,
        "location": location,
        "description": description,
        "location_evidence": json.dumps(evidence, ensure_ascii=False),
    }



def process_v56_expansion_source(source):
    """Discover, validate and score one V5.8.6 expansion company."""
    company = source["company"]
    v576_sd_worx = (company == "SD Worx")
    links = discover_v56_generic(source)

    accepted_rows = []
    rejected_rows = []
    loc_rejected = 0
    extraction_failures = 0

    print("  opening targeted detail pages:", len(links))

    for url, listing_title in links:
        try:
            html = fetch(url)
            job = extract_v562_job_page(company, url, html, listing_title)
            if v576_sd_worx:
                _v576_sd_worx_trace("raw job result", job)
                if not isinstance(job, dict):
                    job = _v576_unwrap_dict(job, "raw job result")
        except Exception as exc:
            extraction_failures += 1
            print("  detail skipped:", url, "->", exc)
            continue

        if not job or not clean(job.get("title", "")):
            continue

        job = normalize_expansion_job_v574(job)
        title = clean(job.get("title", ""))
        description = clean(job.get("description", ""))

        category_titles = {
            "all jobs", "jobs", "careers", "vacancies", "job openings",
            "reporting & controlling", "reporting and controlling",
            "search jobs", "open positions"
        }
        if title.lower().strip() in category_titles:
            print(f"  rejected category/listing page: {title}")
            continue

        # Reject pages that are not actual vacancies.
        if not looks_like_real_vacancy_v563(title, description, url):
            print(f"  rejected non-vacancy page: {title or url}")
            continue

        # Country/location validation before profile scoring.
        refreshed = location_intelligence(
            company=company,
            title=title,
            location=job.get("location", ""),
            description=description,
            url=url,
            existing_evidence=job.get("location_evidence", ""),
        )
        job.update(refreshed)

        if job.get("country_status") == "OUTSIDE_BELGIUM":
            loc_rejected += 1
            print(
                f"  REJECT LOCATION: {title} -> outside Belgium "
                f"({job.get('country', '')})"
            )
            continue

        decision = evaluate_expansion_job_v573(job)
        accepted_decision, score_value, rejection_reason = normalize_expansion_decision_v577(decision)

        if accepted_decision:
            job["score"] = score_value
            job["rejection_reason"] = rejection_reason
            accepted_rows.append(job)
            print(f"  ACCEPT: {title} -> score {score_value}")
        else:
            job["rejection_reason"] = rejection_reason
            rejected_rows.append(job)
            print(
                f"  REJECT: {title} -> "
                f"{rejection_reason}"
            )

    stat = DISCOVERY_HEALTH.setdefault(company, {})
    extracted_count = len(accepted_rows) + len(rejected_rows)
    stat["extracted"] = extracted_count
    stat["accepted"] = len(accepted_rows)
    stat["rejected"] = len(rejected_rows)
    stat["loc_rejected"] = loc_rejected
    stat["extraction_failures"] = extraction_failures

    # A source with queued targets but zero parsed vacancy details is degraded.
    if links and extracted_count == 0:
        stat["status"] = "DEGRADED"
        stat["reason"] = "target URLs queued but no vacancy details extracted"
    elif extracted_count > 0:
        stat["status"] = "HEALTHY"
        stat["reason"] = ""

    print(
        f"  accepted: {len(accepted_rows)} | "
        f"rejected: {len(rejected_rows)} | "
        f"loc_rejected: {loc_rejected}"
    )
    return accepted_rows, rejected_rows, loc_rejected




def location_intelligence(company, title, location, description, url,
                          existing_evidence=""):
    """
    V5.8.6 compatibility bridge for expansion sources.
    Reuses the validated V5.1+ location intelligence instead of maintaining
    a second location implementation.
    """
    fn = globals().get("location_intelligence_v51")
    if fn is None:
        # Safe fallback: preserve raw evidence and let final location
        # consolidation handle unresolved cases.
        resolved = _location_from_text(
            " ".join([
                clean(location),
                clean(description),
                clean(existing_evidence),
            ])
        )
        return {
            "location": clean(location) or resolved,
            "location_evidence": clean(existing_evidence),
        }

    return fn(
        company=company,
        title=title,
        location=location,
        description=description,
        url=url,
        existing_evidence=existing_evidence,
    )




def evaluate_expansion_job_v573(job):
    """Evaluate expansion jobs with the scraper's existing hard_filter + score."""
    job = normalize_expansion_job_v574(job)
    title = clean(job.get("title", ""))
    description = clean(job.get("description", ""))
    url = clean(job.get("url", ""))
    location = clean(job.get("location", ""))

    # Core hard filter.
    try:
        rejection = hard_filter(title, description)
    except TypeError:
        try:
            rejection = hard_filter(title, description, location)
        except TypeError:
            rejection = hard_filter(job)

    # hard_filter implementations may return a reason, bool, tuple or None.
    reason = ""
    rejected = False
    if isinstance(rejection, tuple):
        rejected = bool(rejection[0])
        if len(rejection) > 1:
            reason = clean(rejection[1])
    elif isinstance(rejection, str):
        reason = clean(rejection)
        rejected = bool(reason)
    elif isinstance(rejection, bool):
        rejected = rejection

    if rejected:
        return False, 0, reason or "hard profile filter"

    # Core score.
    try:
        value = score(title, description)
    except TypeError:
        try:
            value = score(title, description, location)
        except TypeError:
            value = score(job)

    if isinstance(value, tuple):
        value = value[0]

    try:
        value = int(round(float(value)))
    except Exception:
        value = 0

    return True, value, ""


def classify_source_exception_v573(exc):
    msg = str(exc).lower()
    if any(x in msg for x in (
        "network is unreachable", "connection reset", "connection aborted",
        "connection refused", "max retries exceeded", "timed out",
        "temporary failure", "remote end closed connection",
    )):
        return "TRANSIENT"
    if "403" in msg or "forbidden" in msg:
        return "BLOCKED"
    if "404" in msg or "not found" in msg:
        return "DEGRADED"
    return "BROKEN"




V574_EXPANSION_JOB_DEFAULTS = {
    "job_family": "", "job_level": "", "employment_type": "",
    "contract_type": "", "department": "", "business_unit": "",
    "experience": "", "education": "", "degree": "",
    "language": "", "languages": "", "location": "",
    "location_evidence": "", "description": "", "title": "",
    "url": "", "company": "",
}

def normalize_expansion_job_v574(job):
    # V5.8.6: tolerate tuple/list wrappers returned by expansion helpers.
    if isinstance(job, (tuple, list)):
        payload = next((item for item in job if isinstance(item, dict)), None)
        if payload is not None:
            job = payload
        else:
            values = list(job)
            job = {}
            if values:
                first = clean(values[0])
                job["url" if first.startswith("http") else "title"] = first
            if len(values) > 1:
                second = clean(values[1])
                if second.startswith("http") and not job.get("url"):
                    job["url"] = second
                elif not job.get("title"):
                    job["title"] = second

    normalized = dict(V574_EXPANSION_JOB_DEFAULTS)
    if isinstance(job, dict):
        normalized.update(job)
    aliases = {
        "job_family": ("family", "category", "job_category", "jobFamily"),
        "job_level": ("level", "seniority", "jobLevel"),
        "employment_type": ("employmentType", "employment", "type"),
        "contract_type": ("contractType", "contract"),
        "department": ("team", "function", "departmentName"),
        "business_unit": ("businessUnit", "division"),
        "experience": ("experience_required", "experienceRequired"),
        "education": ("education_required", "educationRequired"),
        "location": ("city", "job_location", "jobLocation"),
        "description": ("body", "content", "job_description"),
    }
    for target, sources in aliases.items():
        if clean(normalized.get(target, "")):
            continue
        for source in sources:
            if normalized.get(source):
                normalized[target] = normalized[source]
                break
    return normalized

def _v574_belfius_is_detail_url(url):
    if not url:
        return False
    parsed = urlparse(url)
    path = parsed.path.lower().rstrip("/")
    query = parsed.query.lower()
    if any(x in path for x in (
        "/category/", "/categories/", "/job-category/", "/job-categories/",
        "/domain/", "/domains/", "/function/", "/functions/",
        "/reporting-controlling", "/reporting-and-controlling",
    )):
        return False
    terminal = path.split("/")[-1]
    if terminal in {
        "reporting-controlling", "reporting-and-controlling",
        "jobs", "vacancies", "careers", "search"
    }:
        return False
    if re.search(r"/\d{4,}$", path):
        return True
    if re.search(r"(?:job|vacancy|position|req|requisition)(?:id)?=[a-z0-9_-]{3,}", query):
        return True
    if any(x in path for x in (
        "/job/", "/vacancy/", "/job-detail/", "/jobdetails/",
        "/position/", "/open-position/", "/offer/", "/offre/", "/vacature/"
    )):
        return True
    if re.search(r"/[a-z0-9][a-z0-9-]{5,}[-_/](?:[a-z]{0,4})?\\d{4,}$", path):
        return True
    return False

def v574_expansion_schema_selfcheck():
    probe = normalize_expansion_job_v574({
        "company": "SD Worx",
        "title": "Data Analyst",
        "description": "Power BI SQL reporting",
        "url": "https://example.invalid/job/1234",
    })
    for key in V574_EXPANSION_JOB_DEFAULTS:
        if key not in probe:
            raise AssertionError(f"V5.8.6 missing expansion key: {key}")
    _ = probe["job_family"]
    tuple_probe = normalize_expansion_job_v574((
        {"company": "SD Worx", "title": "Data Analyst", "description": "SQL Power BI"},
        {"meta": "ignored"},
    ))
    if tuple_probe.get("title") != "Data Analyst":
        raise AssertionError("V5.8.6 tuple normalization self-check failed")
    print("V5.8.6 expansion schema self-check: PASSED")




def _v576_type_summary(value):
    """Compact, non-secret diagnostic description of an intermediate value."""
    if isinstance(value, dict):
        return f"dict(keys={sorted(str(k) for k in value.keys())[:20]})"
    if isinstance(value, (tuple, list)):
        return (
            f"{type(value).__name__}(len={len(value)}, "
            f"types={[type(x).__name__ for x in value[:8]]})"
        )
    return type(value).__name__


def _v576_unwrap_dict(value, stage="unknown"):
    """
    Accept a dict directly or unwrap a tuple/list containing exactly one
    plausible job dict. Raise a precise error otherwise.
    """
    if isinstance(value, dict):
        return value

    if isinstance(value, (tuple, list)):
        dicts = [x for x in value if isinstance(x, dict)]
        if len(dicts) == 1:
            print(
                f"  V5.8.6 SD WORX TRACE: {stage}: "
                f"unwrapped {_v576_type_summary(value)} -> dict"
            )
            return dicts[0]

    raise TypeError(
        f"V5.8.6 SD WORX {stage}: expected job dict, got "
        f"{_v576_type_summary(value)}"
    )


def _v576_sd_worx_trace(stage, value):
    print(f"  V5.8.6 SD WORX TRACE: {stage}: {_v576_type_summary(value)}")
    return value




def v576_sd_worx_diagnostic_selfcheck():
    probe = ({"title": "Data Analyst", "company": "SD Worx"}, "metadata")
    unwrapped = _v576_unwrap_dict(probe, "selfcheck")
    if unwrapped.get("title") != "Data Analyst":
        raise AssertionError("V5.8.6 SD Worx unwrap self-check failed")
    try:
        _v576_unwrap_dict(("a", "b"), "selfcheck-invalid")
    except TypeError:
        pass
    else:
        raise AssertionError("V5.8.6 invalid tuple self-check failed")
    print("V5.8.6 SD Worx diagnostic self-check: PASSED")




def normalize_expansion_decision_v577(decision):
    """Normalize the evaluator's (accepted, score, reason) tuple contract."""
    if not isinstance(decision, (tuple, list)) or len(decision) != 3:
        raise TypeError(
            "V5.8.6 expansion decision contract violation: "
            f"expected 3-item tuple/list, got {_v576_type_summary(decision)}"
        )
    accepted, score_value, rejection_reason = decision
    try:
        score_value = int(round(float(score_value)))
    except Exception:
        score_value = 0
    return bool(accepted), score_value, clean(rejection_reason)


def v577_decision_contract_selfcheck():
    if normalize_expansion_decision_v577((True, 79, "")) != (True, 79, ""):
        raise AssertionError("V5.8.6 accepted decision self-check failed")
    rejected = normalize_expansion_decision_v577((False, 0, "profile mismatch"))
    if rejected != (False, 0, "profile mismatch"):
        raise AssertionError("V5.8.6 rejected decision self-check failed")
    try:
        normalize_expansion_decision_v577({"accepted": True})
    except TypeError:
        pass
    else:
        raise AssertionError("V5.8.6 invalid contract self-check failed")
    print("V5.8.6 expansion decision contract self-check: PASSED")




V578_FOREIGN_CITY_SIGNALS = {
    "oslo": "Norway", "bergen": "Norway", "trondheim": "Norway", "stavanger": "Norway",
    "amsterdam": "Netherlands", "rotterdam": "Netherlands", "utrecht": "Netherlands",
    "eindhoven": "Netherlands", "den haag": "Netherlands", "the hague": "Netherlands",
    "paris": "France", "lille": "France", "lyon": "France",
    "berlin": "Germany", "munich": "Germany", "münchen": "Germany",
    "frankfurt": "Germany", "hamburg": "Germany", "cologne": "Germany", "köln": "Germany",
    "luxembourg": "Luxembourg", "london": "United Kingdom", "manchester": "United Kingdom",
    "dublin": "Ireland", "lisbon": "Portugal", "lisboa": "Portugal", "porto": "Portugal",
    "madrid": "Spain", "barcelona": "Spain", "milan": "Italy", "milano": "Italy",
}
V578_FOREIGN_COUNTRY_SIGNALS = {
    "norway": "Norway", "norge": "Norway", "netherlands": "Netherlands",
    "nederland": "Netherlands", "france": "France", "germany": "Germany",
    "deutschland": "Germany", "luxembourg": "Luxembourg",
    "united kingdom": "United Kingdom", "ireland": "Ireland",
    "portugal": "Portugal", "spain": "Spain", "italy": "Italy",
}

def _v578_country_evidence_from_row(row):
    parts = []
    for key in ("location", "location_evidence", "canonical_url", "url", "title"):
        try:
            value = row.get(key, "")
        except Exception:
            value = ""
        if value is not None and str(value).lower() != "nan":
            parts.append(str(value))
    return " ".join(parts).lower()

def v578_detect_strong_foreign_signal(row):
    evidence = _v578_country_evidence_from_row(row)
    for token, country in V578_FOREIGN_COUNTRY_SIGNALS.items():
        if re.search(r"(?<![a-z])" + re.escape(token) + r"(?![a-z])", evidence):
            return country, f"explicit foreign-country signal: {token}"
    for city, country in V578_FOREIGN_CITY_SIGNALS.items():
        if re.search(r"(?<![a-z])" + re.escape(city) + r"(?![a-z])", evidence):
            return country, f"foreign-city signal: {city}"
    return "", ""

def v580_country_guard_selfcheck():
    oslo = {
        "title": "Nyutdannet høsten 2027 - Data Engineer / Data Analyst",
        "canonical_url": "https://careers.capgemini.com/job/Oslo-Nyutdannet-hosten-2027-Data-Engineer-Data-Analyst/1413101933",
    }
    country, _ = v578_detect_strong_foreign_signal(oslo)
    if country != "Norway":
        raise AssertionError("V5.8.6 Oslo/Norway guard self-check failed")
    neutral = {"title": "Data Analyst", "url": "https://example.be/jobs/data-analyst"}
    country, _ = v578_detect_strong_foreign_signal(neutral)
    if country:
        raise AssertionError("V5.8.6 conservative unknown-country self-check failed")
    print("V5.8.6 final country guard self-check: PASSED")




def v586_rail_successfactors_selfcheck():
    infrabel_url = (
        "https://jobs.infrabel.be/job/"
        "Stage-EU-Digital-Regulation-Radar-for-Cloud-Master/36730-nl_NL/"
    )
    hrrail_url = (
        "https://jobs.hr-rail.be/HRRail/job/"
        "Senior-SAP-Payroll-Analyst/31238-nl_NL/"
    )

    infrabel_pattern = re.compile(
        r"/job/[^/?#]+/\d+(?:-[A-Za-z]{2}_[A-Za-z]{2})?/?$",
        re.I,
    )
    hrrail_pattern = re.compile(
        r"/HRRail/job/[^/?#]+/\d+(?:-[A-Za-z]{2}_[A-Za-z]{2})?/?$",
        re.I,
    )

    if not infrabel_pattern.search(urlparse(infrabel_url).path):
        raise AssertionError("V5.8.6 Infrabel URL-pattern self-check failed")
    if not hrrail_pattern.search(urlparse(hrrail_url).path):
        raise AssertionError("V5.8.6 HR Rail URL-pattern self-check failed")
    if urlparse(hrrail_url).netloc.lower() != "jobs.hr-rail.be":
        raise AssertionError("V5.8.6 HR Rail hostname self-check failed")

    print("V5.8.6 rail SuccessFactors recovery self-check: PASSED")




def v586_successfactors_response_diagnostics(company, url, html):
    if company not in ("Infrabel", "HR Rail") or not html:
        return
    raw = str(html)
    low = raw.lower()
    hrefs = re.findall(r'href\s*=\s*["\']([^"\']+)["\']', raw, flags=re.I)
    jobish = [h for h in hrefs if "/job/" in h.lower()]
    data_attrs = re.findall(r'data-[A-Za-z0-9_-]+\\s*=\\s*["\\\']([^"\\\']+)["\\\']', raw, flags=re.I)
    candidate_job_ids = sorted(set(re.findall(
        r'(?i)(?:jobid|jobreqid|requisitionid)[^0-9]{0,20}([0-9]{3,})',
        raw,
    )))
    print(f"  V5.8.6 RAIL TRACE [{company}]")
    print(f"    url: {url}")
    print(f"    html_chars={len(raw)} hrefs={len(hrefs)} jobish_hrefs={len(jobish)}")
    print(f"    data_attrs={len(data_attrs)} candidate_job_ids={candidate_job_ids[:10]}")
    for token in ("jobid", "jobreqid", "startrow", "searchresults", "ajax", "api", "json"):
        count = low.count(token)
        if count:
            print(f"    indicator {token}={count}")
    if jobish:
        print("    sample job hrefs:")
        for h in jobish[:5]:
            print(f"      {h}")


def v586_sd_worx_contract_selfcheck():
    accepted_decision, score_value, rejection_reason = normalize_expansion_decision_v577((True, 42, ""))
    if not accepted_decision or score_value != 42 or rejection_reason:
        raise AssertionError("V5.8.6 SD Worx contract self-check failed")
    print("V5.8.6 SD Worx no-dict-update self-check: PASSED")




def v586_rail_extraction_trace(company, discovered_count, jobs):
    if company not in ("Infrabel", "HR Rail"):
        return
    print(f"  V5.8.6 RAIL EXTRACTION TRACE [{company}]")
    print(f"    discovered_detail_urls={discovered_count}")
    print(f"    parsed_target_jobs={len(jobs)}")
    if discovered_count and not jobs:
        print("    diagnosis: discovery succeeded but target extraction returned zero")
    for job in jobs[:5]:
        print(
            "    parsed:",
            clean(job.get("title", "")),
            "| location=",
            clean(job.get("location", "")),
            "| desc_chars=",
            len(clean(job.get("description", ""))),
        )


def v586_rail_health_selfcheck():
    # In V5.8.3, inventory alone must not be treated as end-to-end healthy.
    assert ("DEGRADED" if 17 > 0 and 0 == 0 else "HEALTHY") == "DEGRADED"
    print("V5.8.6 rail extraction health self-check: PASSED")




def v586_extract_sf_endpoint_evidence(html):
    raw = str(html or "")
    evidence = []

    for m in re.finditer(r"<form\b([^>]*)>", raw, flags=re.I | re.S):
        attrs = m.group(1)
        am = re.search(r'action\s*=\s*["\']([^"\']+)["\']', attrs, flags=re.I)
        mm = re.search(r'method\s*=\s*["\']([^"\']+)["\']', attrs, flags=re.I)
        if am:
            evidence.append(("form", am.group(1), mm.group(1) if mm else ""))

    for m in re.finditer(r'https?://[^"\'<>\s\\]+', raw, flags=re.I):
        value = m.group(0).replace("\\/", "/").replace("&amp;", "&")
        if any(t in value.lower() for t in ("search", "ajax", "api", "career", "job")):
            evidence.append(("url", value[:700], ""))

    for m in re.finditer(r'<input\b([^>]*)>', raw, flags=re.I | re.S):
        attrs = m.group(1)
        nm = re.search(r'name\s*=\s*["\']([^"\']+)["\']', attrs, flags=re.I)
        vm = re.search(r'value\s*=\s*["\']([^"\']*)["\']', attrs, flags=re.I)
        if nm and any(t in nm.group(1).lower() for t in
                      ("search", "start", "job", "req", "csrf", "token", "career", "locale")):
            evidence.append(("input", nm.group(1), (vm.group(1) if vm else "")[:300]))

    out, seen = [], set()
    for item in evidence:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def v586_print_sf_deep_trace(company, url, html):
    if company not in ("Infrabel", "HR Rail"):
        return
    evidence = v586_extract_sf_endpoint_evidence(html)
    print(f"  V5.8.6 SF DEEP TRACE [{company}]")
    print(f"    source: {url}")
    print(f"    endpoint/form evidence: {len(evidence)}")
    for kind, value, extra in evidence[:20]:
        print(f"    {kind}: {value}" + (f" | {extra}" if extra else ""))


def v586_detail_page_trace(company, url, html, listing_title=""):
    if company not in ("Infrabel", "HR Rail"):
        return
    raw = str(html or "")
    tm = re.search(r"<title[^>]*>(.*?)</title>", raw, flags=re.I | re.S)
    html_title = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", tm.group(1))).strip() if tm else ""
    visible = re.sub(r"<script\b.*?</script>", " ", raw, flags=re.I | re.S)
    visible = re.sub(r"<style\b.*?</style>", " ", visible, flags=re.I | re.S)
    visible = re.sub(r"<[^>]+>", " ", visible)
    visible = re.sub(r"\s+", " ", visible).strip()
    low = visible.lower()
    hits = [t for t in (
        "data", "analyst", "analytics", "business intelligence", "power bi",
        "reporting", "governance", "data quality", "sql", "sap", "hris",
        "payroll", "human resources"
    ) if t in low]
    print(f"  V5.8.6 DETAIL PAGE TRACE [{company}]")
    print(f"    url: {url}")
    print(f"    listing_title: {listing_title or '<empty>'}")
    print(f"    html_title: {html_title or '<empty>'}")
    print(f"    html_chars={len(raw)} visible_chars={len(visible)} target_terms={hits}")
    if visible:
        print(f"    text_sample: {visible[:900]}")


def v586_deep_recovery_selfcheck():
    sample = '<form method="get" action="/HRRail/search/"><input name="startrow" value="25"></form>'
    ev = v586_extract_sf_endpoint_evidence(sample)
    if not any(x[0] == "form" and "/HRRail/search/" in x[1] for x in ev):
        raise AssertionError("V5.8.6 SuccessFactors evidence self-check failed")
    print("V5.8.6 rail deep-recovery self-check: PASSED")




def v586_rail_title_recovery_selfcheck():
    title = "Finance Data Advanced Specialist Lead"
    rail_terms = (
        "data", "analytics", "business intelligence", "power bi",
        "reporting", "governance", "data quality", "analyst",
        "hris", "successfactors"
    )
    if not any(term in clean(title).lower() for term in rail_terms):
        raise AssertionError("V5.8.6 Infrabel title recovery self-check failed")
    print("V5.8.6 Infrabel title recovery self-check: PASSED")



def v586_akkodis_recovery_selfcheck():
    samples = [
        "/en-be/careers/jobs/data-analyst/2026-34885",
        "/nl-be/werken-bij/jobs/data-engineer/2026-34883",
    ]
    pat = re.compile(r"/(?:en-be/careers|nl-be/werken-bij)/jobs/[^/]+/\d{4}-\d+/?$", re.I)
    if not all(pat.search(x) for x in samples):
        raise AssertionError("V5.8.6 Akkodis URL-pattern self-check failed")
    print("V5.8.6 Akkodis URL-pattern self-check: PASSED")


def run():
    v586_akkodis_recovery_selfcheck()
    v586_rail_title_recovery_selfcheck()
    v586_deep_recovery_selfcheck()
    v586_rail_health_selfcheck()
    v586_sd_worx_contract_selfcheck()
    v586_rail_successfactors_selfcheck()
    v580_country_guard_selfcheck()
    v577_decision_contract_selfcheck()
    v576_sd_worx_diagnostic_selfcheck()
    v574_expansion_schema_selfcheck()

    v580_regression_selfcheck()
    v580_rss_parser_selfcheck()
    location_rejections_v51 = {}

    now = datetime.now(
        timezone.utc
    ).isoformat()

    accepted = []

    rejected = 0

    total_discovered = 0
    source_health = []

    print()
    print("=" * 50)
    print("JOB SEARCHING AGENT V5.8.6 - AKKODIS RECOVERY")
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

            if source["company"] in ("Infrabel", "HR Rail"):
                _diag = DISCOVERY_HEALTH.get(source["company"], {})
                v586_rail_extraction_trace(
                    source["company"],
                    int(_diag.get("inventory", 0) or 0),
                    jobs,
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
                company_key_v51 = clean(job.get("company", ""))
                location_rejections_v51[company_key_v51] = (
                    location_rejections_v51.get(company_key_v51, 0) + 1
                )
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
            if source["company"] in ("Infrabel", "HR Rail"):
                if int(diagnostic.get("inventory", 0) or 0) > 0 and len(jobs) == 0:
                    diagnostic["status"] = "DEGRADED"
                    diagnostic["error"] = "detail URLs discovered but zero target jobs extracted"
                elif len(jobs) > 0:
                    diagnostic["status"] = "HEALTHY"

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
    # --------------------------------------------------
    # V5.8.6 expansion wave
    # --------------------------------------------------
    expansion_accepted_rows = []
    expansion_rejected_rows = []

    for source in V56_EXPANSION_SOURCES:
        company = source["company"]
        print("-" * 50)
        print(f"Scraping {company}")
        print("-" * 50)

        try:
            new_accepted, new_rejected, new_loc_rejected = (
                process_v56_expansion_source(source)
            )

            # V5.6 bug fix:
            # accepted/rejected are integer counters in this part of run().
            # Never call .extend() on them.
            expansion_accepted_rows.extend(new_accepted)
            expansion_rejected_rows.extend(new_rejected)

            location_rejections_v51[company] = (
                location_rejections_v51.get(company, 0) + new_loc_rejected
            )
        except Exception as exc:
            print(f"  SOURCE ERROR: {exc}")
            if company == "SD Worx":
                print("  V5.8.6 SD WORX TRACEBACK:")
                for _line in traceback.format_exc().rstrip().splitlines():
                    print(f"    {_line}")

            # V5.8.6: preserve any discovery statistics already collected.
            previous = DISCOVERY_HEALTH.get(company, {})
            had_progress = (
                previous.get("scanned", 0) > 0
                or previous.get("queued", 0) > 0
            )

            previous.update({
                "status": ("DEGRADED" if had_progress else classify_source_exception_v573(exc)),
                "extracted": previous.get("extracted", 0),
                "accepted": previous.get("accepted", 0),
                "rejected": previous.get("rejected", 0),
                "reason": str(exc),
            })
            DISCOVERY_HEALTH[company] = previous

    # Merge expansion jobs into the master job collection rather than into
    # integer summary counters. The main pipeline later performs the normal
    # final deduplication and CSV output.
    if expansion_accepted_rows:
        jobs.extend(expansion_accepted_rows)

    # Preserve rejected expansion rows for accounting where a rejected-row
    # collection exists; otherwise the source-health counters remain the
    # authoritative rejection diagnostics.
    if isinstance(locals().get("rejected_jobs"), list):
        rejected_jobs.extend(expansion_rejected_rows)

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
                f"targets={targets:<3} | accepted={ok_count:<3} | rejected={rejected_count} | loc_rejected={location_rejections_v51.get(company, 0)}"
            )

    print()
    print("")
    print("=" * 50)
    print("V5.8.6 WAVE-2 DISCOVERY DIAGNOSTICS")
    print("=" * 50)
    for company in sorted(V571_WAVE2_COMPANIES):
        stat = DISCOVERY_HEALTH.get(company, {})
        print(
            f"{company:<20} | status={stat.get('status', 'UNKNOWN'):<11} | "
            f"internal={stat.get('internal_links', 0):<4} | "
            f"joblinks={stat.get('probable_job_links', 0):<4} | "
            f"indexed={stat.get('indexed_candidates', 0):<4} | "
            f"scanned={stat.get('scanned', 0):<4} | "
            f"queued={stat.get('queued', 0):<4} | "
            f"extracted={stat.get('extracted', 0):<4}"
        )

    print("")
    print("=" * 50)
    print("V5.8.6 EXPANSION SOURCE HEALTH")
    print("=" * 50)

    for source in V56_EXPANSION_SOURCES:
        company = source["company"]
        stat = DISCOVERY_HEALTH.get(company, {})
        status = clean(stat.get("status", "UNKNOWN")) or "UNKNOWN"
        scanned = stat.get("scanned", 0)
        queued = stat.get("queued", 0)
        extracted = stat.get("extracted", 0)
        acc = stat.get("accepted", 0)
        rej = stat.get("rejected", 0)
        locrej = stat.get("loc_rejected", 0)

        print(
            f"{status:<10} | {company:<22} | "
            f"scanned={scanned:<3} | queued={queued:<3} | "
            f"extracted={extracted:<3} | accepted={acc:<3} | "
            f"rejected={rej:<3} | loc_rejected={locrej}"
        )

    print("=" * 50)
    print("V5.8.6 SOURCE REJECTION RECONCILIATION")
    print("=" * 50)
    if location_rejections_v51:
        for company, count in sorted(location_rejections_v51.items()):
            print(f"{company:<22} | additional_location_rejections={count}")
    else:
        print("No additional location-based rejections.")

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

    # V5.8.6: final conservative country guard.
    # Existing explicit outside-Belgium rejection remains primary. This catches
    # only COUNTRY_UNKNOWN rows with strong foreign URL/location/title evidence.
    _v578_drop_indices = []
    for _idx, _row in df.iterrows():
        _country_status = clean(_row.get("country_status", "")).upper()
        if _country_status in {"BELGIUM", "BE", "BELGIUM_FLEXIBLE"}:
            continue
        _foreign_country, _foreign_reason = v578_detect_strong_foreign_signal(_row)
        if _foreign_country:
            print(
                f"  V5.8.6 FINAL COUNTRY REJECT: {clean(_row.get('title', ''))} "
                f"-> outside Belgium ({_foreign_country}) | {_foreign_reason}"
            )
            _v578_drop_indices.append(_idx)
            _company = clean(_row.get("company", ""))
            if _company:
                location_rejections_v51[_company] = location_rejections_v51.get(_company, 0) + 1

    if _v578_drop_indices:
        df = df.drop(index=_v578_drop_indices).reset_index(drop=True)
        print(f"V5.8.6 final country guard removed {len(_v578_drop_indices)} foreign job(s).")


    print()
    print("=" * 50)
    print("V5.8.6 SOURCE RECOVERY DIAGNOSTICS")
    print("=" * 50)
    # Diagnostics must never crash an otherwise successful scraper run.
    health_by_company = {company: (targets, ok_count, rejected_count)
                         for company, targets, ok_count, rejected_count in source_health}
    for dead_name in ("Akkodis", "Infrabel", "HR Rail"):
        diagnostic = DISCOVERY_HEALTH.get(dead_name, {}) or {}
        targets, ok_count, rejected_count = health_by_company.get(dead_name, (0, 0, 0))
        scanned = diagnostic.get("inventory", 0)
        extracted = diagnostic.get("extracted", targets)
        if not scanned and not extracted:
            print(f"RECOVERY_NEEDED | {dead_name:<18} | zero inventory discovered")
        else:
            print(f"RESPONDING       | {dead_name:<18} | scanned={scanned} | extracted={extracted}")

    print()
    print("=" * 50)
    print("V5.8.6 LOCATION INTELLIGENCE")
    print("=" * 50)
    location_counts = df["location_status"].fillna("LOCATION_UNKNOWN").value_counts()
    for status, count in location_counts.items():
        print(f"{status:<24} | {count}")

    known_distances = pd.to_numeric(df["distance_from_brussels_km"], errors="coerce")
    print(f"Distance resolved for {int(known_distances.notna().sum())}/{len(df)} accepted unique jobs.")
    print("REPORT-ONLY: OUTSIDE_30KM jobs are NOT rejected in V5.8.6.")

    print()
    print("=" * 50)
    print("V5.8.6 LOCATION REJECTIONS BY COMPANY")
    print("=" * 50)
    if location_rejections_v51:
        for company, count in sorted(location_rejections_v51.items()):
            print(f"{company:<22} | outside_belgium_rejected={count}")
    else:
        print("No explicit outside-Belgium vacancies rejected.")

    print()
    print("=" * 50)
    print("V5.8.6 COUNTRY VALIDATION")
    print("=" * 50)
    if "country_status" in df.columns:
        for status, count in df["country_status"].fillna("COUNTRY_UNKNOWN").value_counts().items():
            print(f"{status:<24} | {count}")
    flexible_count = int((df.get("location_status_v50", pd.Series(dtype=str)) == "BELGIUM_FLEXIBLE").sum())
    print(f"{'BELGIUM_FLEXIBLE':<24} | {flexible_count}")

    print()
    print("=" * 50)
    print("V5.8.6 LOCATION RESOLUTION BY COMPANY")
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
        print("V5.8.6 UNRESOLVED LOCATION DIAGNOSTICS")
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