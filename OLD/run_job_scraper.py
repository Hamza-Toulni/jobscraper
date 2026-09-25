# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
import re
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, urldefrag

import pandas as pd
import requests
from bs4 import BeautifulSoup

OUTPUT = "job_market_matches.csv"
TIMEOUT = 25

SOURCES = [
    {"company": "Cegeka", "url": "https://jobs.cegeka.com/en/vacancies", "domain": "jobs.cegeka.com"},
    {"company": "Capgemini", "url": "https://www.capgemini.com/be-en/careers/", "domain": "capgemini.com"},
    {"company": "Akkodis", "url": "https://www.akkodis.com/en-be", "domain": "akkodis.com"},
    {"company": "Pauwels Consulting", "url": "https://www.pauwelsconsulting.com/en/jobs/", "domain": "pauwelsconsulting.com"},
    {"company": "Smals", "url": "https://www.smals.be/en/jobs", "domain": "smals.be"},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/149 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9,nl;q=0.8,fr;q=0.7",
}
session = requests.Session()
session.headers.update(HEADERS)

COLUMNS = [
    "title", "company", "location", "region", "salary", "employment_type",
    "url", "description", "source", "date_found", "active",
    "match_score", "match_reason"
]

POSITIVE_TERMS = [
    "data analyst", "data analytics", "business intelligence", "bi analyst",
    "bi developer", "power bi", "hr analytics", "people analytics",
    "workforce analytics", "hr data", "hris", "data governance",
    "data quality", "reporting analyst", "data consultant",
    "analytics consultant", "business analyst"
]

FINANCE_TERMS = [
    "investment banking", "financial analyst", "finance analyst",
    "financial controller", "accounting analyst", "treasury"
]

JOB_LINK_RE = re.compile(
    r"(job|jobs|career|vacanc|position|opportunit|analyst|analytics|"
    r"business-intelligence|consult|developer|data-governance|power-bi|hr-)",
    re.I,
)


def clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalise_url(value, base):
    value = urljoin(base, value)
    value, _ = urldefrag(value)
    return value.rstrip("/")


def same_domain(url, domain):
    host = urlparse(url).netloc.lower().split(":")[0]
    domain = domain.lower()
    return host == domain or host.endswith("." + domain)


def fetch(url):
    response = session.get(url, timeout=TIMEOUT, allow_redirects=True)
    response.raise_for_status()
    ctype = response.headers.get("content-type", "").lower()
    if "html" not in ctype:
        return ""
    return response.text


def iter_jsonld(soup):
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or script.get_text()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except Exception:
            continue

        objects = obj if isinstance(obj, list) else [obj]
        for item in objects:
            if not isinstance(item, dict):
                continue
            graph = item.get("@graph")
            if isinstance(graph, list):
                yield from graph
            else:
                yield item


def parse_location(job):
    locations = job.get("jobLocation")
    if not locations:
        return ""
    if not isinstance(locations, list):
        locations = [locations]

    results = []
    for loc in locations:
        if not isinstance(loc, dict):
            continue
        address = loc.get("address", {})
        if isinstance(address, str):
            results.append(clean(address))
        elif isinstance(address, dict):
            parts = [
                address.get("postalCode"), address.get("addressLocality"),
                address.get("addressRegion"), address.get("addressCountry")
            ]
            value = ", ".join(clean(x) for x in parts if x)
            if value:
                results.append(value)
    return " / ".join(dict.fromkeys(results))


def parse_jsonld_jobs(soup, source):
    jobs = []
    for obj in iter_jsonld(soup):
        types = obj.get("@type", [])
        if not isinstance(types, list):
            types = [types]
        if "JobPosting" not in types:
            continue

        title = clean(obj.get("title"))
        if not title:
            continue

        org = obj.get("hiringOrganization", {})
        company = clean(org.get("name")) if isinstance(org, dict) else ""
        raw_description = obj.get("description", "")
        description = clean(BeautifulSoup(str(raw_description), "html.parser").get_text(" "))

        employment = obj.get("employmentType", "")
        if isinstance(employment, list):
            employment = ", ".join(map(str, employment))

        jobs.append({
            "title": title,
            "company": company or source["company"],
            "location": parse_location(obj),
            "region": "",
            "salary": "",  # Never invent salary.
            "employment_type": clean(employment),
            "url": normalise_url(obj.get("url") or source["url"], source["url"]),
            "description": description,
            "source": source["company"].lower().replace(" ", "_") + "_web",
        })
    return jobs


def discover_links(soup, source):
    result = []
    home = normalise_url(source["url"], source["url"])

    for a in soup.find_all("a", href=True):
        text = clean(a.get_text(" ", strip=True))
        url = normalise_url(a["href"], source["url"])
        if not same_domain(url, source["domain"]) or url == home:
            continue
        if JOB_LINK_RE.search(text) or JOB_LINK_RE.search(url):
            result.append(url)

    return list(dict.fromkeys(result))


def parse_fallback_detail(html, url, company):
    soup = BeautifulSoup(html, "html.parser")
    h1 = soup.find("h1")
    title = clean(h1.get_text(" ", strip=True)) if h1 else ""

    if not title:
        return None

    description = ""
    for selector in [
        '[class*="job-description"]', '[class*="jobdescription"]',
        '[class*="description"]', '[id*="description"]',
        '[class*="job-detail"]', "main"
    ]:
        node = soup.select_one(selector)
        if node:
            candidate = clean(node.get_text(" ", strip=True))
            if len(candidate) >= 150:
                description = candidate
                break

    if len(description) < 150:
        return None

    return {
        "title": title,
        "company": company,
        "location": "",
        "region": "",
        "salary": "",
        "employment_type": "",
        "url": url,
        "description": description,
        "source": company.lower().replace(" ", "_") + "_web",
    }


def relevant(job):
    text = clean(
        f"{job.get('title','')} {job.get('description','')} {job.get('location','')}"
    ).lower()

    if any(x in text for x in ["internship", "intern ", "traineeship"]):
        return False, "Internship/traineeship"
    if any(x in text for x in FINANCE_TERMS):
        return False, "Finance-focused"
    if not any(x in text for x in POSITIVE_TERMS):
        return False, "Outside target job families"
    return True, ""


def scrape(source, verbose=False, max_pages=35):
    landing_html = fetch(source["url"])
    landing_soup = BeautifulSoup(landing_html, "html.parser")

    jobs = parse_jsonld_jobs(landing_soup, source)
    links = discover_links(landing_soup, source)

    if verbose:
        print(f"  Candidate links: {len(links)}")

    for url in links[:max_pages]:
        try:
            html = fetch(url)
            soup = BeautifulSoup(html, "html.parser")
            structured = parse_jsonld_jobs(soup, source)

            if structured:
                jobs.extend(structured)
            else:
                fallback = parse_fallback_detail(html, url, source["company"])
                if fallback:
                    jobs.append(fallback)

        except Exception as exc:
            if verbose:
                print(f"  Detail skipped: {url} -> {exc}")

        time.sleep(0.1)

    unique = {}
    for job in jobs:
        job["url"] = normalise_url(job["url"], source["url"])
        unique[job["url"]] = job
    return list(unique.values())


def run(verbose=False):
    now = datetime.now(timezone.utc).isoformat()
    kept = []

    for source in SOURCES:
        print(f"Scraping {source['company']}...")
        try:
            candidates = scrape(source, verbose=verbose)
            accepted = 0

            for job in candidates:
                ok, reason = relevant(job)
                if not ok:
                    continue

                job.update({
                    "date_found": now,
                    "active": True,
                    "match_score": "",
                    "match_reason": "",
                })
                kept.append(job)
                accepted += 1

            print(f"  Candidates: {len(candidates)} | Relevant: {accepted}")

        except Exception as exc:
            # A broken/blocked source must not create fake data.
            print(f"  SOURCE ERROR: {exc}")

    new_df = pd.DataFrame(kept, columns=COLUMNS)

    # V2 intentionally rebuilds the live result set each run.
    # This prevents V1's fake/sample rows from surviving forever.
    if new_df.empty:
        print("\nWARNING: No relevant real vacancies were extracted.")
        print("Existing CSV was NOT overwritten, to avoid destroying useful data.")
        return

    new_df.drop_duplicates(subset=["url"], keep="last", inplace=True)
    new_df.sort_values(["company", "title"], inplace=True)
    new_df.to_csv(OUTPUT, index=False)

    print(f"\nSaved {len(new_df)} real matched vacancies to {OUTPUT}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()
    run(args.verbose)
