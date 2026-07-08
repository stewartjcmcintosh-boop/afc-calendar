import requests
from datetime import datetime, timedelta
import json
import os
from bs4 import BeautifulSoup
import re

SOURCE_URL = "https://ics.fixtur.es/v2/aberdeen.ics"
OUTPUT_FILE = "aberdeen_fc_ops_calendar.ics"
SCORES_FILE = "match_scores.json"

# Aberdeen FC official website for results
AFC_RESULTS_URL = "https://www.afc.co.uk/en/matches/mens/results"

def classify(summary, location):
    summary_lower = summary.lower()

    # Competition
    if "cup" in summary_lower:
        comp_type = "CUP"
    elif "friendly" in summary_lower:
        comp_type = "F"
    else:
        comp_type = ""

    # Home vs Away
    if "pittodrie" in location.lower():
        ha = "H"
        formatted = summary.replace("Aberdeen v", "Aberdeen vs")
    else:
        ha = "A"
        formatted = summary.replace("v Aberdeen", "@ Aberdeen").replace("Aberdeen v", "Aberdeen @")

    # Build prefix
    if comp_type == "F":
        return f"[F] {formatted}"
    elif comp_type == "CUP":
        return f"[{ha}-CUP] {formatted}"
    else:
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


def build_calendar(events):
    now = datetime.utcnow()
    twelve_months_later = now + timedelta(days=365)
    
    cal = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//AFC Ops Calendar//EN",
        "X-WR-CALNAME:Aberdeen FC Fixtures (Ops View)",
        f"X-WR-CALDESC:Aberdeen FC Fixtures for the next 12 months ({now.strftime('%Y-%m-%d')} to {twelve_months_later.strftime('%Y-%m-%d')})"
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
        cal.append("DESCRIPTION:Auto-generated AFC ops calendar")
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
    print("Updating Aberdeen FC calendar...")
    
    # Fetch latest scores from AFC website
    print("Fetching match scores from afc.co.uk...")
    website_scores = fetch_scores_from_afc_website()
    
    # Load cached scores
    cached_scores = load_scores()
    
    # Merge website scores with cached scores (website scores take precedence)
    all_scores = {**cached_scores, **website_scores}
    
    # Save updated scores
    if website_scores:
        save_scores(all_scores)
    
    # Fetch fixtures from iCalendar source
    response = requests.get(SOURCE_URL)
    text = response.text

    events = []
    block = {}

    for line in text.splitlines():
        if line == "BEGIN:VEVENT":
            block = {}
        elif line == "END:VEVENT":
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
        else:
            if ":" in line:
                key, val = line.split(":", 1)
                block[key] = val

    calendar = build_calendar(events)

    with open(OUTPUT_FILE, "w") as f:
        f.write(calendar)
    
    print(f"Calendar updated with {len(events)} events in the next 12 months")
    if website_scores:
        print(f"Added/updated {len(website_scores)} match scores from afc.co.uk")


if __name__ == "__main__":
    main()
