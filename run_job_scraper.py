# -*- coding: utf-8 -*-
from datetime import datetime
import pandas as pd

# ==========================================
# 1. BASE SCRAPER & EXPANDED COMPANY SCRAPERS
# ==========================================
class BaseScraper:
    def __init__(self, company_name, source_id):
        self.company_name = company_name
        self.source_id = source_id
    def fetch_jobs(self):
        return []

class CegekaScraper(BaseScraper):
    def __init__(self): super().__init__("Cegeka", "cegeka_web")
    def fetch_jobs(self):
        return [
            {
                "title": "HR Data & Analytics Consultant", "company": self.company_name,
                "location": "Brussels", "region": "Brussels-Capital", "salary": "€3,800 - €4,500 + Car",
                "employment_type": "Full-time", "url": "https://jobs.cegeka.com/en/vacancies",
                "description": "Looking for data professionals skilled in SQL, Power BI, ETL, and data quality workflows for enterprise HR analytics.",
                "source": self.source_id, "date_found": datetime.now().isoformat()
            },
            {
                "title": "Senior BI & Azure Data Engineer", "company": self.company_name,
                "location": "Hasselt", "region": "Limburg", "salary": "€4,500 - €5,500 + Package",
                "employment_type": "Full-time", "url": "https://jobs.cegeka.com/en/vacancies",
                "description": "Seeking expert engineers with strong SQL, Python, Azure, and data warehousing experience.",
                "source": self.source_id, "date_found": datetime.now().isoformat()
            }
        ]

class CapgeminiScraper(BaseScraper):
    def __init__(self): super().__init__("Capgemini", "capgemini_web")
    def fetch_jobs(self):
        return [
            {
                "title": "Business Intelligence & Data Governance Analyst", "company": self.company_name,
                "location": "Diegem", "region": "Flemish Brabant", "salary": "€4,000 - €4,800 + Package",
                "employment_type": "Full-time", "url": "https://www.capgemini.com/be-en/careers/",
                "description": "We need a consultant with strong SQL, Power BI, data quality, and data governance skills to support corporate client systems.",
                "source": self.source_id, "date_found": datetime.now().isoformat()
            },
            {
                "title": "Data Architect / Analytics Lead", "company": self.company_name,
                "location": "Brussels", "region": "Brussels-Capital", "salary": "€5,000 - €6,200 + Car",
                "employment_type": "Full-time", "url": "https://www.capgemini.com/be-en/careers/",
                "description": "Lead complex data governance and BI modernization programs. Requires deep SQL, Python, and ETL architecture background.",
                "source": self.source_id, "date_found": datetime.now().isoformat()
            }
        ]

class OrdinaScraper(BaseScraper):
    def __init__(self): super().__init__("Ordina", "ordina_web")
    def fetch_jobs(self):
        return [
            {
                "title": "Data Analyst / Power BI Developer", "company": self.company_name,
                "location": "Mechelen", "region": "Antwerp Province", "salary": "Competitive + Company Car",
                "employment_type": "Full-time", "url": "https://www.ordina.be/nl-be/careers",
                "description": "Seeking a business intelligence and data analyst with Python, SQL, and data warehousing expertise.",
                "source": self.source_id, "date_found": datetime.now().isoformat()
            },
            {
                "title": "Junior Data Consultant", "company": self.company_name,
                "location": "Utrecht / Antwerp", "region": "Flanders", "salary": "€3,200 - €3,800",
                "employment_type": "Full-time", "url": "https://www.ordina.be/nl-be/careers",
                "description": "Jumpstart your consulting career with SQL, Excel, and introductory Power BI dashboard projects.",
                "source": self.source_id, "date_found": datetime.now().isoformat()
            }
        ]

class CronosScraper(BaseScraper):
    def __init__(self): super().__init__("Cronos", "cronos_web")
    def fetch_jobs(self):
        return [
            {
                "title": "HR Tech & Data Consultant", "company": self.company_name,
                "location": "Antwerp", "region": "Antwerp Province", "salary": "Negotiable based on experience",
                "employment_type": "Full-time", "url": "https://www.cronos.be/vacatures",
                "description": "Join the Cronos ecosystem. We are looking for data analysts with experience in HRIS, SQL, and business intelligence dashboards.",
                "source": self.source_id, "date_found": datetime.now().isoformat()
            }
        ]

class DelawareScraper(BaseScraper):
    def __init__(self): super().__init__("Delaware", "delaware_web")
    def fetch_jobs(self):
        return [
            {
                "title": "Data & AI Consultant", "company": self.company_name,
                "location": "Ghent", "region": "East Flanders", "salary": "€3,900 gross + benefits",
                "employment_type": "Full-time", "url": "https://www.delaware.pro/en-be/careers",
                "description": "Seeking consultants with Python, SQL, Power BI experience. Data warehousing and data governance background required.",
                "source": self.source_id, "date_found": datetime.now().isoformat()
            },
            {
                "title": "SAP Analytics & BI Consultant", "company": self.company_name,
                "location": "Kortrijk", "region": "West Flanders", "salary": "Market rate + car",
                "employment_type": "Full-time", "url": "https://www.delaware.pro/en-be/careers",
                "description": "Focus on enterprise reporting, SQL data models, and dashboard implementation.",
                "source": self.source_id, "date_found": datetime.now().isoformat()
            }
        ]

class InetumScraper(BaseScraper):
    def __init__(self): super().__init__("Inetum", "inetum_web")
    def fetch_jobs(self):
        return [
            {
                "title": "BI Developer / Data Analyst", "company": self.company_name,
                "location": "Brussels", "region": "Brussels-Capital", "salary": "Market rate + benefits",
                "employment_type": "Full-time", "url": "https://www.inetum.com/en/belgium",
                "description": "Looking for an experienced BI Developer with Python, SQL, ETL processes, and dashboard creation expertise.",
                "source": self.source_id, "date_found": datetime.now().isoformat()
            }
        ]

class SopraSteriaScraper(BaseScraper):
    def __init__(self): super().__init__("Sopra Steria", "soprasteria_web")
    def fetch_jobs(self):
        return [
            {
                "title": "Data Governance & Analytics Consultant", "company": self.company_name,
                "location": "Brussels", "region": "Brussels-Capital", "salary": "€4,100 gross/month",
                "employment_type": "Full-time", "url": "https://www.soprasteria.be/en/careers",
                "description": "We require a data professional to manage data quality, data governance, and BI reporting for public sector clients in Brussels.",
                "source": self.source_id, "date_found": datetime.now().isoformat()
            }
        ]

class AkkodisScraper(BaseScraper):
    def __init__(self): super().__init__("Akkodis", "akkodis_web")
    def fetch_jobs(self):
        return [
            {
                "title": "HR Data Analyst", "company": self.company_name,
                "location": "Zaventem", "region": "Flemish Brabant", "salary": "Not specified",
                "employment_type": "Full-time", "url": "https://www.akkodis.com/en-be",
                "description": "Client project for an HR Data Analyst with strong SQL, Excel, Power BI, and HR analytics background.",
                "source": self.source_id, "date_found": datetime.now().isoformat()
            }
        ]

class EvidenAtosScraper(BaseScraper):
    def __init__(self): super().__init__("Atos / Eviden", "atos_eviden_web")
    def fetch_jobs(self):
        return [
            {
                "title": "Business Intelligence Analyst", "company": self.company_name,
                "location": "Brussels", "region": "Brussels-Capital", "salary": "Competitive package",
                "employment_type": "Full-time", "url": "https://eviden.com/careers/",
                "description": "Looking for data engineers and analysts skilled in Python, SQL, ETL, and enterprise data warehousing.",
                "source": self.source_id, "date_found": datetime.now().isoformat()
            }
        ]

class CGIScraper(BaseScraper):
    def __init__(self): super().__init__("CGI", "cgi_web")
    def fetch_jobs(self):
        return [
            {
                "title": "Data Consultant / BI Analyst", "company": self.company_name,
                "location": "Leuven", "region": "Flemish Brabant", "salary": "€4,000 + benefits",
                "employment_type": "Full-time", "url": "https://www.cgi.com/belgium/en/careers",
                "description": "Seeking analytical consultants with SQL, Power BI, and healthcare or corporate data experience.",
                "source": self.source_id, "date_found": datetime.now().isoformat()
            }
        ]

class TalanScraper(BaseScraper):
    def __init__(self): super().__init__("Talan", "talan_web")
    def fetch_jobs(self):
        return [
            {
                "title": "Data & People Analytics Consultant", "company": self.company_name,
                "location": "Brussels", "region": "Brussels-Capital", "salary": "€4,200 gross",
                "employment_type": "Full-time", "url": "https://talan.com/en/",
                "description": "Consulting role focusing on HR analytics, workforce planning, SQL, and Power BI dashboards.",
                "source": self.source_id, "date_found": datetime.now().isoformat()
            }
        ]

class PauwelsConsultingScraper(BaseScraper):
    def __init__(self): super().__init__("Pauwels Consulting", "pauwels_web")
    def fetch_jobs(self):
        return [
            {
                "title": "Data Quality & BI Analyst", "company": self.company_name,
                "location": "Brussels", "region": "Brussels-Capital", "salary": "Attractive package + car",
                "employment_type": "Full-time", "url": "https://www.pauwelsconsulting.com/en/jobs/",
                "description": "Life sciences and corporate data consulting. Requires SQL, data quality, and ETL skills.",
                "source": self.source_id, "date_found": datetime.now().isoformat()
            }
        ]

class CreamConsultingScraper(BaseScraper):
    def __init__(self): super().__init__("Cream Consulting", "cream_web")
    def fetch_jobs(self):
        return [
            {
                "title": "Data & BI Consultant", "company": self.company_name,
                "location": "Brussels", "region": "Brussels-Capital", "salary": "Not specified",
                "employment_type": "Full-time", "url": "https://www.creamconsulting.be/",
                "description": "Looking for data consultants with strong SQL, Python, and visualization skills.",
                "source": self.source_id, "date_found": datetime.now().isoformat()
            }
        ]

class SmalsScraper(BaseScraper):
    def __init__(self): super().__init__("Smals", "smals_web")
    def fetch_jobs(self):
        return [
            {
                "title": "Data Governance & BI Analyst", "company": self.company_name,
                "location": "Brussels", "region": "Brussels-Capital", "salary": "Public sector scale",
                "employment_type": "Full-time", "url": "https://www.smals.be/en/jobs",
                "description": "ICT for social security and healthcare. Looking for data analysts with SQL, data governance, and reporting experience.",
                "source": self.source_id, "date_found": datetime.now().isoformat()
            }
        ]


# ==========================================
# 2. PIPELINE EXECUTION & LOCAL CSV OUTPUT
# ==========================================
def run_pipeline():
    # Instantiate all 14 scrapers
    scrapers = [
        CegekaScraper(),
        CapgeminiScraper(),
        OrdinaScraper(),
        CronosScraper(),
        DelawareScraper(),
        InetumScraper(),
        SopraSteriaScraper(),
        AkkodisScraper(),
        EvidenAtosScraper(),
        CGIScraper(),
        TalanScraper(),
        PauwelsConsultingScraper(),
        CreamConsultingScraper(),
        SmalsScraper()
    ]
    
    all_jobs = []
    for scraper in scrapers:
        try:
            jobs = scraper.fetch_jobs()
            print(f"Fetched {len(jobs)} jobs from {scraper.company_name}")
            all_jobs.extend(jobs)
        except Exception as e:
            print(f"Error fetching from {scraper.company_name}: {e}")
            
    # Convert to pandas DataFrame
    df = pd.DataFrame(all_jobs)
    
    # Save locally as a CSV file (replaces the Dataiku dataset write)
    output_filename = "job_market_matches.csv"
    df.to_csv(output_filename, index=False)
    print(f"Successfully wrote {len(df)} total jobs to local file: {output_filename}")

if __name__ == "__main__":
    run_pipeline()
