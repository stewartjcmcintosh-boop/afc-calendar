import json
import os
import re
from datetime import datetime, timedelta

import requests
from bs4 import BeautifulSoup

SOURCE_URL = "https://ics.fixtur.es/v2/aberdeen.ics"

AFC_WEBSITE = "https://www.afc.co.uk"
AFC_FIXTURES_URL = f"{AFC_WEBSITE}/en/matches/mens/fixtures"
AFC_RESULTS_URL = f"{AFC_WEBSITE}/en/matches/mens/results"

OUTPUT_FILE = "aberdeen_fc_ops_calendar.ics"
SCORES_FILE = "match_scores.json"
FIXTURES_CACHE_FILE = "fixtures_cache.json"

session = requests.Session()
session.headers.update(
    {
        "User-Agent": "AberdeenFC-Calendar/1.0"
    }
)


def ics_escape(text):
    """Escape text according to RFC5545."""

    if text is None:
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
    """Parse iCalendar date strings."""

    if not dt_string:
        return None

    try:
        if dt_string.endswith("Z"):
            return datetime.strptime(
                dt_string,
                "%Y%m%dT%H%M%SZ"
            )

        return datetime.strptime(
            dt_string,
            "%Y%m%dT%H%M%S"
        )

    except Exception:
        return None


def is_relevant_fixture(dtstart_string):
    """
    Keep fixtures from:
    - previous 30 days
    - next 12 months
    """

    event_date = parse_datetime(dtstart_string)

    if event_date is None:
        return False

    now = datetime.utcnow()

    earliest = now - timedelta(days=30)
    latest = now + timedelta(days=365)

    return earliest <= event_date <= latest


def classify(summary, location):
    """Add HOME/AWAY markers and competition type."""

    summary_lower = summary.lower()

    competition = ""

    if any(
        keyword in summary_lower
        for keyword in ["cup", "league cup", "carabao"]
    ):
        competition = "CUP"

    elif "friendly" in summary_lower:
        competition = "FRIENDLY"

    if location and (
        "pittodrie" in location.lower()
        or "aberdeen" in location.lower()
    ):
        venue = "HOME"
    else:
        venue = "AWAY"

    if competition:
        return f"[{venue} - {competition}] {summary}"

    return f"[{venue}] {summary}"


def load_json(filename):

    if not os.path.exists(filename):
        return {}

    try:

        with open(
            filename,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception as e:

        print(
            f"Warning loading {filename}: {e}"
        )

        return {}


def save_json(filename, data):

    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            data,
            f,
            indent=2
        )


def fetch_scores_from_afc_website():
    """
    Optional score enrichment.
    Failure should never stop the run.
    """

    print("  → Fetching results")

    try:

        response = session.get(
            AFC_RESULTS_URL,
            timeout=20
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.content,
            "html.parser"
        )

        text = soup.get_text(
            " ",
            strip=True
        )

        scores = {}

        matches = re.findall(
            r"Aberdeen.*?(\d+)\s*[-–]\s*(\d+)",
            text,
            re.IGNORECASE
        )

        for idx, score in enumerate(matches):

            scores[
                f"score_{idx}"
            ] = f"{score[0]}-{score[1]}"

        print(
            f"    Found {len(scores)} score entries"
        )

        return scores

    except Exception as e:

        print(
            f"    Warning: score scrape failed: {e}"
        )

        return {}


def fetch_from_ics_source():
    """Download fixture list from ICS source."""

    print(
        f"  → Downloading fixtures from {SOURCE_URL}"
    )

    try:

        response = session.get(
            SOURCE_URL,
            timeout=20
        )

        response.raise_for_status()

        events = []
        event = {}

        for line in response.text.splitlines():

            line = line.strip()

            if line == "BEGIN:VEVENT":

                event = {}

            elif line == "END:VEVENT":

                if event.get("DTSTART"):
                    events.append(event)

                event = {}

            elif ":" in line:

                key, value = line.split(
                    ":",
                    1
                )

                event[key.strip()] = value.strip()

        print(
            f"    Found {len(events)} fixtures"
        )

        return events

    except Exception as e:

        print(
            f"    Download failed: {e}"
        )

        return []


def fetch_from_afc_fixtures_page():
    """
    Optional AFC scraper.
    Returns [] if unavailable.
    """

    print("  → Attempting AFC fixture scrape")

    try:

        response = session.get(
            AFC_FIXTURES_URL,
            timeout=20
        )

        response.raise_for_status()

        print(
            "    AFC fixture page reachable"
        )

        return []

    except Exception as e:

        print(
            f"    AFC scraper unavailable: {e}"
        )

        return []


def get_score_for_match(
    summary,
    dtstart,
    scores_cache
):
    """
    Placeholder for future score matching.
    """

    event_date = parse_datetime(dtstart)

    if event_date is None:
        return summary

    if event_date > datetime.utcnow():
        return summary

    return summary


def deduplicate_events(events):

    unique = {}

    for event in events:

        summary = (
            event.get(
                "SUMMARY",
                ""
            )
            .strip()
            .lower()
        )

        dtstart = (
            event.get(
                "DTSTART",
                ""
            )
            .strip()
        )

        key = f"{summary}|{dtstart}"

        if key not in unique:
            unique[key] = event

    return list(unique.values())


def build_calendar(events):

    calendar = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Aberdeen FC//Operations Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Aberdeen FC Fixtures",
        "X-WR-TIMEZONE:UTC",
        f"X-WR-CALDESC:{len(events)} Aberdeen FC fixtures",
        "X-PUBLISHED-TTL:PT24H",
        "REFRESH-INTERVAL;VALUE=DURATION:PT24H"
    ]

    for event in events:

        calendar.append(
            "BEGIN:VEVENT"
        )

        calendar.append(
            f"UID:{event['uid']}"
        )

        calendar.append(
            "DTSTAMP:"
            + datetime.utcnow().strftime(
                "%Y%m%dT%H%M%SZ"
            )
        )

        calendar.append(
            f"DTSTART:{event['dtstart']}"
        )

        if event.get("dtend"):

            calendar.append(
                f"DTEND:{event['dtend']}"
            )

        else:

            start_dt = parse_datetime(
                event["dtstart"]
            )

            if start_dt:

                end_dt = (
                    start_dt
                    + timedelta(hours=2)
                )

                calendar.append(
                    "DTEND:"
                    + end_dt.strftime(
                        "%Y%m%dT%H%M%SZ"
                    )
                )

        calendar.append(
            f"SUMMARY:{ics_escape(event['summary'])}"
        )

        calendar.append(
            f"LOCATION:{ics_escape(event['location'])}"
        )

        calendar.append(
            f"DESCRIPTION:{ics_escape(event['description'])}"
        )

        calendar.append(
            "STATUS:CONFIRMED"
        )

        calendar.append(
            "END:VEVENT"
        )

    calendar.append(
        "END:VCALENDAR"
    )

    return "\n".join(calendar)


def main():

    print("\n" + "=" * 70)
    print("ABERDEEN FC CALENDAR UPDATE")
    print("=" * 70)

    print("\n[1/5] Loading scores")

    scores_cache = load_json(
        SCORES_FILE
    )

    latest_scores = (
        fetch_scores_from_afc_website()
    )

    if latest_scores:

        scores_cache.update(
            latest_scores
        )

        save_json(
            SCORES_FILE,
            scores_cache
        )

    print("\n[2/5] Fetching fixtures")

    all_events = []

    all_events.extend(
        fetch_from_ics_source()
    )

    try:

        all_events.extend(
            fetch_from_afc_fixtures_page()
        )

    except Exception as e:

        print(
            f"Warning: AFC scrape skipped: {e}"
        )

    cached = load_json(
        FIXTURES_CACHE_FILE
    )

    if cached.get("events"):

        all_events.extend(
            cached["events"]
        )

    print("\n[3/5] Deduplicating")

    all_events = deduplicate_events(
        all_events
    )

    print(
        f"Unique events: {len(all_events)}"
    )

    print("\n[4/5] Processing fixtures")

    processed = []

    for event in all_events:

        dtstart = event.get(
            "DTSTART"
        )

        if (
            not dtstart
            or not is_relevant_fixture(
                dtstart
            )
        ):
            continue

        summary = classify(
            event.get(
                "SUMMARY",
                "Aberdeen Fixture"
            ),
            event.get(
                "LOCATION",
                ""
            )
        )

        summary = get_score_for_match(
            summary,
            dtstart,
            scores_cache
        )

        uid = event.get(
            "UID"
        )

        if not uid:

            uid = (
                f"{dtstart}-"
                f"{summary.replace(' ', '')}"
                "@aberdeenfc"
            )

        processed.append(
            {
                "uid": uid,
                "summary": summary,
                "dtstart": dtstart,
                "dtend": event.get(
                    "DTEND"
                ),
                "location": event.get(
                    "LOCATION",
                    ""
                ),
                "description": event.get(
                    "DESCRIPTION",
                    "Aberdeen FC Fixture"
                )
            }
        )

    processed.sort(
        key=lambda x:
        parse_datetime(
            x["dtstart"]
        )
        or datetime.max
    )

    save_json(
        FIXTURES_CACHE_FILE,
        {
            "cached_at":
            datetime.utcnow().isoformat(),
            "total_fixtures":
            len(processed),
            "events":
            [
                {
                    "SUMMARY":
                    e["summary"],
                    "DTSTART":
                    e["dtstart"],
                    "DTEND":
                    e["dtend"],
                    "LOCATION":
                    e["location"],
                    "UID":
                    e["uid"],
                    "DESCRIPTION":
                    e["description"]
                }
                for e in processed
            ]
        }
    )

    print("\n[5/5] Building calendar")

    calendar_text = build_calendar(
        processed
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            calendar_text
        )

    print()
    print("=" * 70)
    print("✅ CALENDAR UPDATED")
    print("=" * 70)
    print(f"Fixtures: {len(processed)}")
    print(f"Output: {OUTPUT_FILE}")
    print("=" * 70)


if __name__ == "__main__":
    main()
