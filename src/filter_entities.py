"""
Task B: Filter Wikidata5m triples and sample entities per class.

Output: data/raw/entities_filtered.csv
Columns: entity_id, class_qcode, class_name
"""

import argparse
import csv
import os
import random
import sys


# Target classes: {Qcode: human-readable name}
TARGET_CLASSES = {
    "Q5":     "human",
    "Q571":   "book",
    "Q532":   "village",
    "Q16521": "taxon",
    "Q11424": "film",
}

SAMPLE_SIZE = 2000
PREDICATE = "P31"
OUTPUT_PATH = os.path.join("data", "raw", "entities_filtered.csv")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Filter Wikidata5m triples and sample entities per class."
    )
    parser.add_argument(
        "--input",
        default="wikidata5m_all_triplet.txt",
        help="Path to the raw triples file (default: wikidata5m_all_triplet.txt)",
    )
    return parser.parse_args()


def stream_filtered_entities(filepath):
    """
    Read the triples file line by line and collect entity IDs per class.

    Each line has three tab-separated fields: head, relation, tail.
    We keep lines where relation == P31 and tail is one of our target classes.
    Returns a dict: {class_qcode: [entity_id, ...]}
    """
    buckets = {qcode: [] for qcode in TARGET_CLASSES}

    with open(filepath, "r", encoding="utf-8") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 3:
                continue  # skip malformed lines

            head, relation, tail = parts

            # Keep only instance-of (P31) triples for our target classes
            if relation == PREDICATE and tail in TARGET_CLASSES:
                buckets[tail].append(head)

    return buckets


def sample_entities(buckets, seed=42):
    """
    Sample up to SAMPLE_SIZE entities per class using a fixed random seed.
    Warns when a class has fewer than SAMPLE_SIZE entities.
    Returns a list of (entity_id, class_qcode, class_name) tuples.
    """
    random.seed(seed)
    rows = []

    for qcode, entities in buckets.items():
        total_found = len(entities)
        class_name = TARGET_CLASSES[qcode]

        if total_found == 0:
            print(f"  WARNING: no entities found for {qcode} ({class_name})")
            continue

        if total_found < SAMPLE_SIZE:
            print(
                f"  WARNING: {qcode} ({class_name}) has only {total_found} entities "
                f"(fewer than {SAMPLE_SIZE}) — using all available."
            )
            sample = entities
        else:
            sample = random.sample(entities, SAMPLE_SIZE)

        for entity_id in sample:
            rows.append((entity_id, qcode, class_name))

    return rows


def save_csv(rows, output_path):
    """Write the sampled rows to a CSV file, creating parent dirs if needed."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["entity_id", "class_qcode", "class_name"])
        writer.writerows(rows)


def print_summary(buckets, rows):
    """Print a before/after summary table."""
    print("\n--- Summary ---")
    print(f"{'Class':<10} {'Name':<10} {'Found':>8} {'Sampled':>8}")
    print("-" * 42)

    sampled_counts = {}
    for entity_id, qcode, _ in rows:
        sampled_counts[qcode] = sampled_counts.get(qcode, 0) + 1

    for qcode, class_name in TARGET_CLASSES.items():
        found = len(buckets[qcode])
        sampled = sampled_counts.get(qcode, 0)
        print(f"{qcode:<10} {class_name:<10} {found:>8} {sampled:>8}")

    print(f"\nTotal rows saved: {len(rows)}")
    print(f"Output: {OUTPUT_PATH}")


def main():
    args = parse_args()

    if not os.path.exists(args.input):
        print(f"ERROR: Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    print(f"Reading triples from: {args.input}")
    print("Streaming file — this may take a few minutes for multi-GB files...\n")

    # Step 1: stream and filter
    buckets = stream_filtered_entities(args.input)

    # Step 2: sample per class
    rows = sample_entities(buckets, seed=42)

    # Step 3: save output
    save_csv(rows, OUTPUT_PATH)

    # Step 4: print summary
    print_summary(buckets, rows)


if __name__ == "__main__":
    main()
