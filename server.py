#!/usr/bin/env python3
"""TechnoScribe Lead Radar — local-first, standard-library-only server."""
import csv, io, json, os, re, sqlite3, urllib.parse, urllib.request, xml.etree.ElementTree as ET
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DB=ROOT/"lead_radar.sqlite3"
FIT=["product marketing","technical writer","developer docs","gtm","cybersecurity","saas","developer marketing","content engineering","competitive"]
SIGNALS=["looking for","seeking","freelancer","freelance","fractional","contract","hiring","need help"]
INDIA=["india","bengaluru","bangalore","mumbai","delhi","hyderabad","pune","chennai","gurugram","gurgaon","noida","kolkata","ahmedabad"]
CITIES={"all":'(Israel OR "Tel Aviv" OR Herzliya OR Jerusalem OR Haifa)',"tel-aviv":'("Tel Aviv" OR "Ramat Gan" OR Holon OR "Petah Tikva")',"herzliya":'(Herzliya OR "Ra\'anana" OR "Kfar Saba")',"jerusalem":'Jerusalem',"haifa":'(Haifa OR Yokneam)',"beer-sheva":'("Beer Sheva" OR Negev)'}
REGIONS={"israel":CITIES["all"],"europe":'(Europe OR UK OR Germany OR Netherlands)',"north-america":'(USA OR Canada)',"all":"","unknown":""}
def connect():
 c=sqlite3.connect(DB);c.row_factory=sqlite3.Row
 c.execute("CREATE TABLE IF NOT EXISTS leads(id INTEGER PRIMARY KEY,url TEXT UNIQUE NOT NULL,title TEXT DEFAULT '',snippet TEXT DEFAULT '',company TEXT DEFAULT '',person TEXT DEFAULT '',location TEXT DEFAULT '',posted TEXT DEFAULT '',source TEXT DEFAULT '',connection TEXT DEFAULT 'unknown',status TEXT DEFAULT 'new',notes TEXT DEFAULT '',score INTEGER DEFAULT 0,created TEXT DEFAULT CURRENT_TIMESTAMP)")
 c.execute("CREATE TABLE IF NOT EXISTS contacts(profile TEXT PRIMARY KEY, first TEXT, last TEXT, company TEXT)")
 c.commit();return c
def excluded(location):
 s=(location or "").casefold()
 return any(re.search(r"(?<!\w)"+re.escape(term)+r"(?!\w)",s) for term in INDIA)
def score(d):
 s=(" ".join([d.get("title",""),d.get("snippet","")])).lower()
 v=min(100,sum(7 for p in FIT if p in s)+sum(6 for p in SIGNALS if p in s)+(18 if "freelance" in s or "fractional" in s else 0)+(12 if d.get("connection")=="1st" else 0))
 return 0 if excluded(d.get("location","")) else v
def matched(c,person):
 words=(person or "").strip().casefold().split()
 if len(words)<2:return False
 return c.execute("SELECT 1 FROM contacts WHERE lower(first)=? AND lower(last)=? LIMIT 1",(words[0],words[-1])).fetchone() is not None
def parse_contacts(raw):
 lines=raw.lstrip("\ufeff").splitlines()
 offset=None
 for i,line in enumerate(lines[:40]):
  try: cols=[v.strip().lstrip("\ufeff").casefold().replace("_"," ") for v in next(csv.reader([line]))]
  except csv.Error:continue
  if any(v in cols for v in ("first name","firstname")) and any(v in cols for v in ("last name","lastname")):offset=i;break
 if offset is None:raise ValueError("No LinkedIn First Name / Last Name header found. Choose the actual Connections.csv, not an archive ZIP.")
 rows=csv.DictReader(io.StringIO("\n".join(lines[offset:])))
 contacts=[];skipped=0
 for row in rows:
  d={str(k).strip().lstrip("\ufeff").casefold().replace("_"," "):(v or "").strip() for k,v in row.items() if k is not None}
  first=d.get("first name") or d.get("firstname") or ""
  last=d.get("last name") or d.get("lastname") or ""
  if not first or not last:skipped+=1;continue
  profile=d.get("url") or d.get("profile url") or d.get("profile") or "name:"+first.casefold()+" "+last.casefold()
  contacts.append((profile,first,last,d.get("company","")))
 if not contacts:raise ValueError("Header found, but no contacts with both first and last names.")
 return contacts,skipped
def query(q,region="israel",city="all"):
 region=region if region in REGIONS else "israel"
 loc=CITIES.get(city,CITIES["all"]) if region=="israel" else REGIONS[region]
 return " ".join(x for x in ('site:linkedin.com/posts/ ('+q+') (freelance OR fractional OR contract OR hiring)',loc) if x)
def search_links(q,days,region,city):
 term=query(q,region,city)
 return [{"name":"Google","url":"https://www.google.com/search?"+urllib.parse.urlencode({"q":term,"tbs":"qdr:d"+str(days)})},{"name":"Bing","url":"https://www.bing.com/search?"+urllib.parse.urlencode({"q":term})},{"name":"Brave","url":"https://search.brave.com/search?"+urllib.parse.urlencode({"q":term})}]
class Handler(BaseHTTPRequestHandler):
 def send_json(self,d,status=200):
  raw=json.dumps(d,ensure_ascii=False).encode()
  self.send_response(status);self.send_header("Content-Type","application/json; charset=utf-8");self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
 def read_json(self):
  length=int(self.headers.get("Content-Length",0))
  if length>15_000_000:raise ValueError("File too large (15 MB limit)")
  return json.loads(self.rfile.read(length).decode("utf-8"))
 def do_GET(self):
  parts=urllib.parse.urlsplit(self.path);q=urllib.parse.parse_qs(parts.query)
  if parts.path in ("/","/index.html"):
   raw=(ROOT/"index.html").read_bytes();self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw);return
  if parts.path=="/api/leads":
   c=connect();r=[dict(v) for v in c.execute("SELECT * FROM leads ORDER BY score DESC,id DESC")];c.close();return self.send_json({"leads":r})
  if parts.path=="/api/search-links":return self.send_json({"links":search_links(q.get("q",["fractional product marketing"])[0][:200],q.get("days",["14"])[0],q.get("region",["israel"])[0],q.get("city",["all"])[0])})
  if parts.path=="/api/export":
   c=connect();rows=[dict(v) for v in c.execute("SELECT * FROM leads")];c.close()
   out=io.StringIO();cols=["company","person","title","url","source","location","connection","posted","status","score","snippet","notes"]
   w=csv.DictWriter(out,fieldnames=cols,extrasaction="ignore");w.writeheader();w.writerows(rows)
   data=out.getvalue().encode("utf-8-sig");self.send_response(200);self.send_header("Content-Type","text/csv");self.send_header("Content-Disposition",'attachment; filename="lead-radar.csv"');self.end_headers();self.wfile.write(data);return
  self.send_json({"error":"Not found"},404)
 def do_POST(self):
  c=None
  try:
   data=self.read_json();p=urllib.parse.urlsplit(self.path).path;c=connect()
   if p=="/api/import-contacts":
    contacts,skipped=parse_contacts(data.get("csv",""));count=0
    for row in contacts:
     c.execute("INSERT INTO contacts(profile,first,last,company) VALUES(?,?,?,?) ON CONFLICT(profile) DO UPDATE SET first=excluded.first,last=excluded.last,company=excluded.company",row);count+=1
    found=0
    for lead in c.execute("SELECT * FROM leads").fetchall():
     d=dict(lead)
     if matched(c,d["person"]) and d["connection"]!="1st":
      d["connection"]="1st";c.execute("UPDATE leads SET connection=?,score=? WHERE id=?",("1st",score(d),d["id"]));found+=1
    c.commit();return self.send_json({"imported":count,"skipped":skipped,"matched":found,"total":c.execute("SELECT COUNT(*) FROM contacts").fetchone()[0]})
   if p=="/api/lead":
    url=str(data.get("url","")).strip()
    if not url.startswith(("https://","http://")):raise ValueError("A valid source URL is required.")
    keys=["url","title","snippet","company","person","location","posted","source","connection","status","notes"]
    d={k:str(data.get(k,"") or "")[:3000] for k in keys}
    if excluded(d["location"]):raise ValueError("India-based posters excluded.")
    if not d["connection"]:d["connection"]="unknown"
    if not d["status"]:d["status"]="new"
    if d["connection"]=="unknown" and matched(c,d["person"]):d["connection"]="1st"
    d["score"]=score(d)
    c.execute("""INSERT INTO leads(url,title,snippet,company,person,location,posted,source,connection,status,notes,score) VALUES (:url,:title,:snippet,:company,:person,:location,:posted,:source,:connection,:status,:notes,:score) ON CONFLICT(url) DO UPDATE SET title=excluded.title,snippet=excluded.snippet,company=excluded.company,person=excluded.person,location=excluded.location,posted=excluded.posted,source=excluded.source,connection=excluded.connection,status=excluded.status,notes=excluded.notes,score=excluded.score""",d)
    c.commit();return self.send_json({"ok":True})
   if p=="/api/remove":c.execute("DELETE FROM leads WHERE id=?",(int(data["id"]),));c.commit();return self.send_json({"ok":True})
   if p=="/api/discover":
    provider=data.get("provider","bing");q=query(str(data.get("query",""))[:200],data.get("region","israel"),data.get("city","all"))
    if provider=="brave":
     key=os.environ.get("BRAVE_API_KEY")
     if not key:raise ValueError("Set BRAVE_API_KEY to use live Brave discovery.")
     request=urllib.request.Request("https://api.search.brave.com/res/v1/web/search?"+urllib.parse.urlencode({"q":q,"count":20}),headers={"Accept":"application/json","X-Subscription-Token":key})
     with urllib.request.urlopen(request,timeout=15) as response:records=json.load(response).get("web",{}).get("results",[])
     found=[{"title":x.get("title",""),"snippet":x.get("description",""),"url":x.get("url",""),"source":"Brave API"} for x in records]
    else:
     request=urllib.request.Request("https://www.bing.com/search?"+urllib.parse.urlencode({"q":q,"format":"rss"}),headers={"User-Agent":"Mozilla/5.0"})
     with urllib.request.urlopen(request,timeout=12) as response:root=ET.fromstring(response.read(500000))
     found=[{"title":x.findtext("title",""),"snippet":x.findtext("description",""),"url":x.findtext("link",""),"source":"Bing RSS"} for x in root.findall(".//item")]
    found=[x for x in found if "linkedin.com" in x["url"]];return self.send_json({"count":len(found),"results":found})
   raise ValueError("Unknown endpoint")
  except Exception as ex:self.send_json({"error":str(ex)},400)
  finally:
   if c:c.close()
if __name__=="__main__":
 connect().close()
 print("Lead Radar — http://127.0.0.1:8765",flush=True)
 ThreadingHTTPServer(("127.0.0.1",8765),Handler).serve_forever()
