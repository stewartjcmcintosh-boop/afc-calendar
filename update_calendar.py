import requests
from datetime import datetime, timedelta
import json
import os
import re
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


def classify(summary, location):
    summary_lower = summary.lower()

    if any(x in summary_lower for x in ["cup", "carabao", "league cup"]):
        competition = "CUP"
    elif "friendly" in summary_lower:
        competition = "FRIENDLY"
    else:
        competition = None

    if location and (
        "pittodrie" in location.lower()
        or "aberdeen" in location.lower()
    ):
        ha = "HOME"
    else:
        ha = "AWAY"

    if competition:
        return f"[{ha} - {competition}] {summary}"

    return f"[{ha}] {summary}"


def parse_datetime(dt_string):
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


def is_within_12_months(dtstart_string):
    event_date = parse_datetime(dtstart_string)

    if event_date is None:
        return False

    now = datetime.utcnow()
    limit = now + timedelta(days=365)

    return now <= event_date <= limit


def load_json(filename):
    if not os.path.exists(filename):
        return {}

    try:
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception as e:
        print(f"Warning loading {filename}: {e}")
        return {}


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def fetch_scores_from_afc_website():

    print("  → Fetching match scores...")

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

        scores = {}

        text = soup.get_text(" ", strip=True)

        score_matches = re.findall(
            r"Aberdeen.*?(\d+)\s*[-–]\s*(\d+)",
            text,
            flags=re.IGNORECASE
        )

        for idx, score in enumerate(score_matches):
            scores[f"result_{idx}"] = (
                f"{score[0]}-{score[1]}"
            )

        print(
            f"    Found {len(scores)} score entries"
        )

        return scores

    except Exception as e:

        print(
            f"    Warning: score scrape failed: {e}"
        )

        return {}


def fetch_from_ics_source(url):

    print(f"  → Downloading {url}")

    try:

        response = session.get(
            url,
            timeout=20
        )

        response.raise_for_status()

        events = []
        block = {}

        for line in response.text.splitlines():

            line = line.strip()

            if line == "BEGIN:VEVENT":
                block = {}

            elif line == "END:VEVENT":

                if block.get("DTSTART"):
                    events.append(block)

                block = {}

            elif ":" in line:

                key, value = line.split(
                    ":",
                    1
                )

                block[key.strip()] = value.strip()

        print(
            f"    Found {len(events)} events"
        )

        return events

    except Exception as e:

        print(
            f"    Error downloading ICS: {e}"
        )

        return []


def fetch_from_afc_fixtures_page():

    print("  → Scraping AFC fixtures page")

    try:

        response = session.get(
            AFC_FIXTURES_URL,
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

        if "Aberdeen" not in text:
            return []

        return []

    except Exception as e:

        print(
            f"    Warning: AFC fixture scrape failed: {e}"
        )

        return []


def get_score_for_match(
    summary,
    dtstart_string,
    scores_cache
):

    event_date = parse_datetime(
        dtstart_string
    )

    if event_date is None:
        return summary

    if event_date > datetime.utcnow():
        return summary

    return summary


def deduplicate_events(event_list):

    unique = {}

    for event in event_list:

        summary = (
            event.get(
                "SUMMARY",
                ""
            )
            .lower()
            .strip()
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
        f"X-WR-CALDESC:{len(events)} Aberdeen FC fixtures"
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
            f"SUMMARY:{event['summary']}"
        )

        calendar.append(
            f"LOCATION:{event['location']}"
        )

        calendar.append(
            f"DESCRIPTION:{event['description']}"
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

    scores_cache = load_json(
        SCORES_FILE
    )

    new_scores = (
        fetch_scores_from_afc_website()
    )

    if new_scores:

        scores_cache.update(
            new_scores
        )

        save_json(
            SCORES_FILE,
            scores_cache
        )

    print("\nFetching fixtures")

    all_events = []

    ics_events = (
        fetch_from_ics_source(
            SOURCE_URL
        )
    )

    all_events.extend(
        ics_events
    )

    try:

        afc_events = (
            fetch_from_afc_fixtures_page()
        )

        all_events.extend(
            afc_events
        )

    except Exception as e:

        print(
            f"Warning: AFC source skipped: {e}"
        )

    cached = load_json(
        FIXTURES_CACHE_FILE
    )

    if cached.get("events"):

        all_events.extend(
            cached["events"]
        )

    all_events = (
        deduplicate_events(
            all_events
        )
    )

    print(
        f"Unique fixtures: {len(all_events)}"
    )

    processed = []

    for event in all_events:

        dtstart = event.get(
            "DTSTART"
        )

        if (
            not dtstart
            or not is_within_12_months(
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

        summary = (
            get_score_for_match(
                summary,
                dtstart,
                scores_cache
            )
        )

        processed.append(
            {
                "uid": event.get(
                    "UID",
                    summary.replace(
                        " ",
                        ""
                    )
                ),
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
        key=lambda x: x["dtstart"]
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

    calendar_text = (
        build_calendar(
            processed
        )
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:

        f.write(
            calendar_text
        )

    print(
        f"Calendar written: {OUTPUT_FILE}"
    )

    print(
        f"Fixtures: {len(processed)}"
    )

    print(
        "\n✅ Update complete"
    )


if __name__ == "__main__":
    main()
