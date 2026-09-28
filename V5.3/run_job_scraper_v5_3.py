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
