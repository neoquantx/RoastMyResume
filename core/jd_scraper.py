"""
jd_scraper.py
Scrapes job descriptions from URLs OR accepts raw paste.
Runs locally — no 3rd-party JD parsing API.
"""

import requests
from bs4 import BeautifulSoup
import re


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Common JD content selectors per job site
SITE_SELECTORS = {
    "linkedin.com": [".description__text", ".job-description"],
    "indeed.com": ["#jobDescriptionText", ".jobsearch-jobDescriptionText"],
    "naukri.com": [".job-desc", ".dang-inner-html", ".styles_job-desc-container"],
    "internshala.com": [".internship_details", ".about_company"],
    "glassdoor.com": [".jobDescriptionContent", "[data-test='description']"],
    "wellfound.com": [".job-description", ".styles_description"],
    "unstop.com": [".description", ".opportunity-detail"],
}


def scrape_jd_from_url(url: str) -> str:
    """
    Attempt to scrape job description from a URL.
    Falls back to generic body text extraction if site-specific selector fails.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Try site-specific selectors first
        for site, selectors in SITE_SELECTORS.items():
            if site in url:
                for sel in selectors:
                    el = soup.select_one(sel)
                    if el:
                        return clean_text(el.get_text())

        # Generic fallback: grab largest text block
        candidates = soup.find_all(["div", "section", "article", "main"])
        best = max(candidates, key=lambda t: len(t.get_text()), default=None)
        if best:
            return clean_text(best.get_text())

        return clean_text(soup.body.get_text() if soup.body else "")

    except Exception as e:
        return f"[Error scraping URL: {str(e)}. Please paste the JD text directly.]"


def parse_jd_text(text: str) -> dict:
    """
    Extract structured info from raw JD text.
    Returns role, company, required skills, experience, and full text.
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    # Heuristically detect key sections
    skills_keywords = []
    experience_req = ""
    role_title = lines[0] if lines else "Unknown Role"

    skill_section_started = False
    for line in lines:
        lower = line.lower()
        if any(k in lower for k in ["skill", "requirement", "qualification", "must have", "you will need"]):
            skill_section_started = True
        if skill_section_started and len(line) < 100:
            skills_keywords.append(line)
        if re.search(r"\d+[\+\-]?\s*(year|yr)", lower):
            experience_req = line

    return {
        "full_text": text,
        "role_title": role_title,
        "required_skills": skills_keywords[:15],
        "experience_required": experience_req,
        "word_count": len(text.split()),
    }


def clean_text(text: str) -> str:
    """Remove excessive whitespace and non-printable chars."""
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\x20-\x7E\n]", "", text)
    return text.strip()
