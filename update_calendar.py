import requests
from datetime import datetime, timedelta
import json
import os

SOURCE_URL = "https://ics.fixtur.es/v2/aberdeen.ics"
OUTPUT_FILE = "aberdeen_fc_ops_calendar.ics"
SCORES_FILE = "match_scores.json"
SCORES_API_URL = "https://api.football-data.org/v4/competitions/PL/matches"  # Example API - adjust as needed

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


def get_score_for_match(summary, dtstart_string):
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
    
    scores = load_scores()
    
    # Create a match key from summary and date
    match_key = f"{summary}_{event_date.strftime('%Y-%m-%d')}"
    
    # Check if we have a cached score
    if match_key in scores:
        score = scores[match_key]
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
    Usage: add_score("[H] Aberdeen vs Hearts", "2026-08-01", "2-1 Aberdeen")
    """
    scores = load_scores()
    match_key = f"{summary}_{date_str}"
    scores[match_key] = score
    save_scores(scores)
    print(f"Score added for {match_key}: {score}")


def main():
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
                new_summary = get_score_for_match(new_summary, dtstart)

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


if __name__ == "__main__":
    main()
