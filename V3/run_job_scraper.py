# -*- coding: utf-8 -*-
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse, urldefrag
import json,re,time
import pandas as pd
import requests
from bs4 import BeautifulSoup

OUTPUT="job_market_matches.csv"
SOURCES=[
 {"company":"Cegeka","url":"https://jobs.cegeka.com/en/vacancies","domain":"jobs.cegeka.com"},
 {"company":"Capgemini","url":"https://www.capgemini.com/be-en/careers/","domain":"capgemini.com"},
 {"company":"Akkodis","url":"https://www.akkodis.com/en-be","domain":"akkodis.com"},
 {"company":"Pauwels Consulting","url":"https://www.pauwelsconsulting.com/en/jobs/","domain":"pauwelsconsulting.com"},
 {"company":"Smals","url":"https://www.smals.be/en/jobs","domain":"smals.be"}]
FAMILIES={
 "HR Data / People Analytics":["hr data analyst","hr analytics","people analytics","workforce analytics","hris analyst","hr reporting"],
 "Data Analyst":["data analyst","data analytics analyst","analytics analyst"],
 "BI / Power BI":["bi analyst","bi developer","business intelligence analyst","business intelligence developer","power bi analyst","power bi developer"],
 "Data Governance / Quality":["data governance","data quality analyst","data quality specialist","data steward"],
 "Reporting":["reporting analyst","reporting developer","reporting specialist"],
 "Data / Analytics Consulting":["data consultant","analytics consultant","bi consultant"],
 "Functional / Business Data Analysis":["functional analyst – data","functional analyst - data","functional analyst data","business analyst – data","business analyst - data","business data analyst"]}
STRETCH=["data engineer","etl developer","etl engineer","data warehouse developer"]
SKILLS={"sql":12,"power bi":12,"etl":10,"data warehouse":9,"data quality":8,"data governance":8,"python":5,"cognos":4,"wherescape":5,"reporting":5,"hr analytics":7,"people analytics":7}
HEADERS={"User-Agent":"Mozilla/5.0 AppleWebKit/537.36 Chrome/149 Safari/537.36","Accept-Language":"en-US,en;q=0.9,nl;q=0.8,fr;q=0.7"}
S=requests.Session(); S.headers.update(HEADERS)

def clean(x): return re.sub(r"\s+"," ",str(x or "")).strip()
def norm(u,b):
 u=urljoin(b,u); u,_=urldefrag(u); return u.rstrip("/")
def same(u,d):
 h=urlparse(u).netloc.lower(); return h==d or h.endswith("."+d)
def fetch(u):
 r=S.get(u,timeout=25,allow_redirects=True); r.raise_for_status()
 return r.text if "html" in r.headers.get("content-type","").lower() else ""
def family(t):
 x=clean(t).lower()
 for f,terms in FAMILIES.items():
  if any(k in x for k in terms): return f
 if any(k in x for k in STRETCH): return "Data Engineering (stretch)"
 return ""
def job_url(u):
 p=urlparse(u).path.lower()
 return bool(re.search(r"/job/|/jobs/[^/]+|/vacanc(?:y|ies)/[^/]+|/job-search/[^/]+",p))
def jsonlds(soup):
 for s in soup.find_all("script",type="application/ld+json"):
  try: x=json.loads(s.string or s.get_text())
  except: continue
  for a in (x if isinstance(x,list) else [x]):
   if isinstance(a,dict):
    for b in (a.get("@graph") if isinstance(a.get("@graph"),list) else [a]):
     if isinstance(b,dict): yield b
def location(o):
 ls=o.get("jobLocation") or []; ls=ls if isinstance(ls,list) else [ls]; out=[]
 for l in ls:
  if not isinstance(l,dict): continue
  a=l.get("address",{})
  if isinstance(a,dict):
   v=", ".join(clean(a.get(k)) for k in ["postalCode","addressLocality","addressRegion","addressCountry"] if a.get(k))
   if v: out.append(v)
 return " / ".join(dict.fromkeys(out))
def structured(html,src,url):
 soup=BeautifulSoup(html,"html.parser"); out=[]
 for o in jsonlds(soup):
  typ=o.get("@type",[]); typ=typ if isinstance(typ,list) else [typ]
  if "JobPosting" not in typ: continue
  title=clean(o.get("title")); fam=family(title)
  if not fam: continue
  desc=clean(BeautifulSoup(str(o.get("description","")),"html.parser").get_text(" "))
  emp=o.get("employmentType",""); emp=", ".join(emp) if isinstance(emp,list) else clean(emp)
  ju=norm(o.get("url") or url,src["url"])
  out.append({"title":title,"job_family":fam,"company":src["company"],"location":location(o),"region":"","salary":"","employment_type":emp,"url":ju,"description":desc,"source":src["company"].lower().replace(" ","_")+"_web"})
 return out
def links(html,src):
 soup=BeautifulSoup(html,"html.parser"); details=[]; pages=[]
 for a in soup.find_all("a",href=True):
  u=norm(a["href"],src["url"]); txt=clean(a.get_text(" ",strip=True))
  if not same(u,src["domain"]): continue
  if family(txt) and job_url(u): details.append(u)
  href=a["href"].lower()
  if re.search(r"[?&]page=\d+",href): pages.append(u)
 return list(dict.fromkeys(details)),list(dict.fromkeys(pages))
def fallback(html,u,src):
 if not job_url(u): return None
 soup=BeautifulSoup(html,"html.parser"); h=soup.find("h1")
 title=clean(h.get_text(" ",strip=True)) if h else ""; fam=family(title)
 if not fam:return None
 main=soup.find("main"); desc=clean(main.get_text(" ",strip=True)) if main else ""
 if len(desc)<200:return None
 return {"title":title,"job_family":fam,"company":src["company"],"location":"","region":"","salary":"","employment_type":"","url":u,"description":desc,"source":src["company"].lower().replace(" ","_")+"_web"}
def hard(j):
 t=(j["title"]+" "+j["description"]).lower()
 if any(x in t for x in ["internship","traineeship","intern "]): return False,"internship"
 if any(x in j["title"].lower() for x in ["financial analyst","finance analyst","financial controller","treasury analyst"]): return False,"finance"
 equivalent=bool(re.search(r"or equivalent|equivalent experience|equivalent qualification",t))
 if re.search(r"master'?s degree|master degree|master diploma",t) and not equivalent:return False,"mandatory Master's"
 if re.search(r"(degree|bachelor|master).{0,60}(computer science|engineering|informatics|information technology|data science|mathematics|statistics)",t) and not equivalent:return False,"mandatory specific technical degree"
 return True,"passed"
def score(j):
 text=(j["title"]+" "+j["description"]).lower(); s=40; why=[j["job_family"]]
 if j["job_family"]=="HR Data / People Analytics":s+=20
 elif j["job_family"] in ["Data Analyst","BI / Power BI","Data Governance / Quality"]:s+=15
 elif j["job_family"]=="Data Engineering (stretch)":s-=5
 else:s+=8
 found=[]
 for k,p in SKILLS.items():
  if k in text:s+=p;found.append(k)
 if found:why.append("skills: "+", ".join(found[:6]))
 if "senior" in j["title"].lower():s-=5;why.append("senior")
 return max(0,min(100,s)),"; ".join(why)
def scrape(src):
 queue=[src["url"]]; seen=set(); detail=[]
 while queue and len(seen)<12:
  u=queue.pop(0)
  if u in seen:continue
  seen.add(u)
  try:h=fetch(u)
  except Exception as e: print("  listing skipped:",e);continue
  d,p=links(h,src);detail+=d
  for x in p:
   if x not in seen and x not in queue:queue.append(x)
  for j in structured(h,src,u):
   if job_url(j["url"]):detail.append(j["url"])
  time.sleep(.1)
 detail=list(dict.fromkeys(detail))[:80]
 print(f"  listing pages: {len(seen)} | target links: {len(detail)}")
 out=[]
 for u in detail:
  try:
   h=fetch(u); js=structured(h,src,u)
   if js:out+=js
   else:
    j=fallback(h,u,src)
    if j:out.append(j)
  except Exception as e: print("  detail skipped:",e)
  time.sleep(.1)
 return list({j["url"]:j for j in out if family(j["title"]) and job_url(j["url"])}.values())
def run():
 now=datetime.now(timezone.utc).isoformat(); accepted=[]; rejected=0
 for src in SOURCES:
  print("\nScraping",src["company"])
  try:jobs=scrape(src)
  except Exception as e:print("  SOURCE ERROR:",e);continue
  for j in jobs:
   ok,status=hard(j)
   if not ok: print("  REJECT:",j["title"],"->",status);rejected+=1;continue
   sc,why=score(j);j.update(date_found=now,active=True,match_score=sc,match_reason=why,hard_filter_status=status);accepted.append(j)
  print("  real target vacancies:",len(jobs))
 cols=["title","job_family","company","location","region","salary","employment_type","url","description","source","date_found","active","match_score","match_reason","hard_filter_status"]
 df=pd.DataFrame(accepted,columns=cols)
 print(f"\nAccepted: {len(df)} | Rejected: {rejected}")
 if df.empty:
  print("No verified matches. Existing CSV left unchanged.");return
 df.drop_duplicates("url",keep="last",inplace=True);df.sort_values("match_score",ascending=False,inplace=True);df.to_csv(OUTPUT,index=False)
 print("Saved",len(df),"verified targeted jobs to",OUTPUT)
if __name__=="__main__":run()
