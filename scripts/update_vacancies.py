
import json
import re
from datetime import datetime, timezone
from html.parser import HTMLParser
from urllib.error import URLError, HTTPError
from urllib.request import Request, urlopen
from pathlib import Path

SOURCES = [
    {
        "name": "UPSC",
        "url": "https://upsc.gov.in/recruitment/recruitment-advertisement",
        "keywords": ["recruitment", "advertisement", "vacancy", "application"]
    },
    {
        "name": "SSC",
        "url": "https://ssc.gov.in/",
        "keywords": ["notice", "recruitment", "examination", "application"]
    },
    {
        "name": "Railway Recruitment Board",
        "url": "https://www.rrbcdg.gov.in/",
        "keywords": ["notice", "recruitment", "vacancy", "notification"]
    },
    {
        "name": "MPSC Maharashtra",
        "url": "https://mpsc.gov.in/",
        "keywords": ["advertisement", "recruitment", "notification", "application"]
    },
    {
        "name": "IBPS",
        "url": "https://www.ibps.in/",
        "keywords": ["recruitment", "notification", "apply", "vacancy"]
    },
    {
        "name": "National Career Service",
        "url": "https://www.ncs.gov.in/",
        "keywords": ["job", "vacancy", "recruitment"]
    }
]

class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.current_url = None
        self.current_text = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            attrs = dict(attrs)
            self.current_url = attrs.get("href")
            self.current_text = []

    def handle_data(self, data):
        if self.current_url:
            self.current_text.append(data.strip())

    def handle_endtag(self, tag):
        if tag == "a" and self.current_url:
            text = " ".join(x for x in self.current_text if x)
            if text and self.current_url:
                self.links.append((text, self.current_url))
            self.current_url = None
            self.current_text = []

def get_page(url):
    request = Request(
        url,
        headers={"User-Agent": "YojanaMitraAI/1.0 (public information directory)"}
    )
    with urlopen(request, timeout=20) as response:
        content_type = response.headers.get("Content-Type", "")
        if "html" not in content_type.lower():
            return ""
        return response.read().decode("utf-8", errors="replace")

def absolute_url(base, link):
    from urllib.parse import urljoin, urlparse
    full = urljoin(base, link)
    parsed = urlparse(full)
    if parsed.scheme not in ("http", "https"):
        return None
    return full

def main():
    results = []
    checked_at = datetime.now(timezone.utc).isoformat()

    for source in SOURCES:
        found = 0
        try:
            html = get_page(source["url"])
            parser = LinkParser()
            parser.feed(html)

            for title, raw_url in parser.links:
                title = re.sub(r"\s+", " ", title).strip()
                url = absolute_url(source["url"], raw_url)

                if not url or len(title) < 5:
                    continue

                # Only retain links on the source's official domain.
                from urllib.parse import urlparse
                source_host = urlparse(source["url"]).hostname
                link_host = urlparse(url).hostname
                if not link_host or not (
                    link_host == source_host or
                    link_host.endswith("." + source_host)
                ):
                    continue

                searchable = title.lower()
                if any(word in searchable for word in source["keywords"]):
                    results.append({
                        "source": source["name"],
                        "title": title,
                        "url": url,
                        "status": "Official link - verify notice",
                        "checkedAt": checked_at
                    })
                    found += 1

        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
            print(f"Could not read {source['name']}: {error}")

        # Keep the official recruitment portal available even if scraping fails.
        if found == 0:
            results.append({
                "source": source["name"],
                "title": source["name"] + " Official Recruitment Portal",
                "url": source["url"],
                "status": "Portal link - check for latest notices",
                "checkedAt": checked_at
            })

    # Remove duplicate links.
    unique = {}
    for item in results:
        unique[item["url"]] = item

    output = {
        "updatedAt": checked_at,
        "notice": (
            "Links are collected from official portals where accessible. "
            "This does not confirm that a vacancy is open or that its deadline "
            "is current. Verify every notice on the official website."
        ),
        "vacancies": list(unique.values())
    }

    Path("vacancies.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"Created vacancies.json with {len(output['vacancies'])} links.")

if __name__ == "__main__":
    main()
