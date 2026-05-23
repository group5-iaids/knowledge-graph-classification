"""
Build human-readable name lookups for property codes and class Q-codes.

Alias file formats (both tab-separated, variable column count)
--------------------------------------------------------------
wikidata5m_relation.txt  — 825 lines, every line is a P-code:
    P834\ttrain depot\trailway depot\tdepot\trail yard
    col[0] = P-code
    col[1] = primary / most-common alias  ← what we store
    col[2..N] = additional aliases (ignored)

wikidata5m_entity.txt  — 4.8 M lines, every line is a Q-code:
    Q532\tvillage\t...
    same layout as above

Note on data quality: the entity file's first alias for several of our five
target classes is unreliable (Q5 → 'Huamn', Q571 → 'wikipedia books/sandbox').
We therefore use the canonical names that were already established in
filter_entities.py rather than trusting the alias file for class names.

Outputs
-------
data/raw/property_names.json  — {P-code: primary_alias}   (for Gunata's visualizations)
data/raw/class_names.json     — {Q-code: canonical_name}  (for the 5 target classes)
"""

import argparse
import json
import os
import sys

RELATIONS_FILE = "wikidata5m_relation.txt"
ENTITIES_FILE  = "wikidata5m_entity.txt"
OUT_PROPS      = os.path.join("data", "raw", "property_names.json")
OUT_CLASSES    = os.path.join("data", "raw", "class_names.json")

# Canonical class names — same source of truth as filter_entities.py.
# We do NOT derive these from the entity alias file because the first alias
# for some Q-codes is a misspelling or sandbox name (see module docstring).
TARGET_CLASSES = {
    "Q5":     "human",
    "Q571":   "book",
    "Q532":   "village",
    "Q16521": "taxon",
    "Q11424": "film",
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build property-name and class-name lookup dicts from Wikidata5m alias files."
    )
    parser.add_argument(
        "--relations",
        default=RELATIONS_FILE,
        help=f"Relation aliases file (default: {RELATIONS_FILE})",
    )
    parser.add_argument(
        "--entities",
        default=ENTITIES_FILE,
        help=f"Entity aliases file — only used for alias cross-check print (default: {ENTITIES_FILE})",
    )
    parser.add_argument(
        "--out-props",
        default=OUT_PROPS,
        help=f"Output path for property names JSON (default: {OUT_PROPS})",
    )
    parser.add_argument(
        "--out-classes",
        default=OUT_CLASSES,
        help=f"Output path for class names JSON (default: {OUT_CLASSES})",
    )
    return parser.parse_args()


def load_property_names(relations_path):
    """
    Read the relation aliases file and return {P-code: primary_alias}.

    Every line in this file starts with a P-code, so no prefix filtering is
    needed — but we assert it to catch unexpected file layout changes.
    Lines with no alias column (only the code) are stored with an empty string.
    Encoding errors are replaced with U+FFFD so the stream never crashes.
    """
    prop_names = {}
    skipped = 0

    with open(relations_path, encoding="utf-8", errors="replace") as fh:
        for lineno, line in enumerate(fh, start=1):
            parts = line.rstrip("\n").split("\t")

            if not parts[0].startswith("P"):
                # Unexpected: the relation file should only contain P-codes
                skipped += 1
                continue

            p_code = parts[0]
            # col[1] is the primary alias; fall back to empty string if missing
            primary_alias = parts[1].strip() if len(parts) > 1 else ""
            prop_names[p_code] = primary_alias

    if skipped:
        print(f"  WARNING: {skipped} lines skipped (did not start with 'P')")

    return prop_names


def show_entity_aliases(entities_path, target_qcodes):
    """
    Print raw aliases from the entity file for the target Q-codes so the user
    can see why we do NOT use them as canonical names.
    """
    remaining = set(target_qcodes)
    aliases_found = {}

    with open(entities_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if parts[0] in remaining:
                aliases_found[parts[0]] = parts[1:4]  # show first 3 aliases only
                remaining.discard(parts[0])
            if not remaining:
                break

    print("\n  Entity alias file — raw first aliases for target Q-codes:")
    print(f"  {'Q-code':<10} {'Alias[1]':<30} {'Alias[2]':<30} {'Alias[3]'}")
    print("  " + "-" * 85)
    for qcode in sorted(target_qcodes):
        raw = aliases_found.get(qcode, [])
        cols = [raw[i] if i < len(raw) else "" for i in range(3)]
        print(f"  {qcode:<10} {cols[0]:<30} {cols[1]:<30} {cols[2]}")
    print()
    print("  → Using hardcoded canonical names instead (see TARGET_CLASSES).")


def print_property_samples(prop_names, n=15):
    """Print n example P-code → name mappings."""
    print(f"\n  Sample property names ({n} entries):")
    print(f"  {'P-code':<10} {'Primary alias'}")
    print("  " + "-" * 50)
    for p_code, name in list(prop_names.items())[:n]:
        print(f"  {p_code:<10} {name}")


def save_json(data, path, label):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
    size_kb = os.path.getsize(path) / 1024
    print(f"Saved {label}: {path}  ({size_kb:.1f} KB, {len(data)} entries)")


def main():
    args = parse_args()

    for label, path in [("relations file", args.relations), ("entities file", args.entities)]:
        if not os.path.exists(path):
            print(f"ERROR: {label} not found: {path}", file=sys.stderr)
            sys.exit(1)

    # Step 1: build P-code → primary alias from the relation aliases file
    print(f"Reading property aliases from: {args.relations}")
    prop_names = load_property_names(args.relations)
    print(f"  {len(prop_names):,} property codes loaded")
    print_property_samples(prop_names, n=15)

    # Step 2: show raw entity aliases so the data quality issue is visible,
    #         then report which canonical names we actually store
    print(f"\nReading entity aliases from: {args.entities}")
    show_entity_aliases(args.entities, TARGET_CLASSES)

    print("  Canonical class names (stored in class_names.json):")
    for qcode, name in TARGET_CLASSES.items():
        print(f"    {qcode} → {name}")

    # Step 3: save both outputs
    print()
    save_json(prop_names, args.out_props, "property_names")
    save_json(TARGET_CLASSES, args.out_classes, "class_names   ")


if __name__ == "__main__":
    main()
