# -*- coding: utf-8 -*-

from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, urldefrag
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

    print(
        "  strategy: Cegeka HTML listing"
    )

    html = fetch(
        source["url"]
    )

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    all_job_links = []

    for anchor in soup.find_all(
        "a",
        href=True,
    ):

        url = normalize_url(
            anchor["href"],
            source["url"],
        )

        path = urlparse(url).path.lower()

        if (
            "/jobs/all-jobs/" in path
            and re.search(r"-\d+$", path)
        ):

            title = clean(
                anchor.get_text(
                    " ",
                    strip=True,
                )
            )

            all_job_links.append(
                (url, title)
            )

    # Remove duplicate links
    unique = {}

    for url, title in all_job_links:
        unique[url] = title

    all_job_links = list(
        unique.items()
    )

    print(
        "  all Cegeka vacancy links:",
        len(all_job_links),
    )

    candidates = []

    for url, title in all_job_links:

        slug = (
            urlparse(url)
            .path
            .split("/")[-1]
            .replace("-", " ")
        )

        combined = clean(
            title + " " + slug
        )

        if looks_targeted(combined):

            candidates.append(
                (url, title)
            )

            print(
                "  TARGET LINK:",
                title or slug,
            )

    print(
        "  relevant vacancy links:",
        len(candidates),
    )

    return candidates


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

    print(
        "  strategy: Capgemini Belgium search"
    )

    candidates = []

    # The search page is paginated. Request several pages
    # instead of assuming size=100 will always be honored.

    for page in range(1, 13):

        url = (
            "https://www.capgemini.com/careers/"
            "join-capgemini/job-search/"
            "?country_code=en-be"
            "&country_name=Belgium"
            f"&page={page}"
            "&size=15"
        )

        try:
            html = fetch(url)

        except Exception as exc:

            print(
                f"  page {page} skipped:",
                exc,
            )

            continue

        found = discover_from_listing(
            html,
            source,
        )

        candidates.extend(found)

        # If no useful links are found, still try a few pages,
        # because Capgemini can render search content differently.

        time.sleep(0.7)

    unique = {}

    for url, text in candidates:
        unique[url] = text

    result = list(
        unique.items()
    )

    print(
        "  relevant vacancy links:",
        len(result),
    )

    return result


# ============================================================
# AKKODIS
# ============================================================

def discover_akkodis(source):

    print(
        "  strategy: Akkodis Belgium careers discovery"
    )

    candidates = []

    # Try several current public entry points.
    # Some Akkodis routes redirect depending on locale/session.

    entry_points = [
        "https://www.akkodis.com/en-be/careers",
        "https://www.akkodis.com/en-be/careers/jobs",
        "https://www.akkodis.com/en-be",
    ]

    for entry in entry_points:

        try:
            html = fetch(entry)

        except Exception as exc:

            print(
                "  entry skipped:",
                entry,
                "->",
                exc,
            )

            continue

        soup = BeautifulSoup(
            html,
            "html.parser",
        )

        for anchor in soup.find_all(
            "a",
            href=True,
        ):

            url = normalize_url(
                anchor["href"],
                entry,
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

            title = clean(
                anchor.get_text(
                    " ",
                    strip=True,
                )
            )

            slug = (
                urlparse(url)
                .path
                .split("/")[-2]
                .replace("-", " ")
            )

            combined = clean(
                title + " " + slug
            )

            if looks_targeted(
                combined
            ):
                candidates.append(
                    (url, title)
                )

        time.sleep(0.7)

    unique = {}

    for url, text in candidates:
        unique[url] = text

    result = list(
        unique.items()
    )

    print(
        "  relevant vacancy links:",
        len(result),
    )

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

    text = text.lower()

    equivalent = bool(
        re.search(
            r"or equivalent"
            r"|equivalent experience"
            r"|equivalent qualification"
            r"|gelijkwaardige ervaring"
            r"|ervaring gelijkwaardig"
            r"|expérience équivalente",
            text,
        )
    )

    master = bool(
        re.search(
            r"\bmaster'?s?\b"
            r"|\bmaster degree\b"
            r"|\bmaster diploma\b"
            r"|\bmasterdiploma\b"
            r"|\bmaster en\b"
            r"|\bmaster in\b",
            text,
        )
    )

    bachelor = bool(
        re.search(
            r"\bbachelor'?s?\b"
            r"|\bbachelor degree\b"
            r"|\bbachelor diploma\b"
            r"|\bbachelordiploma\b",
            text,
        )
    )

    technical_terms = (
        r"computer science"
        r"|engineering"
        r"|informatics"
        r"|information technology"
        r"|data science"
        r"|mathematics"
        r"|statistics"
        r"|ict"
        r"|informatica"
        r"|ingenieur"
    )

    technical_degree = bool(
        re.search(
            rf"(?:degree|bachelor|master|diploma)"
            rf".{{0,100}}(?:{technical_terms})",
            text,
        )
        or
        re.search(
            rf"(?:{technical_terms})"
            rf".{{0,100}}"
            rf"(?:degree|bachelor|master|diploma)",
            text,
        )
    )

    if technical_degree:

        if equivalent:
            return (
                "technical degree or "
                "equivalent experience"
            )

        return (
            "mandatory specific "
            "technical degree"
        )

    if master:

        if equivalent:
            return (
                "Master's or "
                "equivalent experience"
            )

        return "mandatory Master's"

    if bachelor:

        if equivalent:
            return (
                "Bachelor's or "
                "equivalent experience"
            )

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

    if (
        degree
        == "mandatory specific technical degree"
    ):

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

    text = (
        job["title"]
        + " "
        + job["description"]
    ).lower()

    value = 35

    reasons = [
        job["job_family"]
    ]

    fam = job["job_family"]

    if fam == "HR Data / People Analytics":

        value += 22

        reasons.append(
            "high-priority HR/data family"
        )

    elif fam in [
        "Data Analyst",
        "BI / Power BI",
    ]:

        value += 18

    elif fam in [
        "Data Governance / Quality",
        "Reporting",
    ]:

        value += 15

    elif fam == "Data Engineering (stretch)":

        value -= 8

        reasons.append(
            "stretch role"
        )

    else:
        value += 10

    matched, gaps = skill_information(
        job
    )

    for skill in matched:
        value += SKILLS[skill]

    if matched:

        reasons.append(
            "matched: "
            + ", ".join(
                matched[:6]
            )
        )

    if gaps:

        value -= min(
            15,
            len(gaps) * 3,
        )

        reasons.append(
            "potential gaps: "
            + ", ".join(
                gaps[:5]
            )
        )

    years = extract_experience(
        text
    )

    if years is not None:

        reasons.append(
            f"requires {years}+ years"
        )

        if years >= 6:
            value -= 22

        elif years == 5:
            value -= 15

        elif years == 4:
            value -= 8

        elif years <= 3:
            value += 3

    title = job["title"].lower()

    if "senior" in title:

        value -= 8
        reasons.append("senior title")

    if "expert" in title:

        value -= 10
        reasons.append("expert title")

    degree = degree_requirement(
        text
    )

    if (
        "equivalent experience"
        in degree.lower()
    ):

        value -= 5
        reasons.append(degree)

    elif degree == "Bachelor's degree":

        reasons.append(
            "Bachelor's degree requested"
        )

    location = job.get(
        "location",
        "",
    ).lower()

    if any(
        place in location
        for place in [
            "brussels",
            "bruxelles",
            "brussel",
            "anderlecht",
            "schaerbeek",
            "schaarbeek",
            "diegem",
            "machelen",
        ]
    ):

        value += 5
        reasons.append(
            "Brussels area"
        )

    elif any(
        place in location
        for place in [
            "antwerp",
            "antwerpen",
            "brugge",
            "bruges",
            "west flanders",
            "west-vlaanderen",
        ]
    ):

        value -= 8

        reasons.append(
            "outside preferred Brussels area"
        )

    return (
        max(
            0,
            min(100, value),
        ),
        "; ".join(reasons),
    )


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
    print("JOB SCRAPER V3 - COMPANY ADAPTER VERSION")
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
