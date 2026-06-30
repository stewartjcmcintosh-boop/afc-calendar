import requests
from datetime import datetime, timedelta

SOURCE_URL = "https://ics.fixtur.es/v2/aberdeen.ics"
OUTPUT_FILE = "aberdeen_fc_ops_calendar.ics"

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


def build_calendar(events):
    cal = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//AFC Ops Calendar//EN",
        "X-WR-CALNAME:Aberdeen FC Fixtures (Ops View)"
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
        cal.append("END:VEVENT")

    cal.append("END:VCALENDAR")
    return "\n".join(cal)


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

            new_summary = classify(raw_summary, location)

            events.append({
                "uid": block.get("UID", raw_summary.replace(" ", "")),
                "summary": new_summary,
                "dtstart": block.get("DTSTART"),
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


if __name__ == "__main__":
    main()
