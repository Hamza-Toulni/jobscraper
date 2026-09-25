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
        "url": "https://www.cegeka.com/en/be/jobs/all-jobs",
        "domain": "cegeka.com",
    },
    {
        "company": "Capgemini",
        "url": "https://www.capgemini.com/careers/join-capgemini/job-search/?country_code=en-be&country_name=Belgium&size=100",
        "domain": "capgemini.com",
    },
    {
        "company": "Akkodis",
        "url": "https://www.akkodis.com/en-be/careers/jobs",
        "domain": "akkodis.com",
    },
    {
        "company": "Pauwels Consulting",
        "url": "https://www.pauwelsconsulting.com/en/jobs/",
        "domain": "pauwelsconsulting.com",
    },
    {
        "company": "Smals",
        "url": "https://www.smals.be/nl/jobs/list",
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
        "senior data analyst",
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
        "data quality expert",
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
        "data functional analyst",
        "business analyst – data",
        "business analyst - data",
        "business data analyst",
    ],
}


# Stretch jobs:
# We still collect them, but score them more cautiously.

STRETCH = [
    "data engineer",
    "etl developer",
    "etl engineer",
    "data warehouse developer",
]


# ============================================================
# USER PROFILE
# ============================================================

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


# Technologies that can indicate a potential skill gap.
# Mentioning them does not automatically reject the vacancy.

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
    "User-Agent": (
        "Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/149 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,nl;q=0.8,fr;q=0.7",
}


S = requests.Session()
S.headers.update(HEADERS)


# ============================================================
# BASIC HELPERS
# ============================================================

def clean(x):
    return re.sub(r"\s+", " ", str(x or "")).strip()


def norm(u, base):
    u = urljoin(base, u)
    u, _ = urldefrag(u)
    return u.rstrip("/")


def same(u, domain):
    host = urlparse(u).netloc.lower()

    return (
        host == domain
        or host.endswith("." + domain)
    )


def fetch(u):
    r = S.get(
        u,
        timeout=25,
        allow_redirects=True,
    )

    r.raise_for_status()

    content_type = r.headers.get(
        "content-type",
        "",
    ).lower()

    if "html" not in content_type:
        return ""

    return r.text


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
# VACANCY URL DETECTION
# ============================================================

def job_url(u):

    p = urlparse(u).path.lower()

    patterns = [

        # Generic
        r"/job/",

        # Smals
        r"/jobs/apply/\d+/",

        # Akkodis
        r"/careers/jobs/[^/]+/\d+",

        # Other common structures
        r"/jobs/[^/]+",
        r"/vacancy/[^/]+",
        r"/vacancies/[^/]+",
        r"/job-search/[^/]+",

    ]

    return any(
        re.search(pattern, p)
        for pattern in patterns
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

            raw = (
                script.string
                or script.get_text()
            )

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

            if not isinstance(graph, list):
                graph = [obj]

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

        address = loc.get(
            "address",
            {},
        )

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

    return " / ".join(
        dict.fromkeys(out)
    )


# ============================================================
# STRUCTURED JOB EXTRACTION
# ============================================================

def structured(html, src, url):

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    out = []

    for o in jsonlds(soup):

        typ = o.get(
            "@type",
            [],
        )

        if not isinstance(typ, list):
            typ = [typ]

        if "JobPosting" not in typ:
            continue

        title = clean(
            o.get("title")
        )

        fam = family(title)

        # This is where we now decide whether
        # the ACTUAL vacancy title belongs to
        # our target job families.

        if not fam:
            continue

        description_html = str(
            o.get(
                "description",
                "",
            )
        )

        desc = clean(

            BeautifulSoup(
                description_html,
                "html.parser",
            ).get_text(" ")
        )

        emp = o.get(
            "employmentType",
            "",
        )

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

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    details = []
    pages = []

    for a in soup.find_all(
        "a",
        href=True,
    ):

        u = norm(
            a["href"],
            src["url"],
        )

        if not same(
            u,
            src["domain"],
        ):
            continue

        # IMPORTANT CHANGE:
        #
        # We no longer require the visible link text
        # to say "Data Analyst", "BI Developer", etc.
        #
        # A real vacancy link could simply say:
        # "View job", "Read more", etc.
        #
        # We first collect real-looking vacancy URLs,
        # then inspect the actual vacancy title.

        if job_url(u):
            details.append(u)

        href = a["href"].lower()

        # Generic pagination

        if re.search(
            r"[?&]page=\d+",
            href,
        ):
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
        clean(
            h.get_text(
                " ",
                strip=True,
            )
        )
        if h
        else ""
    )

    fam = family(title)

    if not fam:
        return None

    main = soup.find("main")

    desc = (
        clean(
            main.get_text(
                " ",
                strip=True,
            )
        )
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
# EXPERIENCE EXTRACTION
# ============================================================

def extract_experience(text):

    text = text.lower()

    patterns = [

        # English
        r"(\d+)\s*\+\s*years",
        r"minimum\s+(?:of\s+)?(\d+)\s+years",
        r"at least\s+(\d+)\s+years",
        r"(\d+)\s+years\s+of\s+experience",
        r"(\d+)\s+years['’]?\s+experience",

        # Dutch
        r"(\d+)\s+jaar\s+ervaring",
        r"minimum\s+(\d+)\s+jaar",
        r"minstens\s+(\d+)\s+jaar",

        # French
        r"(\d+)\s+ans\s+d['’]expérience",
        r"minimum\s+(\d+)\s+ans",
        r"au moins\s+(\d+)\s+ans",

    ]

    years = []

    for pattern in patterns:

        matches = re.findall(
            pattern,
            text,
        )

        for match in matches:

            try:
                years.append(
                    int(match)
                )

            except Exception:
                pass

    if not years:
        return None

    return max(years)


# ============================================================
# DEGREE REQUIREMENT EXTRACTION
# ============================================================

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

    technical_patterns = [

        (
            r"(?:bachelor|master|degree|diploma)"
            r".{0,100}"
            r"(?:ict|computer science|engineering|"
            r"informatics|information technology|"
            r"data science|mathematics|statistics)"
        ),

        (
            r"(?:ict|computer science|engineering|"
            r"informatics|information technology|"
            r"data science|mathematics|statistics)"
            r".{0,100}"
            r"(?:degree|bachelor|master|diploma)"
        ),

    ]

    technical_degree = any(
        re.search(pattern, t)
        for pattern in technical_patterns
    )

    if technical_degree:

        if equivalent:
            return (
                "technical degree "
                "or equivalent experience"
            )

        return (
            "mandatory specific "
            "technical degree"
        )

    if has_master:

        if equivalent:
            return (
                "Master's or "
                "equivalent experience"
            )

        return "mandatory Master's"

    if has_bachelor:

        if equivalent:
            return (
                "Bachelor's or "
                "equivalent experience"
            )

        return "Bachelor's degree"

    return "not specified"


# ============================================================
# LANGUAGE EXTRACTION
# ============================================================

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

        if any(
            term in t
            for term in terms
        ):
            languages.append(language)

    return ", ".join(languages)


# ============================================================
# SKILL EXTRACTION
# ============================================================

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

    return (
        matched,
        missing,
    )


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

        return (
            False,
            "internship",
        )

    # --------------------------------------------------------
    # Finance-specific jobs
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

        return (
            False,
            "finance-focused role",
        )

    # --------------------------------------------------------
    # Degree requirements
    # --------------------------------------------------------

    degree = extract_degree_requirement(
        text
    )

    if degree == "mandatory Master's":

        return (
            False,
            "mandatory Master's degree",
        )

    if degree == (
        "mandatory specific "
        "technical degree"
    ):

        return (
            False,
            "mandatory specific "
            "technical/ICT degree",
        )

    # --------------------------------------------------------
    # Experience
    # --------------------------------------------------------

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

    return (
        True,
        "passed",
    )


# ============================================================
# MATCH SCORING
# ============================================================

def score(j):

    text = (
        j["title"]
        + " "
        + j["description"]
    ).lower()

    score_value = 35

    reasons = [
        j["job_family"]
    ]

    # --------------------------------------------------------
    # Job-family score
    # --------------------------------------------------------

    if (
        j["job_family"]
        == "HR Data / People Analytics"
    ):

        score_value += 22

        reasons.append(
            "high-priority HR/data family"
        )

    elif j["job_family"] in [
        "Data Analyst",
        "BI / Power BI",
    ]:

        score_value += 18

    elif j["job_family"] in [
        "Data Governance / Quality",
        "Reporting",
    ]:

        score_value += 15

    elif (
        j["job_family"]
        == "Data Engineering (stretch)"
    ):

        score_value -= 8

        reasons.append(
            "stretch role"
        )

    else:

        score_value += 10

    # --------------------------------------------------------
    # Skills
    # --------------------------------------------------------

    matched, missing = (
        extract_skill_info(j)
    )

    for skill in matched:

        score_value += SKILLS[skill]

    if matched:

        reasons.append(
            "matched: "
            + ", ".join(
                matched[:6]
            )
        )

    # --------------------------------------------------------
    # Potential gaps
    # --------------------------------------------------------

    if missing:

        score_value -= min(
            15,
            len(missing) * 3,
        )

        reasons.append(
            "potential gaps: "
            + ", ".join(
                missing[:5]
            )
        )

    # --------------------------------------------------------
    # Experience
    # --------------------------------------------------------

    years = extract_experience(
        text
    )

    if years is not None:

        reasons.append(
            f"requires {years}+ years"
        )

        if years >= 6:

            score_value -= 22

        elif years == 5:

            score_value -= 15

        elif years == 4:

            score_value -= 8

        elif years <= 3:

            score_value += 3

    # --------------------------------------------------------
    # Seniority
    # --------------------------------------------------------

    if "senior" in j["title"].lower():

        score_value -= 8

        reasons.append(
            "senior title"
        )

    if "expert" in j["title"].lower():

        score_value -= 10

        reasons.append(
            "expert title"
        )

    # --------------------------------------------------------
    # Degree
    # --------------------------------------------------------

    degree = extract_degree_requirement(
        text
    )

    if (
        "equivalent experience"
        in degree.lower()
    ):

        score_value -= 5

        reasons.append(
            degree
        )

    elif degree == "Bachelor's degree":

        reasons.append(
            "Bachelor's degree requested"
        )

    # --------------------------------------------------------
    # Location
    # --------------------------------------------------------

    loc = j.get(
        "location",
        "",
    ).lower()

    if any(
        x in loc
        for x in [
            "brussels",
            "bruxelles",
            "brussel",
            "anderlecht",
        ]
    ):

        score_value += 5

        reasons.append(
            "Brussels area"
        )

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

        score_value -= 8

        reasons.append(
            "outside preferred Brussels area"
        )

    return (
        max(
            0,
            min(
                100,
                score_value,
            ),
        ),
        "; ".join(reasons),
    )


# ============================================================
# SCRAPER
# ============================================================

def scrape(src):

    queue = [
        src["url"]
    ]

    seen = set()

    detail = []

    while (
        queue
        and len(seen) < 12
    ):

        u = queue.pop(0)

        if u in seen:
            continue

        seen.add(u)

        try:

            html = fetch(u)

        except Exception as e:

            print(
                "  listing skipped:",
                e,
            )

            continue

        details, pages = links(
            html,
            src,
        )

        detail += details

        for page in pages:

            if (
                page not in seen
                and page not in queue
            ):

                queue.append(page)

        # Some sites expose JobPosting
        # directly on listing pages.

        for job in structured(
            html,
            src,
            u,
        ):

            if job_url(
                job["url"]
            ):

                detail.append(
                    job["url"]
                )

        time.sleep(0.1)

    detail = list(
        dict.fromkeys(detail)
    )

    # Prevent a broken site from creating
    # an uncontrolled crawl.

    detail = detail[:150]

    print(
        f"  listing pages: {len(seen)} "
        f"| vacancy links discovered: "
        f"{len(detail)}"
    )

    out = []

    for u in detail:

        try:

            html = fetch(u)

            jobs = structured(
                html,
                src,
                u,
            )

            if jobs:

                out += jobs

            else:

                job = fallback(
                    html,
                    u,
                    src,
                )

                if job:
                    out.append(job)

        except Exception as e:

            print(
                "  detail skipped:",
                e,
            )

        time.sleep(0.1)

    # Final validation:
    #
    # Only keep actual target-family vacancies.

    unique = {
        job["url"]: job

        for job in out

        if family(job["title"])
        and job_url(job["url"])
    }

    return list(
        unique.values()
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

    print(
        "\n======================================"
    )

    print(
        "JOB SCRAPER V3"
    )

    print(
        "======================================"
    )

    for src in SOURCES:

        print(
            "\n--------------------------------------"
        )

        print(
            "Scraping",
            src["company"],
        )

        print(
            "--------------------------------------"
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
                extract_experience(
                    text
                )
            )

            degree_requirement = (
                extract_degree_requirement(
                    text
                )
            )

            required_languages = (
                extract_languages(
                    text
                )
            )

            (
                matched_skills,
                missing_skills,
            ) = extract_skill_info(j)

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

            match_score, reason = score(j)

            j.update(

                date_found=now,

                active=True,

                required_experience=(
                    required_experience
                    if required_experience
                    is not None
                    else ""
                ),

                degree_requirement=(
                    degree_requirement
                ),

                required_languages=(
                    required_languages
                ),

                matched_skills=", ".join(
                    matched_skills
                ),

                missing_skills=", ".join(
                    missing_skills
                ),

                match_score=match_score,

                match_reason=reason,

                hard_filter_status=status,

                hard_filter_reason="",
            )

            accepted.append(j)

            source_accepted += 1

            print(
                "  ACCEPT:",
                j["title"],
                f"-> score {match_score}",
            )

        print(
            "  real target vacancies:",
            len(jobs),
        )

        print(
            f"  accepted: "
            f"{source_accepted}"
            f" | rejected: "
            f"{source_rejected}"
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
