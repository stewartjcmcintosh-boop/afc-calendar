import requests
from datetime import datetime, timedelta

SOURCE_URL = "https://ics.fixtur.es/v2/aberdeen.ics"
OUTPUT_FILE = "aberdeen_fc_ops_calendar.ics"


def ics_escape(text):
    """Escape special characters according to RFC5545."""

    if not text:
        return ""

    return (
        str(text)
        .replace("\\", "\\\\")
        .replace(";", r"\;")
        .replace(",", r"\,")
        .replace("\n", r"\n")
        .replace("\r", "")
    )


def parse_datetime(dt_string):
    """Parse common ICS date formats."""

    if not dt_string:
        return None

    formats = [
        "%Y%m%dT%H%M%SZ",
        "%Y%m%dT%H%M%S",
        "%Y%m%d"
    ]

    for fmt in formats:
        try:
            return datetime.strptime(dt_string, fmt)
        except ValueError:
            continue

    return None


def classify_fixture(summary):
    """Add HOME/AWAY indicator."""

    summary = summary.strip()

    if summary.startswith("Aberdeen v "):
        return f"[HOME] {summary}"

    if " v Aberdeen" in summary:
        return f"[AWAY] {summary}"

    return summary


def fetch_events():
    """Download and parse ICS source."""

    print(f"Downloading fixtures from {SOURCE_URL}")

    response = requests.get(
        SOURCE_URL,
        timeout=30
    )

    response.raise_for_status()

    events = []
    current = {}

    for raw_line in response.text.splitlines():

        line = raw_line.strip()

        if line == "BEGIN:VEVENT":
            current = {}
            continue

        if line == "END:VEVENT":

            if current.get("DTSTART"):
                events.append(current)

            current = {}
            continue

        if ":" not in line:
            continue

        key, value = line.split(":", 1)

        # Convert:
        # DTSTART;TZID=Europe/London
        # into:
        # DTSTART
        key = key.split(";")[0]

        current[key.strip()] = value.strip()

    print(f"Downloaded {len(events)} fixtures")

    return events


def filter_events(events):
    """Keep last 30 days and next 12 months."""

    now = datetime.utcnow()

    earliest = now - timedelta(days=30)
    latest = now + timedelta(days=365)

    filtered = []

    for event in events:

        dtstart = parse_datetime(
            event.get("DTSTART")
        )

        if dtstart is None:
            continue

        if earliest <= dtstart <= latest:
            filtered.append(event)

    print(
        f"Fixtures within date range: {len(filtered)}"
    )

    return filtered


def build_calendar(events):

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Aberdeen FC//Fixtures//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Aberdeen FC Fixtures",
        "X-WR-TIMEZONE:UTC",
        "X-PUBLISHED-TTL:PT24H",
        "REFRESH-INTERVAL;VALUE=DURATION:PT24H"
    ]

    for event in events:

        summary = classify_fixture(
            event.get(
                "SUMMARY",
                "Aberdeen FC Fixture"
            )
        )

        dtstart = event["DTSTART"]

        start_dt = parse_datetime(dtstart)

        if start_dt:
            end_dt = (
                start_dt +
                timedelta(hours=2)
            )

            dtend = end_dt.strftime(
                "%Y%m%dT%H%M%SZ"
            )
        else:
            dtend = dtstart

        uid = event.get("UID")

        if not uid:
            uid = (
                f"{dtstart}-"
                f"{summary.replace(' ', '')}"
                "@aberdeenfc"
            )

        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{uid}",
                f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
                f"DTSTART:{dtstart}",
                f"DTEND:{dtend}",
                f"SUMMARY:{ics_escape(summary)}",
                f"LOCATION:{ics_escape(event.get('LOCATION', ''))}",
                f"DESCRIPTION:{ics_escape(event.get('DESCRIPTION', 'Aberdeen FC Fixture'))}",
                "STATUS:CONFIRMED",
                "END:VEVENT"
            ]
        )

    lines.append("END:VCALENDAR")

    return "\n".join(lines)


def main():

    print("=" * 60)
    print("ABERDEEN FC CALENDAR UPDATE")
    print("=" * 60)

    events = fetch_events()

    events = filter_events(events)

    events.sort(
        key=lambda event:
        parse_datetime(
            event.get("DTSTART")
        ) or datetime.max
    )

    calendar = build_calendar(events)

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as file:
        file.write(calendar)

    print(
        f"Calendar written to: {OUTPUT_FILE}"
    )

    print(
        f"Fixtures included: {len(events)}"
    )

    print("Update complete")


if __name__ == "__main__":
    main()
