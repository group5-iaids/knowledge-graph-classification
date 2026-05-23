"""
Extract property codes for each filtered entity from the raw Wikidata5m triples.

Streams wikidata5m_all_triplet.txt line-by-line — the file is multi-GB so it is
never fully loaded into RAM. For each triple where the subject is one of our 10k
entities and the predicate is not P31 (instance-of, i.e. the label), we record
the (entity_id, predicate) pair.

Output: data/raw/entity_properties.json
Format: {"Q123": ["P21", "P569", ...], ...}  (lists are sorted for reproducibility)
"""

import argparse
import csv
import json
import os
import random
import sys

random.seed(42)  # required for project-wide reproducibility

ENTITIES_CSV = os.path.join("data", "raw", "entities_filtered.csv")
OUTPUT_JSON = os.path.join("data", "raw", "entity_properties.json")

# P31 is "instance of" — it encodes the class label, so it must not appear as a feature
LABEL_PREDICATE = "P31"
PROGRESS_INTERVAL = 5_000_000  # print a progress line every N lines


def parse_args():
    parser = argparse.ArgumentParser(
        description="Extract property codes for filtered entities from Wikidata5m triples."
    )
    parser.add_argument(
        "--input",
        default="wikidata5m_all_triplet.txt",
        help="Path to raw triples file (default: wikidata5m_all_triplet.txt)",
    )
    parser.add_argument(
        "--entities",
        default=ENTITIES_CSV,
        help=f"Path to filtered entities CSV (default: {ENTITIES_CSV})",
    )
    parser.add_argument(
        "--output",
        default=OUTPUT_JSON,
        help=f"Path for output JSON (default: {OUTPUT_JSON})",
    )
    return parser.parse_args()


def load_entity_set(csv_path):
    """
    Load entity IDs from the filtered CSV into a Python set for O(1) lookup.
    The CSV has columns: entity_id, class_qcode, class_name.
    """
    entity_ids = set()
    with open(csv_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            entity_ids.add(row["entity_id"])
    return entity_ids


def stream_properties(triples_path, entity_set):
    """
    Stream the triples file and build a property-code set per entity.

    Each line is tab-separated: subject <TAB> predicate <TAB> object.
    We skip:
      - lines not matching our 10k entities (subject not in entity_set)
      - P31 triples (that is the class label, not a feature)
      - malformed lines (wrong number of fields)

    encoding errors='replace' substitutes a replacement character (U+FFFD) for
    any byte sequences that are not valid UTF-8, so the stream never crashes.

    Returns: dict mapping entity_id -> set of property codes
    """
    # Pre-initialise every entity so entities with zero matches still appear in output
    props = {eid: set() for eid in entity_set}
    line_count = 0
    match_count = 0

    with open(triples_path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line_count += 1

            if line_count % PROGRESS_INTERVAL == 0:
                print(
                    f"  ... {line_count:,} lines read, "
                    f"{match_count:,} property assignments collected"
                )

            parts = line.rstrip("\n").split("\t")
            if len(parts) != 3:
                continue  # skip malformed / empty lines

            subject, predicate, _ = parts

            # Ignore triples whose subject is not in our filtered entity set
            if subject not in entity_set:
                continue

            # Exclude the label predicate — using it as a feature would leak the target
            if predicate == LABEL_PREDICATE:
                continue

            props[subject].add(predicate)
            match_count += 1

    print(
        f"\n  Done: {line_count:,} lines read | "
        f"{match_count:,} property assignments kept"
    )
    return props


def print_stats(props):
    """Print summary statistics about the extracted property sets."""
    counts = [len(v) for v in props.values()]
    all_props = set()
    for codes in props.values():
        all_props.update(codes)

    total_entities = len(counts)
    entities_with_props = sum(1 for c in counts if c > 0)
    avg = sum(counts) / total_entities if total_entities else 0
    min_count = min(counts) if counts else 0
    max_count = max(counts) if counts else 0

    print("\n--- Property Extraction Statistics ---")
    print(f"  Entities processed           : {total_entities:,}")
    print(f"  Entities with >= 1 property  : {entities_with_props:,}")
    print(f"  Entities with 0 properties   : {total_entities - entities_with_props:,}")
    print(f"  Unique property codes found  : {len(all_props):,}")
    print(f"  Avg properties per entity    : {avg:.1f}")
    print(f"  Min properties (per entity)  : {min_count}")
    print(f"  Max properties (per entity)  : {max_count}")


def save_json(props, output_path):
    """
    Serialize property sets to sorted lists and write compact JSON.
    Sets are sorted so the file is deterministic across runs.
    """
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    serializable = {eid: sorted(codes) for eid, codes in props.items()}
    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(serializable, fh, separators=(",", ":"))
    size_mb = os.path.getsize(output_path) / 1024 / 1024
    print(f"\nSaved: {output_path}  ({size_mb:.1f} MB)")


def main():
    args = parse_args()

    # Validate that required input files exist before starting the long stream
    for label, path in [("triples file", args.input), ("entities CSV", args.entities)]:
        if not os.path.exists(path):
            print(f"ERROR: {label} not found: {path}", file=sys.stderr)
            sys.exit(1)

    # Step 1: build the lookup set of 10k entity IDs
    print(f"Loading entity set from: {args.entities}")
    entity_set = load_entity_set(args.entities)
    print(f"  {len(entity_set):,} entities loaded\n")

    # Step 2: single-pass stream over the multi-GB triples file
    print(f"Streaming triples from: {args.input}")
    print("This may take several minutes for multi-GB files...\n")
    props = stream_properties(args.input, entity_set)

    # Step 3: report statistics
    print_stats(props)

    # Step 4: persist results
    save_json(props, args.output)


if __name__ == "__main__":
    main()
