
import json
import os
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.request import Request, urlopen

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_FILE = os.path.join(BASE_DIR, "vacancies.json")

SOURCES = [
    {
        "name": "UPSC",
        "url": "https://upsc.gov.in/recruitment/recruitment-advertisement",
        "keywords": ["recruitment", "advertisement", "vacancy", "application", "examination"]
    },
    {
        "name": "SSC",
        "url": "https://ssc.gov.in/",
        "keywords": ["notice", "recruitment", "examination", "application", "vacancy"]
    },
    {
        "name": "Railway Recruitment Board",
        "url": "https://www.rrbcdg.gov.in/",
        "keywords": ["notice", "recruitment", "vacancy", "notification", "application"]
    },
    {
        "name": "MPSC Maharashtra",
        "url": "https://mpsc.gov.in/",
        "keywords": ["advertisement", "recruitment", "notification", "application", "vacancy"]
    },
    {
        "name": "Maharashtra PWD",
        "url": "https://pwd.maharashtra.gov.in/en/notice-category/recruitments/",
        "keywords": ["recruitment", "junior engineer", "civil engineer", "clerk", "steno", "vacancy", "appointment"]
    },
    {
        "name": "Maharashtra Police Recruitment",
        "url": "https://www.mahapolice.gov.in/police-recru.php",
        "keywords": ["recruitment", "police", "constable", "advertisement", "vacancy", "notification"]
    },
    {
        "name": "India Post Vacancies",
        "url": "https://www.indiapost.gov.in/vacancies",
        "keywords": ["notification", "recruitment", "vacancy", "driver", "artisan", "posts", "engagement"]
    },
    {
        "name": "India Post GDS",
        "url": "https://www.indiapost.gov.in/gdsonlineengagement",
        "keywords": ["notification", "registration", "application", "vacant posts", "gds"]
    },
    {
        "name": "India Post Payments Bank",
        "url": "https://www.ippbonline.com/en/web/ippb/current-openings",
        "keywords": ["recruitment", "advertisement", "opening", "apply", "executive", "vacancy"]
    },
    {
        "name": "IBPS Banking Recruitment",
        "url": "https://www.ibps.in/",
        "keywords": ["recruitment", "notification", "apply", "vacancy", "examination"]
    },
    {
        "name": "National Career Service",
        "url": "https://www.ncs.gov.in/pages/govt-job-vacancies.aspx",
        "keywords": ["job", "vacancy", "recruitment", "department", "ministry"]
    },
    {
        "name": "Maharashtra Government",
        "url": "https://www.maharashtra.gov.in/",
        "keywords": ["recruitment", "bharti", "vacancy", "advertisement", "notification"]
    },
    {
        "name": "Maharashtra Forest Department",
        "url": "https://mahaforest.gov.in/",
        "keywords": ["recruitment", "bharti", "vacancy", "advertisement", "notification"]
    },
    {
        "name": "Maharashtra Water Resources Department",
        "url": "https://wrd.maharashtra.gov.in/",
        "keywords": ["recruitment", "bharti", "vacancy", "advertisement", "notification", "junior engineer"]
    }
]

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "a":
            attrs = dict(attrs)
            href = attrs.get("href", "")
            if href:
                self.current = {"href": href, "text": ""}

    def handle_data(self, data):
        if self.current is not None:
            self.current["text"] += " " + data.strip()

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self.current is not None:
            self.current["text"] = re.sub(
                r"\s+", " ", self.current["text"]
            ).strip()
            self.links.append(self.current)
            self.current = None


def get_page(url):
    request = Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; YojanaMitraAI/1.0)",
            "Accept": "text/html,application/xhtml+xml"
        }
    )

    with urlopen(request, timeout=25) as response:
        content_type = response.headers.get("Content-Type", "").lower()

        if "html" not in content_type:
            return "", response.geturl()

        html = response.read(3_000_000).decode("utf-8", errors="replace")
        return html, response.geturl()


def clean_url(url):
    url, _ = urldefrag(url)
    return url.strip()


def same_host(url_a, url_b):
    host_a = (urlparse(url_a).hostname or "").lower()
    host_b = (urlparse(url_b).hostname or "").lower()

    if host_a.startswith("www."):
        host_a = host_a[4:]
    if host_b.startswith("www."):
        host_b = host_b[4:]

    return bool(host_a and host_a == host_b)


def looks_relevant(text, keywords):
    text = re.sub(r"[^a-z0-9]+", " ", text.lower())
    return any(
        re.sub(r"[^a-z0-9]+", " ", keyword.lower()).strip() in text
        for keyword in keywords
    )


def collect_source(source):
    now = datetime.now(timezone.utc).isoformat()
    results = []

    try:
        html, final_url = get_page(source["url"])
        parser = LinkParser()
        parser.feed(html)

        for link in parser.links:
            title = link["text"]
            url = clean_url(urljoin(final_url, link["href"]))

            if not title or len(title) < 3:
                continue

            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                continue

            # Only collect links hosted on the same official website.
            if not same_host(url, final_url):
                continue

            if url.rstrip("/") == final_url.rstrip("/"):
                continue

            searchable = title + " " + parsed.path.replace("-", " ").replace("_", " ")

            if not looks_relevant(searchable, source["keywords"]):
                continue

            results.append({
                "source": source["name"],
                "title": title[:220],
                "url": url,
                "status": "Official link - verify notice",
                "type": "official_link",
                "checkedAt": now
            })

        print(f'{source["name"]}: found {len(results)} matching links')

    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        print(f'{source["name"]}: fetch failed: {exc}')

    except Exception as exc:
        print(f'{source["name"]}: parsing failed: {exc}')

    # Keep an official portal link if the page yielded no matching links.
    # This is a portal link, NOT proof of an active vacancy.
    if not results:
        results.append({
            "source": source["name"],
            "title": source["name"] + " - Official Recruitment Portal",
            "url": source["url"],
            "status": "Official portal - check for notices",
            "type": "portal",
            "checkedAt": now
        })

    return results


def main():
    all_results = []
    seen = set()

    for source in SOURCES:
        for item in collect_source(source):
            url = item["url"].rstrip("/")

            if url in seen:
                continue

            seen.add(url)
            all_results.append(item)

    data = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "notice": (
            "Official portal links are provided for verification. "
            "A listed link does not guarantee an active vacancy. "
            "Check the official notification for eligibility and deadlines."
        ),
        "vacancies": all_results
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)

    print(f"Saved {len(all_results)} links to vacancies.json")


if __name__ == "__main__":
    main()
