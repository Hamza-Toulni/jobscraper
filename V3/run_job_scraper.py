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
# CONFIGURATION
# ============================================================

OUTPUT = "job_market_matches.csv"

SOURCES = [
    {
        "company": "Cegeka",
        "url": "https://jobs.cegeka.com/en/vacancies",
        "domain": "jobs.cegeka.com",
    },
    {
        "company": "Capgemini",
        "url": "https://www.capgemini.com/be-en/careers/",
        "domain": "capgemini.com",
    },
    {
        "company": "Akkodis",
        "url": "https://www.akkodis.com/en-be",
        "domain": "akkodis.com",
    },
    {
        "company": "Pauwels Consulting",
        "url": "https://www.pauwelsconsulting.com/en/jobs/",
        "domain": "pauwelsconsulting.com",
    },
    {
        "company": "Smals",
        "url": "https://www.smals.be/en/jobs",
        "domain": "smals.be",
    },
]


# ============================================================
# TARGET JOB FAMILIES
# ============================================================

FAMILIES = {
    "HR Data / People Analytics": [
        "hr data analyst",
        "hr analytics",
        "people analytics",
        "workforce analytics",
        "hris analyst",
        "hr reporting",
    ],
    "Data Analyst": [
        "data analyst",
        "data analytics analyst",
        "analytics analyst",
    ],
    "BI / Power BI": [
        "bi analyst",
        "bi developer",
        "business intelligence analyst",
        "business intelligence developer",
        "power bi analyst",
        "power bi developer",
    ],
    "Data Governance / Quality": [
        "data governance",
        "data quality analyst",
        "data quality specialist",
        "data steward",
    ],
    "Reporting": [
        "reporting analyst",
        "reporting developer",
        "reporting specialist",
    ],
    "Data / Analytics Consulting": [
        "data consultant",
        "analytics consultant",
        "bi consultant",
    ],
    "Functional / Business Data Analysis": [
        "functional analyst – data",
        "functional analyst - data",
        "functional analyst data",
        "business analyst – data",
        "business analyst - data",
        "business data analyst",
    ],
}

STRETCH = [
    "data engineer",
    "etl developer",
    "etl engineer",
    "data warehouse developer",
]


# ============================================================
# USER PROFILE
# ============================================================

# Skills that genuinely overlap with the user's profile.
# Weights represent relative relevance, not proficiency scores.

SKILLS = {
    "sql": 12,
    "power bi": 12,
    "etl": 10,
    "data warehouse": 9,
    "data quality": 8,
    "data governance": 8,
    "python": 5,
    "cognos": 4,
    "wherescape": 5,
    "reporting": 5,
    "hr analytics": 7,
    "people analytics": 7,
}

# Technologies/skills that are relevant but should NOT earn points
# simply because the vacancy mentions them.
#
# They are recorded as potential gaps instead.

GAP_SKILLS = [
    "databricks",
    "dbt",
    "microsoft fabric",
    "snowflake",
    "tableau",
    "azure",
    "collibra",
    "informatica",
    "purview",
    "spark",
    "scala",
]


HEADERS = {
    "User-Agent": "Mozilla/5.0 AppleWebKit/537.36 Chrome/149 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,nl;q=0.8,fr;q=0.7",
}

S = requests.Session()
S.headers.update(HEADERS)


# ============================================================
# BASIC HELPERS
# ============================================================

def clean(x):
    return re.sub(r"\s+", " ", str(x or "")).strip()


def norm(u, b):
    u = urljoin(b, u)
    u, _ = urldefrag(u)
    return u.rstrip("/")


def same(u, d):
    h = urlparse(u).netloc.lower()
    return h == d or h.endswith("." + d)


def fetch(u):
    r = S.get(
        u,
        timeout=25,
        allow_redirects=True,
    )

    r.raise_for_status()

    content_type = r.headers.get("content-type", "").lower()

    return r.text if "html" in content_type else ""


# ============================================================
# JOB FAMILY DETECTION
# ============================================================

def family(title):

    x = clean(title).lower()

    for fam, terms in FAMILIES.items():

        if any(term in x for term in terms):
            return fam

    if any(term in x for term in STRETCH):
        return "Data Engineering (stretch)"

    return ""


# ============================================================
# VACANCY URL VALIDATION
# ============================================================

def job_url(u):

    p = urlparse(u).path.lower()

    return bool(
        re.search(
            r"/job/|"
            r"/jobs/[^/]+|"
            r"/vacanc(?:y|ies)/[^/]+|"
            r"/job-search/[^/]+",
            p,
        )
    )


# ============================================================
# JSON-LD EXTRACTION
# ============================================================

def jsonlds(soup):

    for script in soup.find_all(
        "script",
        type="application/ld+json",
    ):

        try:
            x = json.loads(
                script.string or script.get_text()
            )

        except Exception:
            continue

        objects = x if isinstance(x, list) else [x]

        for obj in objects:

            if not isinstance(obj, dict):
                continue

            graph = (
                obj.get("@graph")
                if isinstance(obj.get("@graph"), list)
                else [obj]
            )

            for item in graph:

                if isinstance(item, dict):
                    yield item


# ============================================================
# LOCATION EXTRACTION
# ============================================================

def location(o):

    locations = o.get("jobLocation") or []

    if not isinstance(locations, list):
        locations = [locations]

    out = []

    for loc in locations:

        if not isinstance(loc, dict):
            continue

        address = loc.get("address", {})

        if not isinstance(address, dict):
            continue

        value = ", ".join(
            clean(address.get(k))
            for k in [
                "postalCode",
                "addressLocality",
                "addressRegion",
                "addressCountry",
            ]
            if address.get(k)
        )

        if value:
            out.append(value)

    return " / ".join(dict.fromkeys(out))


# ============================================================
# STRUCTURED JOB EXTRACTION
# ============================================================

def structured(html, src, url):

    soup = BeautifulSoup(html, "html.parser")

    out = []

    for o in jsonlds(soup):

        typ = o.get("@type", [])

        if not isinstance(typ, list):
            typ = [typ]

        if "JobPosting" not in typ:
            continue

        title = clean(o.get("title"))

        fam = family(title)

        if not fam:
            continue

        desc = clean(
            BeautifulSoup(
                str(o.get("description", "")),
                "html.parser",
            ).get_text(" ")
        )

        emp = o.get("employmentType", "")

        if isinstance(emp, list):
            emp = ", ".join(emp)
        else:
            emp = clean(emp)

        ju = norm(
            o.get("url") or url,
            src["url"],
        )

        out.append(
            {
                "title": title,
                "job_family": fam,
                "company": src["company"],
                "location": location(o),
                "region": "",
                "salary": "",
                "employment_type": emp,
                "url": ju,
                "description": desc,
                "source": (
                    src["company"]
                    .lower()
                    .replace(" ", "_")
                    + "_web"
                ),
            }
        )

    return out


# ============================================================
# LISTING PAGE DISCOVERY
# ============================================================

def links(html, src):

    soup = BeautifulSoup(html, "html.parser")

    details = []
    pages = []

    for a in soup.find_all("a", href=True):

        u = norm(
            a["href"],
            src["url"],
        )

        txt = clean(
            a.get_text(
                " ",
                strip=True,
            )
        )

        if not same(u, src["domain"]):
            continue

        # Only accept vacancy links whose visible title
        # belongs to one of our target job families.

        if family(txt) and job_url(u):
            details.append(u)

        href = a["href"].lower()

        if re.search(r"[?&]page=\d+", href):
            pages.append(u)

    return (
        list(dict.fromkeys(details)),
        list(dict.fromkeys(pages)),
    )


# ============================================================
# FALLBACK EXTRACTION
# ============================================================

def fallback(html, u, src):

    if not job_url(u):
        return None

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    h = soup.find("h1")

    title = (
        clean(h.get_text(" ", strip=True))
        if h
        else ""
    )

    fam = family(title)

    if not fam:
        return None

    main = soup.find("main")

    desc = (
        clean(main.get_text(" ", strip=True))
        if main
        else ""
    )

    if len(desc) < 200:
        return None

    return {
        "title": title,
        "job_family": fam,
        "company": src["company"],
        "location": "",
        "region": "",
        "salary": "",
        "employment_type": "",
        "url": u,
        "description": desc,
        "source": (
            src["company"]
            .lower()
            .replace(" ", "_")
            + "_web"
        ),
    }


# ============================================================
# REQUIREMENT EXTRACTION
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
        r"minimum\s+(\d+)\s+jaar",
        r"minstens\s+(\d+)\s+jaar",
        r"(\d+)\s+ans\s+d['’]expérience",
        r"minimum\s+(\d+)\s+ans",
    ]

    years = []

    for pattern in patterns:

        for match in re.findall(pattern, text):

            try:
                years.append(int(match))
            except Exception:
                pass

    if not years:
        return None

    # A vacancy can mention several experience requirements.
    # We use the largest explicit requirement conservatively.

    return max(years)


def extract_degree_requirement(text):

    t = text.lower()

    equivalent = bool(
        re.search(
            r"or equivalent"
            r"|equivalent experience"
            r"|equivalent qualification"
            r"|equivalent professional experience"
            r"|or equivalent through"
            r"|equivalent through",
            t,
        )
    )

    technical_fields = bool(
        re.search(
            r"\bict\b"
            r"|computer science"
            r"|engineering"
            r"|informatics"
            r"|information technology"
            r"|data science"
            r"|mathematics"
            r"|statistics",
            t,
        )
    )

    has_master = bool(
        re.search(
            r"\bmaster'?s?\b"
            r"|\bmaster degree\b"
            r"|\bmaster diploma\b"
            r"|\bmaster’s\b",
            t,
        )
    )

    has_bachelor = bool(
        re.search(
            r"\bbachelor'?s?\b"
            r"|\bbachelor degree\b"
            r"|\bbachelor’s\b",
            t,
        )
    )

    # Technical degree requirement such as:
    # "bachelor or master in ICT"
    # "degree in computer science"
    # "engineering degree"

    technical_degree = False

    technical_patterns = [
        r"(?:bachelor|master|degree|diploma).{0,100}"
        r"(?:ict|computer science|engineering|informatics|"
        r"information technology|data science|mathematics|statistics)",

        r"(?:ict|computer science|engineering|informatics|"
        r"information technology|data science|mathematics|statistics)"
        r".{0,100}(?:degree|bachelor|master|diploma)",
    ]

    for pattern in technical_patterns:

        if re.search(pattern, t):
            technical_degree = True
            break

    if technical_degree:

        if equivalent:
            return "technical degree or equivalent experience"

        return "mandatory specific technical degree"

    if has_master:

        if equivalent:
            return "Master's or equivalent experience"

        return "mandatory Master's"

    if has_bachelor:

        if equivalent:
            return "Bachelor's or equivalent experience"

        return "Bachelor's degree"

    return "not specified"


def extract_languages(text):

    t = text.lower()

    languages = []

    language_patterns = {
        "Dutch": [
            "dutch",
            "nederlands",
            "néerlandais",
        ],
        "French": [
            "french",
            "français",
            "francais",
            "frans",
        ],
        "English": [
            "english",
            "engels",
            "anglais",
        ],
    }

    for language, terms in language_patterns.items():

        if any(term in t for term in terms):
            languages.append(language)

    return ", ".join(languages)


def extract_skill_info(j):

    text = (
        j["title"]
        + " "
        + j["description"]
    ).lower()

    matched = []

    for skill in SKILLS:

        if skill in text:
            matched.append(skill)

    missing = []

    for skill in GAP_SKILLS:

        if skill in text:
            missing.append(skill)

    return matched, missing


# ============================================================
# HARD FILTERS
# ============================================================

def hard(j):

    title = j["title"].lower()

    text = (
        j["title"]
        + " "
        + j["description"]
    ).lower()

    # --------------------------------------------------------
    # Internship / traineeship
    # --------------------------------------------------------

    if any(
        x in text
        for x in [
            "internship",
            "traineeship",
            "intern ",
        ]
    ):
        return False, "internship"

    # --------------------------------------------------------
    # Finance-specific analyst jobs
    # --------------------------------------------------------

    if any(
        x in title
        for x in [
            "financial analyst",
            "finance analyst",
            "financial controller",
            "treasury analyst",
        ]
    ):
        return False, "finance-focused role"

    # --------------------------------------------------------
    # Degree requirements
    # --------------------------------------------------------

    degree = extract_degree_requirement(text)

    if degree == "mandatory Master's":

        return (
            False,
            "mandatory Master's degree",
        )

    if degree == "mandatory specific technical degree":

        return (
            False,
            "mandatory specific technical/ICT degree",
        )

    # --------------------------------------------------------
    # Experience requirements
    # --------------------------------------------------------

    years = extract_experience(text)

    # 8+ years is clearly beyond the target profile.

    if years is not None and years >= 8:

        return (
            False,
            f"requires {years}+ years relevant experience",
        )

    return True, "passed"


# ============================================================
# MATCH SCORING
# ============================================================

def score(j):

    text = (
        j["title"]
        + " "
        + j["description"]
    ).lower()

    s = 35

    reasons = [j["job_family"]]

    # --------------------------------------------------------
    # Job family
    # --------------------------------------------------------

    if j["job_family"] == "HR Data / People Analytics":

        s += 22
        reasons.append("high-priority HR/data family")

    elif j["job_family"] == "Data Analyst":

        s += 18

    elif j["job_family"] == "BI / Power BI":

        s += 18

    elif j["job_family"] == "Data Governance / Quality":

        s += 15

    elif j["job_family"] == "Reporting":

        s += 15

    elif j["job_family"] == "Data Engineering (stretch)":

        s -= 8
        reasons.append("stretch role")

    else:

        s += 10

    # --------------------------------------------------------
    # Matching skills
    # --------------------------------------------------------

    matched, missing = extract_skill_info(j)

    for skill in matched:

        s += SKILLS[skill]

    if matched:

        reasons.append(
            "matched: "
            + ", ".join(matched[:6])
        )

    # --------------------------------------------------------
    # Potential skill gaps
    # --------------------------------------------------------

    if missing:

        # Small penalty per advanced technology that appears
        # in the vacancy but is not part of the established profile.

        s -= min(15, len(missing) * 3)

        reasons.append(
            "potential gaps: "
            + ", ".join(missing[:5])
        )

    # --------------------------------------------------------
    # Experience requirement
    # --------------------------------------------------------

    years = extract_experience(text)

    if years is not None:

        reasons.append(
            f"requires {years}+ years"
        )

        if years >= 6:
            s -= 22

        elif years == 5:
            s -= 15

        elif years == 4:
            s -= 8

        elif years <= 3:
            s += 3

    # --------------------------------------------------------
    # Senior title
    # --------------------------------------------------------

    if "senior" in j["title"].lower():

        s -= 8
        reasons.append("senior title")

    if "expert" in j["title"].lower():

        s -= 10
        reasons.append("expert title")

    # --------------------------------------------------------
    # Degree requirement
    # --------------------------------------------------------

    degree = extract_degree_requirement(text)

    if "equivalent experience" in degree.lower():

        reasons.append(degree)

        # Equivalent experience means the role is not rejected,
        # but it should not receive the same score as a role
        # without such an educational requirement.

        s -= 5

    elif degree == "Bachelor's degree":

        reasons.append(
            "Bachelor's degree requested"
        )

    # --------------------------------------------------------
    # Location
    # --------------------------------------------------------

    loc = j.get("location", "").lower()

    if any(
        x in loc
        for x in [
            "brussels",
            "bruxelles",
            "brussel",
            "anderlecht",
        ]
    ):

        s += 5
        reasons.append("Brussels area")

    elif any(
        x in loc
        for x in [
            "antwerpen",
            "antwerp",
            "brugge",
            "bruges",
            "beerse",
            "west flanders",
        ]
    ):

        s -= 8
        reasons.append("outside preferred Brussels area")

    return (
        max(0, min(100, s)),
        "; ".join(reasons),
    )


# ============================================================
# SCRAPER
# ============================================================

def scrape(src):

    queue = [src["url"]]

    seen = set()

    detail = []

    while queue and len(seen) < 12:

        u = queue.pop(0)

        if u in seen:
            continue

        seen.add(u)

        try:

            h = fetch(u)

        except Exception as e:

            print(
                "  listing skipped:",
                e,
            )

            continue

        d, p = links(
            h,
            src,
        )

        detail += d

        for x in p:

            if (
                x not in seen
                and x not in queue
            ):
                queue.append(x)

        for j in structured(
            h,
            src,
            u,
        ):

            if job_url(j["url"]):
                detail.append(j["url"])

        time.sleep(0.1)

    detail = list(
        dict.fromkeys(detail)
    )[:80]

    print(
        f"  listing pages: {len(seen)} "
        f"| target links: {len(detail)}"
    )

    out = []

    for u in detail:

        try:

            h = fetch(u)

            js = structured(
                h,
                src,
                u,
            )

            if js:

                out += js

            else:

                j = fallback(
                    h,
                    u,
                    src,
                )

                if j:
                    out.append(j)

        except Exception as e:

            print(
                "  detail skipped:",
                e,
            )

        time.sleep(0.1)

    return list(
        {
            j["url"]: j
            for j in out
            if family(j["title"])
            and job_url(j["url"])
        }.values()
    )


# ============================================================
# MAIN PIPELINE
# ============================================================

def run():

    now = datetime.now(
        timezone.utc
    ).isoformat()

    accepted = []

    rejected = 0

    total_discovered = 0

    for src in SOURCES:

        print(
            "\n======================================"
        )

        print(
            "Scraping",
            src["company"],
        )

        print(
            "======================================"
        )

        try:

            jobs = scrape(src)

        except Exception as e:

            print(
                "  SOURCE ERROR:",
                e,
            )

            continue

        total_discovered += len(jobs)

        source_accepted = 0

        source_rejected = 0

        for j in jobs:

            text = (
                j["title"]
                + " "
                + j["description"]
            )

            required_experience = (
                extract_experience(text)
            )

            degree_requirement = (
                extract_degree_requirement(text)
            )

            required_languages = (
                extract_languages(text)
            )

            matched_skills, missing_skills = (
                extract_skill_info(j)
            )

            ok, status = hard(j)

            if not ok:

                print(
                    "  REJECT:",
                    j["title"],
                    "->",
                    status,
                )

                rejected += 1
                source_rejected += 1

                continue

            sc, why = score(j)

            j.update(
                date_found=now,
                active=True,
                required_experience=(
                    required_experience
                    if required_experience is not None
                    else ""
                ),
                degree_requirement=degree_requirement,
                required_languages=required_languages,
                matched_skills=", ".join(
                    matched_skills
                ),
                missing_skills=", ".join(
                    missing_skills
                ),
                match_score=sc,
                match_reason=why,
                hard_filter_status=status,
                hard_filter_reason="",
            )

            accepted.append(j)

            source_accepted += 1

            print(
                "  ACCEPT:",
                j["title"],
                f"-> score {sc}",
            )

        print(
            f"  real target vacancies: {len(jobs)}"
        )

        print(
            f"  accepted: {source_accepted}"
            f" | rejected: {source_rejected}"
        )

    # ========================================================
    # OUTPUT
    # ========================================================

    cols = [
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
        columns=cols,
    )

    print(
        "\n======================================"
    )

    print(
        "SCRAPER SUMMARY"
    )

    print(
        "======================================"
    )

    print(
        "Target vacancies discovered:",
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
            "No verified matches."
        )

        print(
            "Existing CSV left unchanged."
        )

        return

    df.drop_duplicates(
        "url",
        keep="last",
        inplace=True,
    )

    df.sort_values(
        "match_score",
        ascending=False,
        inplace=True,
    )

    df.to_csv(
        OUTPUT,
        index=False,
    )

    print(
        "Saved",
        len(df),
        "verified targeted jobs to",
        OUTPUT,
    )


if __name__ == "__main__":
    run()
