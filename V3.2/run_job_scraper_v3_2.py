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
            re.search(
                r"/job/[^/]+",
                path,
            )
            or re.search(
                r"/(?:be-en/)?jobs/[^/]+",
                path,
            )
        )

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

        return make_job(
            source,
            title,
            description,
            url,
            location,
            clean(employment),
        )

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
    }


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

    description = page_description(
        soup
    )

    if len(description) < 150:
        return None

    location = guess_location(
        soup,
        description,
    )

    return make_job(
        source,
        title,
        description,
        url,
        location,
    )


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
    print("  strategy: Cegeka listing + indexed discovery + live seed validation")

    candidates = []

    # --------------------------------------------------------
    # 1. Normal server-rendered listing
    # --------------------------------------------------------
    try:
        html = fetch(source["url"])
        soup = BeautifulSoup(html, "html.parser")
        all_links = {}

        for anchor in soup.find_all("a", href=True):
            url = normalize_url(anchor["href"], source["url"])
            path = urlparse(url).path.lower()

            if "/jobs/all-jobs/" in path and re.search(r"-\d+$", path):
                all_links[url] = clean(anchor.get_text(" ", strip=True))

        print("  server-rendered vacancy links:", len(all_links))

        for url, title in all_links.items():
            slug = (
                urlparse(url).path.split("/")[-1]
                .replace("-", " ")
                .replace("_", " ")
            )

            if looks_targeted(clean(title + " " + slug)):
                candidates.append((url, title))

    except Exception as exc:
        print("  Cegeka listing skipped:", exc)

    # --------------------------------------------------------
    # 2. Search-index discovery
    #
    # Cegeka's current jobs page is partly client-rendered.
    # Search engines can therefore see individual vacancies that
    # requests/BeautifulSoup does not receive in the listing HTML.
    # We use TWO independent discovery paths. The detail page must
    # still pass is_job_url() and later real-vacancy validation.
    # --------------------------------------------------------
    queries = [
        'site:cegeka.com/en/be/jobs/all-jobs/ "Data Analyst"',
        'site:cegeka.com/en/be/jobs/all-jobs/ "Data Engineer"',
        'site:cegeka.com/en/be/jobs/all-jobs/ "BI Developer"',
        'site:cegeka.com/en/be/jobs/all-jobs/ "Business Intelligence"',
        'site:cegeka.com/en/be/jobs/all-jobs/ "Power BI"',
        'site:cegeka.com/en/be/jobs/all-jobs/ "Data Governance"',
        'site:cegeka.com/en/be/jobs/all-jobs/ "Data Quality"',
        'site:cegeka.com/en/be/jobs/all-jobs/ "People Analytics"',
        'site:cegeka.com/en/be/jobs/all-jobs/ "HR Data"',
        'site:cegeka.com/en/be/jobs/all-jobs/ "Reporting Analyst"',
    ]

    indexed_found = 0

    for query in queries:
        discovered = []

        try:
            discovered.extend(
                search_discovery(
                    query,
                    domains=["cegeka.com"],
                    max_results=20,
                )
            )
        except Exception as exc:
            print("  Cegeka DuckDuckGo discovery skipped:", exc)

        try:
            discovered.extend(
                search_discovery_bing(
                    query,
                    domains=["cegeka.com"],
                    max_results=20,
                )
            )
        except Exception as exc:
            print("  Cegeka Bing discovery skipped:", exc)

        for url, title in discovered:
            if not is_job_url(url, source):
                continue

            slug = (
                urlparse(url).path.split("/")[-1]
                .replace("-", " ")
                .replace("_", " ")
            )

            if looks_targeted(clean(title + " " + slug)):
                candidates.append((url, title))
                indexed_found += 1

        time.sleep(0.5)

    print("  indexed target candidates:", indexed_found)

    # --------------------------------------------------------
    # 3. Current live Cegeka Data & AI seed pages
    #
    # Safety net for client-rendering/search-index outages.
    # These are not accepted blindly: scrape_company() fetches the
    # page, verifies the actual title/description, applies target
    # family detection and all normal hard filters.
    #
    # Stale/removed seed URLs simply fail to fetch and disappear.
    # --------------------------------------------------------
    live_seeds = [
        (
            "https://www.cegeka.com/en/be/jobs/all-jobs/"
            "data-engineer-data-ai-6536",
            "Data Engineer - Data & AI",
        ),
        (
            "https://www.cegeka.com/en/be/jobs/all-jobs/"
            "data-engineer-ms-fabric-data-ai-7308",
            "Data Engineer MS Fabric - Data & AI",
        ),
        (
            "https://www.cegeka.com/en/be/jobs/all-jobs/"
            "data-governance-lead-data-ai-7896",
            "Data Governance Lead - Data & AI",
        ),
    ]

    seed_added = 0

    for url, title in live_seeds:
        if looks_targeted(title):
            candidates.append((url, title))
            seed_added += 1

    print("  live seed candidates:", seed_added)

    # --------------------------------------------------------
    # Deduplicate before opening detail pages.
    # --------------------------------------------------------
    unique = {}

    for url, title in candidates:
        unique[url] = title

    result = list(unique.items())

    print("  relevant vacancy links:", len(result))
    return result


# ============================================================
# SMALS
# ============================================================

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
    print("  strategy: Capgemini Belgium page + indexed-job fallback")

    candidates = []

    try:
        html = fetch(source["url"])
        soup = BeautifulSoup(html, "html.parser")

        for anchor in soup.find_all("a", href=True):
            url = normalize_url(anchor["href"], source["url"])
            title = clean(anchor.get_text(" ", strip=True))

            if not host_matches(url, source["domain"]):
                continue
            if not is_job_url(url, source):
                continue

            slug = urlparse(url).path.split("/")[-1].replace("-", " ")
            if looks_targeted(clean(title + " " + slug)):
                candidates.append((url, title))

    except Exception as exc:
        print("  Capgemini Belgium page skipped:", exc)

    queries = [
        'site:careers.capgemini.com/job/ Belgium "Data Analyst"',
        'site:careers.capgemini.com/job/ Belgium "Data Engineer"',
        'site:careers.capgemini.com/job/ Belgium "Business Intelligence"',
        'site:careers.capgemini.com/job/ Belgium "Power BI"',
        'site:careers.capgemini.com/job/ Belgium "Data Governance"',
        'site:careers.capgemini.com/job/ Belgium "Data Quality"',
        'site:careers.capgemini.com/job/ Diegem "Data"',
    ]

    for query in queries:
        try:
            for url, title in search_discovery(
                query, domains=["capgemini.com"], max_results=20
            ):
                if not is_job_url(url, source):
                    continue
                slug = urlparse(url).path.split("/")[-1].replace("-", " ")
                if looks_targeted(clean(title + " " + slug)):
                    candidates.append((url, title))
            time.sleep(0.6)
        except Exception as exc:
            print("  Capgemini indexed discovery skipped:", exc)

    unique = {}
    for url, title in candidates:
        unique[url] = title

    result = list(unique.items())
    print("  relevant vacancy links:", len(result))
    return result

# ============================================================
# AKKODIS
# ============================================================

def discover_akkodis(source):
    print("  strategy: Akkodis Belgium careers + indexed-job fallback")

    candidates = []

    for entry in [
        "https://www.akkodis.com/en-be/careers",
        "https://www.akkodis.com/en-be",
    ]:
        try:
            html = fetch(entry)
            soup = BeautifulSoup(html, "html.parser")

            for anchor in soup.find_all("a", href=True):
                url = normalize_url(anchor["href"], entry)
                if not host_matches(url, source["domain"]):
                    continue
                if not is_job_url(url, source):
                    continue

                title = clean(anchor.get_text(" ", strip=True))
                parts = urlparse(url).path.split("/")
                slug = parts[-2].replace("-", " ") if len(parts) >= 2 else ""

                if looks_targeted(clean(title + " " + slug)):
                    candidates.append((url, title))

        except Exception as exc:
            print("  Akkodis entry skipped:", entry, "->", exc)

        time.sleep(0.5)

    queries = [
        'site:akkodis.com/en-be/careers/jobs/ "Data Analyst"',
        'site:akkodis.com/en-be/careers/jobs/ "Data Engineer"',
        'site:akkodis.com/en-be/careers/jobs/ "Power BI"',
        'site:akkodis.com/en-be/careers/jobs/ "Business Intelligence"',
        'site:akkodis.com/en-be/careers/jobs/ "Data Governance"',
        'site:akkodis.com/en-be/careers/jobs/ "Data Quality"',
    ]

    for query in queries:
        try:
            for url, title in search_discovery(
                query, domains=["akkodis.com"], max_results=20
            ):
                if not is_job_url(url, source):
                    continue
                parts = urlparse(url).path.split("/")
                slug = parts[-2].replace("-", " ") if len(parts) >= 2 else ""
                if looks_targeted(clean(title + " " + slug)):
                    candidates.append((url, title))
            time.sleep(0.6)
        except Exception as exc:
            print("  Akkodis indexed discovery skipped:", exc)

    unique = {}
    for url, title in candidates:
        unique[url] = title

    result = list(unique.items())
    print("  relevant vacancy links:", len(result))
    return result

# ============================================================
# DISCOVERY ROUTER
# ============================================================

def discover(source):

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

    return []


# ============================================================
# EXPERIENCE
# ============================================================

def extract_experience(text):

    text = text.lower()

    patterns = [
        r"(\d+)\s*\+\s*years",
        r"minimum\s+(?:of\s+)?(\d+)\s+years",
        r"at least\s+(\d+)\s+years",
        r"(\d+)\s+years\s+of\s+experience",
        r"(\d+)\s+years['’]?\s+experience",

        r"(\d+)\s+jaar\s+ervaring",
        r"minimaal\s+(\d+)\s+jaar",
        r"minimum\s+(\d+)\s+jaar",
        r"minstens\s+(\d+)\s+jaar",

        r"(\d+)\s+ans\s+d['’]expérience",
        r"minimum\s+(\d+)\s+ans",
        r"au moins\s+(\d+)\s+ans",
    ]

    years = []

    for pattern in patterns:

        for match in re.findall(
            pattern,
            text,
        ):

            try:
                years.append(
                    int(match)
                )

            except ValueError:
                pass

    if not years:
        return None

    return max(years)


# ============================================================
# DEGREE REQUIREMENTS
# ============================================================

def degree_requirement(text):
    lower = clean(text).lower()
    sentences = re.split(r"(?<=[.!?;])\s+|\n+", lower)
    contexts = []

    edu_words = re.compile(
        r"\b(bachelor(?:'s)?|master(?:'s)?|degree|diploma|"
        r"bachelordiploma|masterdiploma|diplôme|diplome)\b",
        re.I,
    )

    for sentence in sentences:
        if not edu_words.search(sentence):
            continue

        # Do not interpret the data-management concept "master data"
        # as an academic Master's requirement.
        if (
            "master data" in sentence
            and not re.search(
                r"master(?:'s)?\s+(degree|diploma)|"
                r"degree.{0,50}master|"
                r"master.{0,50}(computer science|engineering|informatics|"
                r"information technology|data science|mathematics|"
                r"statistics|ict|informatica|ingenieur)",
                sentence,
                re.I,
            )
        ):
            continue

        contexts.append(sentence)

    if not contexts:
        return "not specified"

    context = " ".join(contexts)

    equivalent = bool(re.search(
        r"or equivalent|equivalent experience|equivalent qualification|"
        r"gelijkwaardige ervaring|gelijkwaardig door ervaring|"
        r"ervaring gelijkwaardig|of gelijkwaardig|"
        r"expérience équivalente|experience équivalente|"
        r"ou expérience équivalente",
        context, re.I
    ))

    preferred = bool(re.search(
        r"\b(preferred|preferably|ideally|nice to have)\b|"
        r"\bbij voorkeur\b|\bde préférence\b|\bidéalement\b",
        context, re.I
    ))

    bachelor = bool(re.search(r"\bbachelor(?:'s)?\b|\bbachelordiploma\b", context))
    master = bool(re.search(r"\bmaster(?:'s)?\b|\bmasterdiploma\b", context))

    bachelor_or_master = bool(re.search(
        r"\bbachelor.{0,35}(?:or|of|ou|/).{0,35}master\b|"
        r"\bmaster.{0,35}(?:or|of|ou|/).{0,35}bachelor\b",
        context, re.I
    ))

    technical_terms = (
        r"computer science|business engineering|engineering|informatics|"
        r"information technology|business it|data science|mathematics|"
        r"statistics|ict|informatica|ingenieur"
    )

    technical_degree = bool(
        re.search(
            rf"(?:degree|bachelor|master|diploma).{{0,120}}(?:{technical_terms})",
            context, re.I
        )
        or re.search(
            rf"(?:{technical_terms}).{{0,120}}(?:degree|bachelor|master|diploma)",
            context, re.I
        )
    )

    if bachelor_or_master:
        if equivalent:
            return "Bachelor's/Master's or equivalent experience"
        if preferred:
            return "Bachelor's/Master's preferred"
        if technical_degree:
            return "mandatory Bachelor/Master in technical field"
        return "Bachelor's or Master's degree"

    if technical_degree:
        if equivalent:
            return "technical degree or equivalent experience"
        if preferred:
            return "technical degree preferred"
        return "mandatory specific technical degree"

    if master:
        if equivalent:
            return "Master's or equivalent experience"
        if preferred:
            return "Master's preferred"
        return "mandatory Master's"

    if bachelor:
        if equivalent:
            return "Bachelor's or equivalent experience"
        if preferred:
            return "Bachelor's preferred"
        return "Bachelor's degree"

    return "not specified"

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

    text = (
        job["title"]
        + " "
        + job["description"]
    ).lower()

    if any(
        term in text
        for term in [
            "internship",
            "traineeship",
            "stage ",
        ]
    ):
        return False, "internship"

    if any(
        term in title
        for term in [
            "financial analyst",
            "finance analyst",
            "financial controller",
            "treasury analyst",
        ]
    ):
        return (
            False,
            "finance-focused role",
        )

    degree = degree_requirement(
        text
    )

    if degree == "mandatory Master's":

        return (
            False,
            "mandatory Master's degree",
        )

    if degree in [
        "mandatory specific technical degree",
        "mandatory Bachelor/Master in technical field",
    ]:

        return (
            False,
            "mandatory specific "
            "technical/ICT degree",
        )

    years = extract_experience(
        text
    )

    if (
        years is not None
        and years >= 8
    ):

        return (
            False,
            f"requires {years}+ years "
            f"relevant experience",
        )

    return True, "passed"


# ============================================================
# MATCH SCORE
# ============================================================

def score(job):
    text = (job["title"] + " " + job["description"]).lower()
    fam = job["job_family"]
    reasons = [fam]

    family_base = {
        "HR Data / People Analytics": 72,
        "Data Analyst": 68,
        "BI / Power BI": 68,
        "Data Governance / Quality": 64,
        "Reporting": 64,
        "Data / Analytics Consulting": 60,
        "Functional / Business Data Analysis": 60,
        "Data Engineering (stretch)": 48,
    }

    value = family_base.get(fam, 50)
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

    value += min(18, sum(bonuses.get(skill, 0) for skill in matched))

    if matched:
        reasons.append("matched: " + ", ".join(matched[:6]))

    if gaps:
        value -= min(12, len(gaps) * 2)
        reasons.append("potential gaps: " + ", ".join(gaps[:5]))

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

    title = job["title"].lower()

    if "senior" in title:
        value -= 7
        reasons.append("senior title")

    if "expert" in title:
        value -= 9
        reasons.append("expert title")

    if "manager" in title or "lead" in title:
        value -= 12
        reasons.append("leadership title")

    if "architect" in title:
        value -= 12
        reasons.append("architect title")

    degree = degree_requirement(text)

    if "equivalent experience" in degree.lower():
        value -= 2
        reasons.append(degree)
    elif degree in ["Bachelor's degree", "Bachelor's or Master's degree"]:
        value -= 3
        reasons.append(degree)
    elif "preferred" in degree.lower():
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
# SCRAPE ONE COMPANY
# ============================================================

def scrape_source(source):

    candidates = discover(
        source
    )

    jobs = []

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

        except Exception as exc:

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

    print()
    print("=" * 50)
    print("JOB SCRAPER V3.2 - CEGEKA DISCOVERY VERSION")
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

    columns = [
        "title",
        "job_family",
        "company",
        "location",
        "region",
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

    df.drop_duplicates(
        subset=["url"],
        keep="last",
        inplace=True,
    )

    df.sort_values(
        by="match_score",
        ascending=False,
        inplace=True,
    )

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
