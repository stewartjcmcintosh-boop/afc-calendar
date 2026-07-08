import requests
from datetime import datetime, timedelta
import json
import os

SOURCE_URL = "https://ics.fixtur.es/v2/aberdeen.ics"
OUTPUT_FILE = "aberdeen_fc_ops_calendar.ics"
SCORES_FILE = "match_scores.json"

# Using football-data.org API - requires free API key from https://www.football-data.org/
# Set FOOTBALL_DATA_API_KEY environment variable or replace with your key
FOOTBALL_DATA_API_KEY = os.getenv("FOOTBALL_DATA_API_KEY", "")
FOOTBALL_DATA_BASE_URL = "https://api.football-data.org/v4"

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


def fetch_scores_from_api():
    """
    Fetch Aberdeen FC match results from football-data.org API.
    Updates the match_scores.json with latest results.
    """
    if not FOOTBALL_DATA_API_KEY:
        print("Warning: FOOTBALL_DATA_API_KEY not set. Skipping automatic score fetch.")
        return {}
    
    try:
        headers = {"X-Auth-Token": FOOTBALL_DATA_API_KEY}
        
        # Fetch Aberdeen's matches from multiple competitions
        # Note: You may need to adjust competition IDs based on available leagues
        competitions = ["PL", "CUP", "LC"]  # Premier League, FA Cup, League Cup
        
        updated_scores = {}
        
        for comp in competitions:
            try:
                url = f"{FOOTBALL_DATA_BASE_URL}/competitions/{comp}/matches?status=FINISHED"
                response = requests.get(url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    matches = response.json().get("matches", [])
                    
                    for match in matches:
                        home_team = match.get("homeTeam", {}).get("name", "")
                        away_team = match.get("awayTeam", {}).get("name", "")
                        
                        # Filter for Aberdeen matches
                        if "Aberdeen" not in home_team and "Aberdeen" not in away_team:
                            continue
                        
                        status = match.get("status")
                        if status != "FINISHED":
                            continue
                        
                        score = match.get("score", {})
                        home_score = score.get("fullTime", {}).get("home")
                        away_score = score.get("fullTime", {}).get("away")
                        
                        if home_score is None or away_score is None:
                            continue
                        
                        match_date = match.get("utcDate", "")
                        if not match_date:
                            continue
                        
                        # Format: "2026-08-01T16:30:00Z" -> "2026-08-01"
                        date_str = match_date.split("T")[0]
                        
                        # Create match key based on team names
                        if "Aberdeen" in home_team:
                            match_summary = f"Aberdeen vs {away_team}"
                        else:
                            match_summary = f"Aberdeen @ {home_team}"
                        
                        score_str = f"{home_score}-{away_score}"
                        match_key = f"{match_summary}_{date_str}"
                        
                        updated_scores[match_key] = score_str
                        print(f"Fetched: {match_summary} on {date_str} - {score_str}")
                
            except Exception as e:
                print(f"Error fetching from competition {comp}: {e}")
                continue
        
        return updated_scores
    
    except Exception as e:
        print(f"Error fetching scores from API: {e}")
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
    Usage: add_score("[H] Aberdeen vs Hearts", "2026-08-01", "2-1")
    """
    scores = load_scores()
    match_key = f"{summary}_{date_str}"
    scores[match_key] = score
    save_scores(scores)
    print(f"Score added for {match_key}: {score}")


def main():
    print("Updating Aberdeen FC calendar...")
    
    # Fetch latest scores from API
    print("Fetching match scores from football-data.org...")
    api_scores = fetch_scores_from_api()
    
    # Load cached scores
    cached_scores = load_scores()
    
    # Merge API scores with cached scores (API scores take precedence)
    all_scores = {**cached_scores, **api_scores}
    
    # Save updated scores
    if api_scores:
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
    if api_scores:
        print(f"Added/updated {len(api_scores)} match scores from API")


if __name__ == "__main__":
    main()
