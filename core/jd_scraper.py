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

# --- Role title detection -----------------------------------------------------
# Everything below matches on WHOLE WORDS only. Substring matching previously
# mistook "Backend Engineer" for nav chrome (because of "back") and matched
# "ai"/"ml"/"data" inside words like "Maintain" and "Available".

# Multi-word titles are the strongest signal, so they are checked first.
STRONG_ROLE_PHRASES = (
    "machine learning engineer", "site reliability engineer", "software engineer",
    "data engineer", "data scientist", "data analyst", "product manager",
    "engineering manager", "devops engineer", "qa engineer", "test engineer",
    "solutions architect", "product designer", "ux designer", "ui designer",
    "graphic designer", "business analyst", "marketing manager",
    "project manager", "account executive", "full stack engineer",
    "fullstack engineer", "front end engineer", "backend engineer",
    "research scientist", "product owner", "scrum master",
)

# Single words that genuinely appear in job titles.
ROLE_WORDS = frozenset({
    "engineer", "engineering", "developer", "development", "designer", "manager",
    "analyst", "intern", "internship", "scientist", "architect", "consultant",
    "specialist", "associate", "director", "coordinator", "executive", "officer",
    "administrator", "administrative", "assistant", "supervisor", "lead",
    "head", "chief", "president", "recruiter", "technician", "strategist",
    "accountant", "auditor", "attorney", "editor", "producer", "marketer",
    "copywriter", "planner", "buyer", "seller", "counsel", "nurse", "teacher",
    "sre", "sde", "swe", "devops", "frontend", "backend", "fullstack",
})

# Generic words that only count when they are part of a compound title
# (e.g. "Data Scientist" or "AI Engineer"), never on their own.
WEAK_ROLE_WORDS = frozenset({"data", "ai", "ml", "cloud", "security", "qa", "test", "product"})

# Navigation / page chrome. Phrased as whole phrases so that legitimate titles
# such as "Backend Engineer" or "Feedback Lead" survive.
NAV_CHROME = (
    r"\bapply now\b", r"\bapply\b", r"\bapply here\b", r"\blog ?in\b", r"\bsign in\b",
    r"\bsign up\b", r"\bregister\b", r"\bcookie", r"\bprivacy policy\b",
    r"\bterms of (?:use|service)\b", r"\bhome\b", r"\bsearch\b",
    r"\bsave (?:this )?job\b", r"\breport (?:this|job)\b", r"\bshare\b",
    r"\bback to\b", r"\bview all\b", r"\ball (?:jobs|openings|roles)\b",
    r"\bskip to\b", r"\baccessibility\b", r"\bsitemap\b", r"\bnewsletter\b",
    r"\bsubscribe\b", r"\bhttp[s]?://", r"\bwww\.", r"\bcookie settings\b",
    r"\bclick here\b", r"\bread more\b", r"\bsee (?:all|more)\b",
)

# Words that give away a sentence / paragraph rather than a title.
SENTENCE_MARKERS = (
    r"\byou will\b", r"\bwe are\b", r"\bwe're\b", r"\bour team\b", r"\bthe team\b",
    r"\bthis role\b", r"\bthe role\b", r"\bresponsib", r"\byou have\b",
    r"\bwe're looking\b", r"\blooking for\b", r"\bhelp us\b", r"\bwhat you'll\b",
    r"\babout the (?:role|company|team)\b", r"\bwhat you will\b",
)

MAX_TITLE_CHARS = 120
MAX_TITLE_WORDS = 9
MAX_EXPERIENCE_CHARS = 200
TITLE_SCAN_LINES = 20

_NAV_RE = re.compile("|".join(NAV_CHROME), re.IGNORECASE)
_SENTENCE_RE = re.compile("|".join(SENTENCE_MARKERS), re.IGNORECASE)
_STRONG_PHRASE_RE = re.compile(
    "|".join(re.escape(p) for p in STRONG_ROLE_PHRASES), re.IGNORECASE
)
_WEAK_PHRASE_RE = re.compile(
    r"\b(?:" + "|".join(sorted(WEAK_ROLE_WORDS)) + r")\s+\w+"
    r"(?:\s+(?:engineer|developer|scientist|analyst|manager|specialist|architect|lead))?",
    re.IGNORECASE,
)
_WHITESPACE_RE = re.compile(r"[^\S\n]+")
_BLANK_LINES_RE = re.compile(r"\n{3,}")
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")
_YEARS_RE = re.compile(r"\d+[\+\-]?\s*(?:years?|yrs?)", re.IGNORECASE)
_SKILL_HEADER_RE = re.compile(
    r"skill|requirement|qualification|must have|you will need", re.IGNORECASE
)


def _strip_control_chars(text: str) -> str:
    """Drop true control characters but keep all printable Unicode.

    An aggressive ``[^\\x20-\\x7E\\n]`` filter used to eat em-dashes, curly
    quotes, bullets and non-Latin text.
    """
    return _CONTROL_CHARS_RE.sub("", text)


def _looks_like_title(line: str) -> bool:
    """Heuristic: short, title-cased, no sentence markers."""
    if _SENTENCE_RE.search(line):
        return False
    words = line.split()
    if not (1 <= len(words) <= MAX_TITLE_WORDS):
        return False
    if line.rstrip().endswith((".", ",", ":", ";", "!", "?")):
        return False
    meaningful = [w for w in words if re.search(r"[A-Za-z]", w)]
    if not meaningful:
        return False
    capitalised = sum(1 for w in meaningful if w[:1].isupper())
    return capitalised / len(meaningful) >= 0.6


def _score_role_line(line: str, index: int) -> int:
    """Score how likely a single line is to be the job title. 0 means 'no'."""
    if not line or len(line) > MAX_TITLE_CHARS or _NAV_RE.search(line):
        return 0

    score = 0
    if _STRONG_PHRASE_RE.search(line):
        score += 5
    if any(word.lower().strip(".,:;-()") in ROLE_WORDS for word in line.split()):
        score += 3
    if _WEAK_PHRASE_RE.search(line):
        score += 2
    if _looks_like_title(line):
        score += 2
    if len(line) <= 60:
        score += 1
    if index < 8:
        score += 1
    if _SENTENCE_RE.search(line):
        score -= 4
    if len(line.split()) > MAX_TITLE_WORDS:
        score -= 3
    return score


def _detect_role_title(lines: list[str]) -> str:
    """Pick the most title-like line, ignoring nav chrome and prose."""
    best_title = ""
    best_score = 0
    for index, line in enumerate(lines[:TITLE_SCAN_LINES]):
        score = _score_role_line(line, index)
        # Strictly greater keeps the earliest line on ties, which is the title.
        if score > best_score:
            best_score, best_title = score, line

    if best_title:
        return best_title

    # Fallback: first plausible-looking line, so callers never get an empty title.
    for line in lines[:TITLE_SCAN_LINES]:
        if 3 <= len(line) <= MAX_TITLE_CHARS and not _NAV_RE.search(line):
            return line
    return "Unknown Role"


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
                        return normalize_block_text(el.get_text())

        # Generic fallback: grab largest text block
        candidates = soup.find_all(["div", "section", "article", "main"])
        best = max(candidates, key=lambda t: len(t.get_text()), default=None)
        if best:
            return normalize_block_text(best.get_text())

        return normalize_block_text(soup.body.get_text() if soup.body else "")

    except Exception as e:
        return f"[Error scraping URL: {str(e)}. Please paste the JD text directly.]"


def parse_jd_text(text: str) -> dict:
    """
    Extract structured info from raw JD text.
    Returns role, company, required skills, experience, and full text.
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]

    role_title = _detect_role_title(lines)

    skills_keywords = []
    experience_req = ""

    skill_section_started = False
    for line in lines:
        if _SKILL_HEADER_RE.search(line):
            skill_section_started = True
        elif skill_section_started and len(line) < 100:
            skills_keywords.append(line)
        if not experience_req and _YEARS_RE.search(line):
            # Bound the value: a flattened scrape can otherwise hand the model
            # an entire multi-kilobyte paragraph as "experience required".
            experience_req = line[:MAX_EXPERIENCE_CHARS].strip()

    return {
        "full_text": text,
        "role_title": role_title,
        "required_skills": skills_keywords[:15],
        "experience_required": experience_req,
        "word_count": len(text.split()),
    }


def normalize_block_text(text: str) -> str:
    """Normalise scraped HTML text while PRESERVING line breaks.

    ``clean_text`` collapses newlines, which turned every scraped posting into
    one giant line and left ``parse_jd_text`` with nothing to detect a title
    from. Block text keeps its structure: horizontal whitespace is squeezed,
    blank runs are collapsed to one blank line, control characters are dropped.
    """
    text = _strip_control_chars(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _WHITESPACE_RE.sub(" ", text)
    lines = [line.strip() for line in text.split("\n")]
    return _BLANK_LINES_RE.sub("\n\n", "\n".join(lines)).strip()


def clean_text(text: str) -> str:
    """Collapse to a single line, keeping all printable Unicode."""
    text = _strip_control_chars(text)
    return re.sub(r"\s+", " ", text).strip()
