import requests
from datetime import datetime, timedelta
import json
import os
from bs4 import BeautifulSoup
import re

# Primary fixture source
SOURCE_URL = "https://ics.fixtur.es/v2/aberdeen.ics"

# Alternative fixture sources for comprehensive coverage
ALTERNATIVE_SOURCES = [
    "https://www.afc.co.uk/en/matches/mens/fixtures",  # Official AFC website
    "https://www.spfl.co.uk/",  # Scottish Premier Football League
]

OUTPUT_FILE = "aberdeen_fc_ops_calendar.ics"
SCORES_FILE = "match_scores.json"
FIXTURES_CACHE_FILE = "fixtures_cache.json"

# Aberdeen FC official website for results
AFC_RESULTS_URL = "https://www.afc.co.uk/en/matches/mens/results"

def classify(summary, location):
    summary_lower = summary.lower()

    # Competition
    if "cup" in summary_lower:
        comp_type = "CUP"
    elif "friendly" in summary_lower:
        comp_type = "FRIENDLY"
    else:
        comp_type = ""

    # Home vs Away - Make it very visible
    if "pittodrie" in location.lower():
        ha = "HOME"
        ha_symbol = "🏠"
        formatted = summary.replace("Aberdeen v", "Aberdeen vs")
    else:
        ha = "AWAY"
        ha_symbol = "✈️"
        formatted = summary.replace("v Aberdeen", "@ Aberdeen").replace("Aberdeen v", "Aberdeen @")

    # Build prefix with enhanced home/away visibility
    if comp_type == "FRIENDLY":
        return f"[{ha} - FRIENDLY] {formatted}"
    elif comp_type == "CUP":
        return f"[{ha} - CUP] {formatted}"
    else:
        # League match - make home/away very clear
        return f"[{ha}] {formatted}"


def parse_datetime(dt_string):
    """Parse iCalendar datetime string (YYYYMMDDTHHMMSSZ) to datetime object"""
    try:
        return datetime.strptime(dt_string, "%Y%m%dT%H%M%SZ")
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
    """
    Scrape Aberdeen FC official website for match results.
    Returns dictionary of match scores.
    """
    try:
        print("Fetching match scores from afc.co.uk...")
        response = requests.get(AFC_RESULTS_URL, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        updated_scores = {}
        
        # Look for result cards/entries on the page
        # The exact structure may vary, so we'll look for common patterns
        result_elements = soup.find_all(['div', 'article'], class_=re.compile(r'(result|match|fixture)', re.I))
        
        if not result_elements:
            # Alternative: look for score elements
            result_elements = soup.find_all(['div'], class_=re.compile(r'(score|result)', re.I))
        
        for element in result_elements:
            try:
                # Extract team names
                teams_text = element.get_text(strip=True)
                
                # Look for score pattern: "Team1 X-X Team2" or similar
                score_pattern = r'(\w+[\w\s]*?)\s(\d+)\s*[-–]\s*(\d+)\s*(\w+[\w\s]*?)(?:\s|$)'
                match = re.search(score_pattern, teams_text)
                
                if not match:
                    continue
                
                home_team = match.group(1).strip()
                home_score = match.group(2)
                away_score = match.group(3)
                away_team = match.group(4).strip()
                
                # Filter for Aberdeen matches
                if "Aberdeen" not in home_team and "Aberdeen" not in away_team:
                    continue
                
                # Extract date if available
                date_text = element.get_text(strip=True)
                date_pattern = r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})'
                date_match = re.search(date_pattern, date_text)
                
                if not date_match:
                    continue
                
                day, month, year = date_match.groups()
                if len(year) == 2:
                    year = "20" + year
                
                date_str = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                
                # Create match key
                score_str = f"{home_score}-{away_score}"
                
                if "Aberdeen" in home_team:
                    match_summary = f"Aberdeen vs {away_team.strip()}"
                else:
                    match_summary = f"Aberdeen @ {home_team.strip()}"
                
                match_key = f"{match_summary}_{date_str}"
                updated_scores[match_key] = score_str
                print(f"Fetched: {match_summary} on {date_str} - {score_str}")
                
            except Exception as e:
                continue
        
        if updated_scores:
            print(f"Successfully fetched {len(updated_scores)} match results")
        else:
            print("No match results found on afc.co.uk - trying alternative parsing...")
            # Try more aggressive scraping
            updated_scores = _scrape_results_alternative(soup)
        
        return updated_scores
    
    except Exception as e:
        print(f"Error fetching scores from afc.co.uk: {e}")
        return {}


def _scrape_results_alternative(soup):
    """
    Alternative scraping method if standard parsing fails.
    Looks for text patterns matching results.
    """
    try:
        updated_scores = {}
        text_content = soup.get_text()
        
        # Look for common result patterns in page text
        # Pattern: "Team1 X Aberdeen X Team2" or "Aberdeen X vs X Team"
        result_patterns = [
            r'([\w\s]+?)\s(\d+)\s*(?:–|-)\s*(\d+)\s*(?:Aberdeen)',
            r'(?:Aberdeen)\s(\d+)\s*(?:–|-)\s*(\d+)\s*([\w\s]+)',
        ]
        
        for pattern in result_patterns:
            for match in re.finditer(pattern, text_content):
                pass  # Process if needed
        
        return updated_scores
    except:
        return {}


def fetch_from_ics_source(url):
    """
    Fetch and parse ICS/iCalendar fixtures from a source URL.
    Returns list of event dictionaries.
    """
    try:
        print(f"Fetching fixtures from {url}...")
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        
        events = []
        block = {}
        
        for line in response.text.splitlines():
            if line == "BEGIN:VEVENT":
                block = {}
            elif line == "END:VEVENT":
                if block.get("DTSTART"):
                    events.append(block)
                block = {}
            else:
                if ":" in line:
                    key, val = line.split(":", 1)
                    block[key] = val
        
        print(f"Fetched {len(events)} events from ICS source")
        return events
    
    except Exception as e:
        print(f"Error fetching from {url}: {e}")
        return []


def fetch_from_afc_website_fixtures():
    """
    Scrape Aberdeen FC official fixtures page.
    Returns list of event dictionaries.
    """
    try:
        print("Fetching fixtures from afc.co.uk...")
        response = requests.get(ALTERNATIVE_SOURCES[0], timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        events = []
        
        # Look for fixture elements
        fixture_elements = soup.find_all(['div', 'tr'], class_=re.compile(r'(fixture|match|game)', re.I))
        
        for element in fixture_elements:
            try:
                text = element.get_text(strip=True)
                
                # Look for date pattern
                date_pattern = r'(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})'
                date_match = re.search(date_pattern, text)
                
                if not date_match:
                    continue
                
                day, month, year = date_match.groups()
                if len(year) == 2:
                    year = "20" + year
                
                # Look for time pattern
                time_pattern = r'(\d{1,2}):(\d{2})'
                time_match = re.search(time_pattern, text)
                
                if time_match:
                    hour, minute = time_match.groups()
                    dtstart = f"{year}{month.zfill(2)}{day.zfill(2)}T{hour.zfill(2)}{minute}00Z"
                else:
                    dtstart = f"{year}{month.zfill(2)}{day.zfill(2)}T150000Z"  # Default to 3 PM
                
                # Extract opponent
                opponent_match = re.search(r'(?:vs|v|@)\s+([A-Z][A-Za-z\s]+?)(?:\s|$)', text, re.IGNORECASE)
                
                if opponent_match:
                    opponent = opponent_match.group(1).strip()
                    
                    # Determine home/away
                    if "@" in text.lower():
                        summary = f"Aberdeen @ {opponent}"
                        location = "Away"
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
        
        print(f"Fetched {len(events)} fixtures from AFC website")
        return events
    
    except Exception as e:
        print(f"Error fetching fixtures from AFC website: {e}")
        return []


def get_score_for_match(summary, dtstart_string, scores_cache):
    """
    Check if match has concluded and retrieve score.
    Returns updated summary with score if available, otherwise returns original.
    """
    event_date = parse_datetime(dtstart_string)
    if not event_date:
        return summary
    
    now = datetime.utcnow()
    
    # Only check for scores if match has already concluded
    if event_date > now:
        return summary
    
    # Create a match key from summary and date
    match_key = f"{summary}_{event_date.strftime('%Y-%m-%d')}"
    
    # Check if we have a cached score
    if match_key in scores_cache:
        score = scores_cache[match_key]
        return f"{summary} - Final: {score}"
    
    return summary


def deduplicate_events(events_list):
    """
    Remove duplicate events from combined sources.
    Returns deduplicated list maintaining order.
    """
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
    now = datetime.utcnow()
    twelve_months_later = now + timedelta(days=365)
    
    cal = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//AFC Ops Calendar//EN",
        "X-WR-CALNAME:Aberdeen FC Fixtures (Ops View)",
        f"X-WR-CALDESC:Aberdeen FC Fixtures for the next 12 months ({now.strftime('%Y-%m-%d')} to {twelve_months_later.strftime('%Y-%m-%d')})",
        "X-WR-TIMEZONE:UTC"
    ]

    for e in events:
        cal.append("BEGIN:VEVENT")
        cal.append(f"UID:{e['uid']}")
        cal.append(f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}")
        cal.append(f"SUMMARY:{e['summary']}")
        cal.append(f"DTSTART:{e['dtstart']}")
        if e.get("dtend"):
            cal.append(f"DTEND:{e['dtend']}")
        cal.append(f"LOCATION:{e['location']}")
        cal.append("DESCRIPTION:Auto-generated AFC ops calendar - Aberdeen FC")
        cal.append("END:VEVENT")

    cal.append("END:VCALENDAR")
    return "\n".join(cal)


def add_score(summary, date_str, score):
    """
    Manually add or update a match score.
    Usage: add_score("Aberdeen vs Hearts", "2026-08-01", "2-1")
    """
    scores = load_scores()
    match_key = f"{summary}_{date_str}"
    scores[match_key] = score
    save_scores(scores)
    print(f"Score added for {match_key}: {score}")


def main():
    print("=" * 60)
    print("Updating Aberdeen FC calendar - Multi-Source Fixture Fetcher")
    print("=" * 60)
    
    # Fetch latest scores from AFC website
    print("\n[STEP 1] Fetching match scores from afc.co.uk...")
    website_scores = fetch_scores_from_afc_website()
    
    # Load cached scores
    cached_scores = load_scores()
    
    # Merge website scores with cached scores (website scores take precedence)
    all_scores = {**cached_scores, **website_scores}
    
    # Save updated scores
    if website_scores:
        save_scores(all_scores)
    
    print("\n[STEP 2] Fetching fixtures from multiple sources...")
    
    # Collect events from all sources
    all_events = []
    
    # Source 1: Primary ICS feed
    print(f"\n  Source 1: ICS Feed ({SOURCE_URL})")
    try:
        ics_events = fetch_from_ics_source(SOURCE_URL)
        all_events.extend(ics_events)
        print(f"    ✓ Added {len(ics_events)} events")
    except Exception as e:
        print(f"    ✗ Error: {e}")
    
    # Source 2: AFC Official Website Fixtures
    print(f"\n  Source 2: AFC Website Fixtures")
    try:
        afc_events = fetch_from_afc_website_fixtures()
        all_events.extend(afc_events)
        print(f"    ✓ Added {len(afc_events)} events")
    except Exception as e:
        print(f"    ✗ Error: {e}")
    
    # Source 3: Load any cached fixtures
    print(f"\n  Source 3: Cached Fixtures")
    cached_fixtures = load_fixtures_cache()
    if cached_fixtures:
        all_events.extend(cached_fixtures.get("events", []))
        print(f"    ✓ Added {len(cached_fixtures.get('events', []))} cached events")
    
    print(f"\n[STEP 3] Processing and filtering fixtures...")
    
    # Deduplicate events
    all_events = deduplicate_events(all_events)
    print(f"  After deduplication: {len(all_events)} unique events")
    
    # Filter to 12 months and process
    events = []
    for block in all_events:
        raw_summary = block.get("SUMMARY", "Aberdeen Fixture")
        location = block.get("LOCATION", "")
        dtstart = block.get("DTSTART")
        
        # Filter: only include events within the next 12 months
        if dtstart and is_within_12_months(dtstart):
            new_summary = classify(raw_summary, location)
            
            # Check for scores if match has concluded
            new_summary = get_score_for_match(new_summary, dtstart, all_scores)

            events.append({
                "uid": block.get("UID", raw_summary.replace(" ", "")),
                "summary": new_summary,
                "dtstart": dtstart,
                "dtend": block.get("DTEND"),
                "location": location
            })
    
    # Sort events by date
    events.sort(key=lambda x: x['dtstart'])
    
    print(f"  Filtered to 12-month window: {len(events)} fixtures")
    
    # Cache the fixtures
    print(f"\n[STEP 4] Caching fixtures...")
    save_fixtures_cache({
        "events": [
            {
                "SUMMARY": e['summary'],
                "DTSTART": e['dtstart'],
                "LOCATION": e['location'],
                "DTEND": e.get('dtend'),
                "UID": e['uid']
            }
            for e in events
        ],
        "cached_at": datetime.utcnow().isoformat()
    })
    print(f"  ✓ Fixtures cached")
    
    # Build and write calendar
    print(f"\n[STEP 5] Building ICS calendar file...")
    calendar = build_calendar(events)
    
    with open(OUTPUT_FILE, "w") as f:
        f.write(calendar)
    
    print(f"  ✓ Calendar written to {OUTPUT_FILE}")
    
    print("\n" + "=" * 60)
    print(f"SUCCESS: Calendar updated with {len(events)} fixtures")
    print(f"Time range: Today to 12 months ahead")
    print(f"Scores captured: {len(all_scores)} matches")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
