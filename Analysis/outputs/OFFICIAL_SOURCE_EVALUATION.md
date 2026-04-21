# Official Station Source Evaluation

Run completed on 2026-04-03 for the Phase 1 source evaluation requested in
`COLLAB_LOG.md`.

## Recommendation

Use **Option A: TfL Unified API StopPoint endpoint** as the primary official
source for the accessibility variable.

Why this source won:

- It was directly accessible in practice and returned JSON successfully.
- Its scope matches the project definition exactly: Tube, DLR, Overground, and
  Elizabeth line.
- A hub-first deduplication rule produces a clean station-complex layer that is
  appropriate for nearest-station distance.
- WGS84 coordinates are easy to reproject to `EPSG:27700`.
- It is fresher and more operationally reliable than the London Datastore copy,
  while requiring much less ambiguous filtering than NaPTAN.

## Option A: TfL Unified API

- URL tested:
  `https://api.tfl.gov.uk/StopPoint/Mode/tube,dlr,overground,elizabeth-line`
- Accessibility:
  - Download worked successfully.
  - No registration wall blocked the request during testing.
- Filtering result:
  - Total returned stop points: `2,639`
  - Stop points inside the London LSOA study boundary: `2,342`
  - Station complexes after hub-first deduplication
    (`hubNaptanCode -> stationNaptan -> naptanId`): `385`
- Data quality:
  - Coordinates were present and valid.
  - Raw API records include platforms, entrances, access areas, and
    interchange-level records, so station-level deduplication is necessary.
  - `hubNaptanCode` successfully collapses multi-mode complexes like Bank into a
    single physical station complex.
- CRS:
  - Source coordinates are WGS84 lat/lon and were reprojected cleanly to
    `EPSG:27700`.

## Option B: NaPTAN

- URL tested:
  `https://naptan.api.dft.gov.uk/v1/access-nodes?dataFormat=csv`
- Accessibility:
  - Download worked successfully.
  - No registration required.
- Filtering result:
  - Bounding-box rows in the London area test: `30,543`
  - Rail-like rows after `StopType` filter (`MET`, `RLY`, `RSE`, `PLT`):
    `2,278`
  - Name-pattern counts within that filtered subset:
    - `Underground`: `854` rows, `273` unique names
    - `DLR`: `129` rows, `45` unique names
    - `Overground`: `1` row, `1` unique name
    - `Elizabeth`: `0`
    - `Rail Station`: `660` rows, `446` unique names
- Data quality:
  - Coordinates are present and NaPTAN includes BNG fields, which is a real
    strength.
  - In practice, the rapid-transit subset is hard to isolate cleanly: bbox and
    rail-type filters still pull in many non-target stations and tram stops.
  - Test samples included clearly unwanted names such as Addlestone, Ashtead,
    and multiple tram stops, which means a trustworthy final subset would
    require more bespoke filtering logic.
- CRS:
  - Strong on CRS because BNG is included directly.

## Option C: London Datastore

- Dataset page tested:
  `https://data.london.gov.uk/dataset/tfl-station-locations-2zmpy/`
- Accessibility:
  - The page exists, but direct resource discovery was poor.
  - CKAN API metadata for `TfL Station Locations` (`2zmpy`) returned
    `0` resources.
- Data quality:
  - CKAN metadata shows `metadata_modified = 2014-03-25T15:12:09`.
  - That age makes it much less suitable for the primary accessibility
    variable than the live TfL API.
- CRS:
  - Not a blocker in theory, but the stale and opaque resource situation makes
    this option weak overall.

## Decision

TfL API is the best balance of accessibility, scope correctness, and practical
cleaning effort. NaPTAN remains academically strong but was materially harder to
filter cleanly for this exact London rapid-transit definition. London Datastore
looks too stale and too opaque to justify as the main source.
