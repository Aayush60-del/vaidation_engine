import json
import sys
import time
from pathlib import Path
from urllib import parse, request, error

import pandas as pd
from rapidfuzz import fuzz

from utils.helpers import coerce_float, haversine_km


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

DATA_FOLDER = Path(__file__).resolve().parents[1] / "Final_states_data 1 (1)" / "Final_states_data"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
RADII_TO_TRY = (500, 1000, 2000)
CEMETERY_TYPES = {"cemetery", "grave_yard", "burial_ground"}


def main():
    csv_file = sorted(DATA_FOLDER.glob("*.csv"))[0]
    df = pd.read_csv(csv_file).fillna("").head(5)
    records = df.to_dict(orient="records")

    print(f"CSV FILE: {csv_file}")
    print("\nSAMPLE RECORDS:")
    for index, record in enumerate(records, start=1):
        print({
            "record": index,
            "name": record.get("name"),
            "latitude": record.get("latitude"),
            "longitude": record.get("longitude"),
            "state": record.get("state"),
            "county": record.get("county"),
            "city": record.get("city"),
            "type": record.get("type"),
        })

    reports = []
    for index, record in enumerate(records, start=1):
        if index > 1:
            time.sleep(3)

        lat = coerce_float(record.get("latitude"))
        lon = coerce_float(record.get("longitude"))
        raw_response = None
        parsed = {"elements": []}
        api_error = None

        if lat is None or lon is None:
            api_error = "Invalid CSV coordinates; Overpass query skipped."
        else:
            raw_response, parsed, api_error = fetch_overpass(lat, lon, radius=500)

        print(f"\nRAW OSM RESPONSE RECORD {index}:")
        print(raw_response if raw_response is not None else api_error)

        elements = parsed.get("elements", []) if isinstance(parsed, dict) else []
        best = choose_best_osm_match(record, elements, lat, lon)
        radius_results = {500: bool(elements)}

        if not elements and lat is not None and lon is not None:
            for radius in (1000, 2000):
                time.sleep(3)
                radius_raw, radius_parsed, radius_error = fetch_overpass(lat, lon, radius=radius)
                radius_elements = radius_parsed.get("elements", []) if isinstance(radius_parsed, dict) else []
                radius_results[radius] = bool(radius_elements)
                print(f"\nRAW OSM RESPONSE RECORD {index} RADIUS {radius}m:")
                print(radius_raw if radius_raw is not None else radius_error)
                if radius_elements and best is None:
                    best = choose_best_osm_match(record, radius_elements, lat, lon)

        comparison = compare_record(record, best, lat, lon)
        reports.append({
            "index": index,
            "record": record,
            "best": best,
            "comparison": comparison,
            "api_error": api_error,
            "radius_results": radius_results,
            "csv_lat": lat,
            "csv_lon": lon,
            "csv_lat_type": type(record.get("latitude")).__name__,
            "csv_lon_type": type(record.get("longitude")).__name__,
        })

        print_report(reports[-1])

    print_summary(reports)


def fetch_overpass(lat, lon, radius):
    query = build_query(lat, lon, radius)
    data = parse.urlencode({"data": query}).encode("utf-8")
    req = request.Request(
        OVERPASS_URL,
        data=data,
        headers={"User-Agent": "validation-engine-osm-qa/1.0"},
        method="POST",
    )

    for attempt in range(2):
        try:
            with request.urlopen(req, timeout=45) as response:
                raw = response.read().decode("utf-8")
                return raw, json.loads(raw), None
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            if exc.code == 429 and attempt == 0:
                print("Overpass rate limited; waiting 10 seconds and retrying.")
                time.sleep(10)
                continue
            return raw, {"elements": []}, f"HTTP {exc.code}: {raw}"
        except Exception as exc:
            return None, {"elements": []}, str(exc)

    return None, {"elements": []}, "Overpass retry failed."


def build_query(lat, lon, radius):
    return f"""[out:json][timeout:30];
(
  node["amenity"="grave_yard"](around:{radius},{lat},{lon});
  way["amenity"="grave_yard"](around:{radius},{lat},{lon});
  node["landuse"="cemetery"](around:{radius},{lat},{lon});
  way["landuse"="cemetery"](around:{radius},{lat},{lon});
  relation["landuse"="cemetery"](around:{radius},{lat},{lon});
);
out body;"""


def choose_best_osm_match(record, elements, csv_lat, csv_lon):
    if not elements:
        return None

    scored = []
    for element in elements:
        item = extract_osm_element(element)
        name_score = fuzz.token_sort_ratio(str(record.get("name") or ""), item["osm_name"] or "")
        distance_m = None
        if item["osm_lat"] is not None and item["osm_lon"] is not None and csv_lat is not None and csv_lon is not None:
            distance_m = haversine_km(csv_lat, csv_lon, item["osm_lat"], item["osm_lon"]) * 1000
        distance_score = 0 if distance_m is None else max(0, 100 - distance_m)
        scored.append((name_score, distance_score, item))

    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return scored[0][2]


def extract_osm_element(element):
    tags = element.get("tags", {}) if isinstance(element.get("tags"), dict) else {}
    osm_type = tags.get("amenity") or tags.get("landuse") or tags.get("historic") or tags.get("cemetery")
    return {
        "osm_id": element.get("id"),
        "osm_name": tags.get("name"),
        "osm_lat": coerce_float(element.get("lat")),
        "osm_lon": coerce_float(element.get("lon")),
        "osm_type": osm_type,
        "element_type": element.get("type"),
        "tags": tags,
    }


def compare_record(record, best, csv_lat, csv_lon):
    if best is None:
        return {
            "found": False,
            "name_score": 0,
            "name_pass": False,
            "distance_m": None,
            "location_pass": False,
            "type_pass": False,
            "result": "NOT VERIFIED",
            "reason": "No cemetery object found in Overpass response.",
        }

    csv_name = str(record.get("name") or "")
    osm_name = best.get("osm_name") or ""
    name_score = fuzz.token_sort_ratio(csv_name, osm_name) if osm_name else 0
    name_pass = name_score >= 70

    distance_m = None
    if best.get("osm_lat") is not None and best.get("osm_lon") is not None and csv_lat is not None and csv_lon is not None:
        distance_m = haversine_km(csv_lat, csv_lon, best["osm_lat"], best["osm_lon"]) * 1000
    location_pass = distance_m is not None and distance_m <= 500

    csv_type_text = str(record.get("type") or "").strip().lower()
    osm_type_text = str(best.get("osm_type") or "").strip().lower()
    csv_indicates_cemetery = any(value in csv_type_text for value in CEMETERY_TYPES) or "cemeter" in csv_type_text
    osm_indicates_cemetery = osm_type_text in {"cemetery", "grave_yard", "yes"}
    type_pass = csv_indicates_cemetery and osm_indicates_cemetery

    passed = sum([name_pass, location_pass, type_pass])
    if passed == 3:
        result = "VERIFIED"
        reason = "Name, location, and cemetery type all passed."
    elif passed > 0:
        result = "PARTIAL"
        reason = "At least one comparison passed, but not all verification checks passed."
    else:
        result = "NOT VERIFIED"
        reason = "OSM object was found but name, location, and type checks did not pass."

    return {
        "found": True,
        "name_score": round(name_score, 2),
        "name_pass": name_pass,
        "distance_m": distance_m,
        "location_pass": location_pass,
        "type_pass": type_pass,
        "result": result,
        "reason": reason,
    }


def print_report(report):
    record = report["record"]
    best = report["best"]
    comparison = report["comparison"]
    distance_text = "not available" if comparison["distance_m"] is None else f"{round(comparison['distance_m'])}m"
    distance_icon = "✅" if comparison["location_pass"] else "❌"
    name_icon = "✅" if comparison["name_pass"] else "❌"
    type_icon = "✅" if comparison["type_pass"] else "❌"
    result_icon = {"VERIFIED": "✅", "PARTIAL": "⚠️", "NOT VERIFIED": "❌"}[comparison["result"]]

    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(f"RECORD {report['index']}: {record.get('name')}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
    print("CSV DATA:")
    print(f"  Name      : {record.get('name')}")
    print(f"  Lat/Lon   : {record.get('latitude')}, {record.get('longitude')}")
    print(f"  State     : {record.get('state')}")
    print(f"  County    : {record.get('county')}")
    print(f"  City      : {record.get('city')}")
    print(f"  Type      : {record.get('type')}")
    print("\nOSM RESPONSE:")
    print(f"  Found     : {'YES' if comparison['found'] else 'NO'}")
    print(f"  OSM Name  : {best.get('osm_name') if best else 'not found'}")
    print(f"  OSM Lat   : {best.get('osm_lat') if best else 'not found'}")
    print(f"  OSM Lon   : {best.get('osm_lon') if best else 'not found'}")
    print(f"  OSM Type  : {best.get('osm_type') if best else 'not found'}")
    print(f"  OSM ID    : {best.get('osm_id') if best else 'not found'}")
    print("\nCOMPARISON:")
    print(f"  Name Match    : {comparison['name_score']}/100 {name_icon}")
    print(f"  Distance      : {distance_text} {distance_icon}")
    print(f"  Type Match    : {type_icon}")
    print(f"\nRESULT: {result_icon} {comparison['result']}")
    print(f"\nREASON: {comparison['reason']}")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")


def print_summary(reports):
    total = len(reports)
    found = sum(1 for report in reports if report["comparison"]["found"])
    name_pass = sum(1 for report in reports if report["comparison"]["name_pass"])
    location_pass = sum(1 for report in reports if report["comparison"]["location_pass"])
    full = sum(1 for report in reports if report["comparison"]["result"] == "VERIFIED")

    print("\nBUG CHECKS")
    print("BUG CHECK 1 — Radius")
    print("  Current code radius: no Overpass radius; Nominatim reverse zoom=14 and search query have no radius.")
    for report in reports:
        print(f"  Record {report['index']} radius results: {report['radius_results']}")

    print("BUG CHECK 2 — Query Tags")
    print("  Current code searches Nominatim text/category/type/display_name, not Overpass tags.")
    print("  Trust/ambiguity only recognize amenity=grave_yard and landuse=cemetery.")
    print('  Missing tags to add if Overpass is adopted: historic=cemetery, cemetery=yes.')

    print("BUG CHECK 3 — Name Comparison")
    print("  Current Nominatim code uses substring matching, not fuzzy matching; no fuzzy threshold exists.")
    print("  Test fuzzy scores:", [report["comparison"]["name_score"] for report in reports])

    print("BUG CHECK 4 — No Name in OSM")
    print("  Current Nominatim search requires a name/display_name match; unnamed cemetery objects would not pass search_match.")

    print("BUG CHECK 5 — API Timeout / Error")
    errors = [report["api_error"] for report in reports if report["api_error"]]
    print(f"  Overpass errors/timeouts: {errors or 'none'}")
    print("  Current Nominatim code logs and returns None; it does not retry failures.")

    print("BUG CHECK 6 — String vs Float coordinates")
    print("  CSV coordinate Python types:", [
        (report["csv_lat_type"], report["csv_lon_type"]) for report in reports
    ])
    print("  Test runner coerced coordinates with utils.helpers.coerce_float before querying.")
    print("  Current validation code also coerces with coerce_float.")

    print("\nOSM VERIFICATION TEST SUMMARY")
    print("══════════════════════════════")
    print(f"Total records tested  : {total}")
    print(f"OSM found             : {found}/{total}")
    print(f"Name match passed     : {name_pass}/{total}")
    print(f"Location match passed : {location_pass}/{total}")
    print(f"Full verification     : {full}/{total}")
    print("\nBUGS FOUND IN CURRENT OSM CODE:")
    bugs = summarize_bugs(reports)
    for index, bug in enumerate(bugs, start=1):
        print(f"{index}. {bug}")

    if full == total:
        verdict = "✅ OSM working correctly"
    elif found:
        verdict = "⚠️ OSM partially working"
    else:
        verdict = "❌ OSM broken — needs fix"
    print("\nVERDICT:")
    print(verdict)


def summarize_bugs(reports):
    bugs = [
        "No Overpass verification exists in current code; Nominatim search/reverse is used instead → add a dedicated Overpass client if tag/radius verification is required.",
        "No retry exists for current Nominatim API failures → add retry/backoff for timeout and 429 responses.",
        "Current Nominatim name comparison is substring-only, not fuzzy → use rapidfuzz token_sort_ratio with a threshold such as 70.",
        "Unnamed OSM cemetery objects cannot pass current search_match → allow location/type match to verify when a cemetery object exists nearby.",
        "Current trust/ambiguity tag support misses historic=cemetery and cemetery=yes → include these tags in OSM tag checks.",
    ]

    if any(not report["radius_results"].get(500) and any(report["radius_results"].get(radius) for radius in (1000, 2000)) for report in reports):
        bugs.append("A larger radius found objects when 500m did not → make radius configurable or try fallback radii.")

    if any(report["comparison"]["found"] and not report["comparison"]["location_pass"] for report in reports):
        bugs.append("Some Overpass results lack node coordinates or are outside 500m → use 'out center;' for ways/relations or compute geometry centers.")

    return bugs


if __name__ == "__main__":
    main()
