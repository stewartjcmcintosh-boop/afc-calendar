import requests
from datetime import datetime, timedelta
import json
import os
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin

# Primary fixture sources
SOURCE_URL = "https://ics.fixtur.es/v2/aberdeen.ics"
AFC_WEBSITE = "https://www.afc.co.uk"
AFC_FIXTURES_URL = f"{AFC_WEBSITE}/en/matches/mens/fixtures"
AFC_RESULTS_URL = f"{AFC_WEBSITE}/en/matches/mens/results"

OUTPUT_FILE = "aberdeen_fc_ops_calendar.ics"
SCORES_FILE = "match_scores.json"
FIXTURES_CACHE_FILE = "fixtures_cache.json"

def classify(summary, location):
    """Classify fixture and format title with HOME/AWAY visibility"""
    summary_lower = summary.lower()

    # Competition type
    if "cup" in summary_lower or "carabao" in summary_lower or "league cup" in summary_lower:
        comp_type = "CUP"
    elif "friendly" in summary_lower:
        comp_type = "FRIENDLY"
    else:
        comp_type = ""

    # Home vs Away - Make it very visible
    if location and ("pittodrie" in location.lower() or "aberdeen" in location.lower()):
        ha = "HOME"
        formatted = summary.replace("Aberdeen v", "Aberdeen vs").replace("v Aberdeen", "vs Aberdeen")
    else:
        ha = "AWAY"
        formatted = summary.replace("v Aberdeen", "@ Aberdeen").replace("Aberdeen v", "Aberdeen @")

    # Build prefix with enhanced home/away visibility
    if comp_type == "FRIENDLY":
        return f"[{ha} - FRIENDLY] {formatted}"
    elif comp_type == "CUP":
        return f"[{ha} - CUP] {formatted}"
    else:
        return f"[{ha}] {formatted}"


def parse_datetime(dt_string):
    """Parse iCalendar datetime string"""
    if not dt_string:
        return None
    try:
        # Handle both formats: YYYYMMDDTHHMMSSZ and YYYYMMDDTHHMMSS
        if dt_string.endswith('Z'):
            return datetime.strptime(dt_string, "%Y%m%dT%H%M%SZ")
        else:
            return datetime.strptime(dt_string, "%Y%m%dT%H%M%S")
    except (ValueError, TypeError):
        return None


def is_within_12_months(dtstart_string):
    """Check if event is within the next 12 months from today"""
    event_date = parse_datetime(dtstart_string)
    if not event_date:
        return False
    
    now = datetime.utcnow()
    twelve_months_later = now + timedelta(days=365)
    
    return now <= event_date <= twelve_months_later


def load_scores():
    """Load match scores from local cache"""
    if os.path.exists(SCORES_FILE):
        try:
            with open(SCORES_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_scores(scores):
    """Save match scores to local cache"""
    with open(SCORES_FILE, "w") as f:
        json.dump(scores, f, indent=2)


def load_fixtures_cache():
    """Load fixtures from cache"""
    if os.path.exists(FIXTURES_CACHE_FILE):
        try:
            with open(FIXTURES_CACHE_FILE, "r") as f:
                return json.load(f)
        except:
            return {}
    return {}


def save_fixtures_cache(fixtures):
    """Save fixtures to cache"""
    with open(FIXTURES_CACHE_FILE, "w") as f:
        json.dump(fixtures, f, indent=2)


def fetch_scores_from_afc_website():
    """Scrape Aberdeen FC website for match results"""
    try:
        print("  → Fetching match scores from afc.co.uk...")
        response = requests.get(AFC_RESULTS_URL, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        updated_scores = {}
        
        # Look for result elements
        result_elements = soup.find_all(['div', 'article', 'tr'], 
                                       class_=re.compile(r'(result|match|game|fixture)', re.I))
        
        for element in result_elements:
            try:
                text = element.get_text(strip=True)
                
                # Look for score pattern: "Team1 X-X Team2"
                score_pattern = r'(\w+[\w\s]*?)\s+(\d+)\s*[-–]\s*(\d+)\s+(?:Aberdeen|(?:.*?Aberdeen))'
                match = re.search(score_pattern, text, re.IGNORECASE)
                
                if not match:
                    continue
                
                # Extract date
                date_pattern = r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})'
                date_match = re.search(date_pattern, text)
                
                if not date_match:
                    continue
                
                day, month, year = date_match.groups()
                if len(year) == 2:
                    year = "20" + year
                
                date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                score_str = f"{match.group(2)}-{match.group(3)}"
                
                # Extract opponent
                if "Aberdeen" in text:
                    opponent = re.search(r'vs?\s+([A-Z][A-Za-z\s]+?)(?:\s+\d+|$)', text, re.IGNORECASE)
                    if opponent:
                        opp_name = opponent.group(1).strip()
                        match_key = f"Aberdeen vs {opp_name}_{date_str}"
                        updated_scores[match_key] = score_str
                        print(f"    ✓ {match_key}: {score_str}")
            
            except Exception as e:
                continue
        
        if updated_scores:
            print(f"    Found {len(updated_scores)} match results")
        
        return updated_scores
    
    except Exception as e:
        print(f"    ✗ Error fetching scores: {e}")
        return {}


def fetch_from_ics_source(url):
    """Fetch and parse ICS file from URL"""
    try:
        print(f"  → Fetching from ICS source: {url}...")
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        events = []
        block = {}
        
        for line in response.text.splitlines():
            if line.strip() == "BEGIN:VEVENT":
                block = {}
            elif line.strip() == "END:VEVENT":
                if block.get("DTSTART"):
                    events.append(block)
                block = {}
            else:
                if ":" in line:
                    key, val = line.split(":", 1)
                    block[key.strip()] = val.strip()
        
        print(f"    Found {len(events)} events")
        return events
    
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return []


def fetch_from_afc_fixtures_page():
    """Scrape Aberdeen FC fixtures page for comprehensive fixture list"""
    try:
        print(f"  → Fetching fixtures from AFC website...")
        response = requests.get(AFC_FIXTURES_URL, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        events = []
        
        # Look for fixture elements (cards, rows, divs)
        fixture_elements = soup.find_all(['div', 'tr', 'article'], 
                                        class_=re.compile(r'(fixture|match|game)', re.I))
        
        for element in fixture_elements:
            try:
                text = element.get_text(strip=True)
                
                if "Aberdeen" not in text:
                    continue
                
                # Extract date
                date_pattern = r'(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})|(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})'
                date_match = re.search(date_pattern, text)
                
                if not date_match:
                    continue
                
                # Parse date
                if date_match.group(2):  # "01 Jan 2026" format
                    day = date_match.group(1)
                    month_name = date_match.group(2)
                    year = date_match.group(3)
                    month_dict = {
                        'January': '01', 'February': '02', 'March': '03', 'April': '04',
                        'May': '05', 'June': '06', 'July': '07', 'August': '08',
                        'September': '09', 'October': '10', 'November': '11', 'December': '12'
                    }
                    month = month_dict.get(month_name, '01')
                else:  # "01/01/2026" format
                    day = date_match.group(4)
                    month = date_match.group(5)
                    year = date_match.group(6)
                    if len(year) == 2:
                        year = "20" + year
                
                # Extract time
                time_pattern = r'(\d{1,2}):(\d{2})'
                time_match = re.search(time_pattern, text)
                
                if time_match:
                    hour = time_match.group(1).zfill(2)
                    minute = time_match.group(2)
                    dtstart = f"{year}{month.zfill(2)}{day.zfill(2)}T{hour}{minute}00Z"
                else:
                    dtstart = f"{year}{month.zfill(2)}{day.zfill(2)}T150000Z"
                
                # Extract opponent and venue
                opponent_pattern = r'(?:vs?|@)\s+([A-Z][A-Za-z\s]+?)(?:\s+\d+|\s+KO|\s*$)'
                opponent_match = re.search(opponent_pattern, text, re.IGNORECASE)
                
                if not opponent_match:
                    continue
                
                opponent = opponent_match.group(1).strip()
                
                # Determine home/away
                if "@" in text.lower() or opponent.lower() in text.lower() and text.index("@") < text.index("Aberdeen"):
                    summary = f"Aberdeen @ {opponent}"
                    location = f"{opponent} Stadium"
                else:
                    summary = f"Aberdeen vs {opponent}"
                    location = "Pittodrie Stadium"
                
                events.append({
                    "SUMMARY": summary,
                    "DTSTART": dtstart,
                    "LOCATION": location,
                    "UID": f"{summary.replace(' ', '')}_{dtstart}"
                })
            
            except Exception as e:
                continue
        
        print(f"    Found {len(events)} fixtures")
        return events
    
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return []


def get_score_for_match(summary, dtstart_string, scores_cache):
    """Check if match has concluded and add score"""
    event_date = parse_datetime(dtstart_string)
    if not event_date:
        return summary
    
    now = datetime.utcnow()
    
    if event_date > now:
        return summary
    
    # Try to find score with multiple key variations
    date_str = event_date.strftime('%Y-%m-%d')
    
    # Try exact match
    match_key = f"{summary}_{date_str}"
    if match_key in scores_cache:
        score = scores_cache[match_key]
        return f"{summary} - Final: {score}"
    
    # Try variations (remove [HOME]/[AWAY] tags)
    summary_clean = re.sub(r'\[.*?\]\s*', '', summary)
    match_key = f"{summary_clean}_{date_str}"
    if match_key in scores_cache:
        score = scores_cache[match_key]
        return f"{summary} - Final: {score}"
    
    return summary


def deduplicate_events(events_list):
    """Remove duplicate events from combined sources"""
    seen = {}
    unique_events = []
    
    for event in events_list:
        summary = event.get("SUMMARY", "")
        dtstart = event.get("DTSTART", "")
        key = f"{summary}_{dtstart}"
        
        if key not in seen:
            seen[key] = True
            unique_events.append(event)
    
    return unique_events


def build_calendar(events):
    """Build ICS calendar file"""
    now = datetime.utcnow()
    twelve_months_later = now + timedelta(days=365)
    
    cal = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//AFC Calendar//aberdeen.football//EN",
        "X-WR-CALNAME:Aberdeen FC Fixtures",
        f"X-WR-CALDESC:Aberdeen FC Fixtures - {len(events)} matches for next 12 months",
        "X-WR-TIMEZONE:UTC",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH"
    ]

    for e in events:
        cal.append("BEGIN:VEVENT")
        cal.append(f"UID:{e['uid']}")
        cal.append(f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}")
        cal.append(f"DTSTART:{e['dtstart']}")
        if e.get("dtend"):
            cal.append(f"DTEND:{e['dtend']}")
        else:
            # Default 2-hour duration
            cal.append(f"DTEND:{e['dtstart'][:-1]}02{e['dtstart'][-1]}")
        cal.append(f"SUMMARY:{e['summary']}")
        cal.append(f"LOCATION:{e['location']}")
        cal.append(f"DESCRIPTION:{e.get('description', 'Aberdeen FC Fixture')}")
        cal.append("STATUS:CONFIRMED")
        cal.append("END:VEVENT")

    cal.append("END:VCALENDAR")
    return "\n".join(cal)


def main():
    print("\n" + "=" * 70)
    print("ABERDEEN FC CALENDAR - COMPREHENSIVE FIXTURE FETCHER")
    print("=" * 70)
    
    # Step 1: Fetch scores
    print("\n[STEP 1] Fetching Match Scores...")
    website_scores = fetch_scores_from_afc_website()
    cached_scores = load_scores()
    all_scores = {**cached_scores, **website_scores}
    
    if website_scores:
        save_scores(all_scores)
        print(f"  ✓ Total scores cached: {len(all_scores)}")
    
    # Step 2: Fetch fixtures from multiple sources
    print("\n[STEP 2] Fetching Fixtures from Multiple Sources...")
    all_events = []
    
    # Source 1: Primary ICS feed
    print("\n  Source 1: ICS Feed")
    ics_events = fetch_from_ics_source(SOURCE_URL)
    all_events.extend(ics_events)
    
    # Source 2: AFC Website Fixtures
    print("\n  Source 2: AFC Website Fixtures")
    afc_events = fetch_from_afc_fixtures_page()
    all_events.extend(afc_events)
    
    # Source 3: Cached fixtures
    print("\n  Source 3: Cached Fixtures")
    cached_fixtures = load_fixtures_cache()
    if cached_fixtures.get("events"):
        all_events.extend(cached_fixtures["events"])
        print(f"    Found {len(cached_fixtures['events'])} cached events")
    
    # Step 3: Process and filter
    print("\n[STEP 3] Processing Fixtures...")
    
    # Deduplicate
    all_events = deduplicate_events(all_events)
    print(f"  ✓ After deduplication: {len(all_events)} unique events")
    
    # Filter to 12 months and classify
    events = []
    for block in all_events:
        raw_summary = block.get("SUMMARY", "Aberdeen Fixture")
        location = block.get("LOCATION", "")
        dtstart = block.get("DTSTART")
        
        if dtstart and is_within_12_months(dtstart):
            new_summary = classify(raw_summary, location)
            new_summary = get_score_for_match(new_summary, dtstart, all_scores)

            events.append({
                "uid": block.get("UID", raw_summary.replace(" ", "")),
                "summary": new_summary,
                "dtstart": dtstart,
                "dtend": block.get("DTEND"),
                "location": location,
                "description": block.get("DESCRIPTION", "Aberdeen FC Fixture")
            })
    
    # Sort by date
    events.sort(key=lambda x: x['dtstart'])
    print(f"  ✓ Filtered to 12-month window: {len(events)} fixtures")
    
    # Step 4: Cache and build
    print("\n[STEP 4] Caching and Building Calendar...")
    
    save_fixtures_cache({
        "events": [
            {
                "SUMMARY": e['summary'],
                "DTSTART": e['dtstart'],
                "LOCATION": e['location'],
                "DTEND": e.get('dtend'),
                "UID": e['uid'],
                "DESCRIPTION": e.get('description')
            }
            for e in events
        ],
        "cached_at": datetime.utcnow().isoformat(),
        "total_fixtures": len(events)
    })
    
    calendar = build_calendar(events)
    
    with open(OUTPUT_FILE, "w") as f:
        f.write(calendar)
    
    print(f"  ✓ ICS file written: {OUTPUT_FILE}")
    print(f"  ✓ File size: {len(calendar)} bytes")
    print(f"  ✓ Total fixtures: {len(events)}")
    
    # Summary
    print("\n" + "=" * 70)
    print(f"✅ SUCCESS: Calendar updated with {len(events)} Aberdeen FC fixtures")
    print(f"   Time range: {datetime.utcnow().strftime('%Y-%m-%d')} to {(datetime.utcnow() + timedelta(days=365)).strftime('%Y-%m-%d')}")
    print(f"   Scores captured: {len(all_scores)} matches")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
