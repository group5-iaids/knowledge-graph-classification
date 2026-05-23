"""
Build a binary sparse feature matrix from extracted entity properties.

Rows   = entities in the same order as data/raw/entities_filtered.csv
Columns = all unique property codes found in entity_properties.json, sorted for
          reproducibility (P31 was already excluded during extraction).

Outputs
-------
data/processed/feature_matrix.npz         — scipy CSR sparse matrix (binary, uint8)
data/processed/feature_matrix_columns.json — ordered list of P-codes (column names)
data/processed/labels.csv                 — entity_id, class_name, class_qcode
                                            in the same row order as the matrix
"""

import argparse
import csv
import json
import os
import sys

import numpy as np
import scipy.sparse as sp

ENTITIES_CSV     = os.path.join("data", "raw", "entities_filtered.csv")
PROPS_JSON       = os.path.join("data", "raw", "entity_properties.json")
OUT_MATRIX       = os.path.join("data", "processed", "feature_matrix.npz")
OUT_COLUMNS      = os.path.join("data", "processed", "feature_matrix_columns.json")
OUT_LABELS       = os.path.join("data", "processed", "labels.csv")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build a binary sparse feature matrix from entity properties."
    )
    parser.add_argument(
        "--entities",
        default=ENTITIES_CSV,
        help=f"Filtered entities CSV (default: {ENTITIES_CSV})",
    )
    parser.add_argument(
        "--props",
        default=PROPS_JSON,
        help=f"Entity properties JSON (default: {PROPS_JSON})",
    )
    parser.add_argument(
        "--out-matrix",
        default=OUT_MATRIX,
        help=f"Output path for .npz matrix (default: {OUT_MATRIX})",
    )
    parser.add_argument(
        "--out-columns",
        default=OUT_COLUMNS,
        help=f"Output path for column names JSON (default: {OUT_COLUMNS})",
    )
    parser.add_argument(
        "--out-labels",
        default=OUT_LABELS,
        help=f"Output path for labels CSV (default: {OUT_LABELS})",
    )
    return parser.parse_args()


def load_entities(csv_path):
    """
    Read entities_filtered.csv and return an ordered list of
    (entity_id, class_qcode, class_name) tuples.

    The order here becomes the canonical row order of the feature matrix.
    """
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            rows.append((row["entity_id"], row["class_qcode"], row["class_name"]))
    return rows


def load_properties(json_path):
    """
    Load entity_properties.json.
    Returns a dict: {entity_id: list_of_property_codes}.
    """
    with open(json_path, encoding="utf-8") as fh:
        return json.load(fh)


def build_vocabulary(props, entity_order):
    """
    Collect all unique property codes that appear for our entities and sort them.

    Sorting gives a stable column order across runs. P31 must not appear here
    because it was excluded during extraction — we assert this as a safeguard.
    """
    all_props = set()
    entity_ids = {eid for eid, _, _ in entity_order}
    for eid in entity_ids:
        all_props.update(props.get(eid, []))

    assert "P31" not in all_props, (
        "P31 (instance-of) found in property vocabulary — "
        "it must be excluded from features because it encodes the label."
    )

    return sorted(all_props)


def build_csr_matrix(entity_order, props, vocab):
    """
    Build a binary CSR matrix using COO format as an intermediate step.

    COO (coordinate format) lets us collect (row, col) pairs cheaply before
    converting to CSR in one shot — much faster than setting elements in a
    lil_matrix one by one.

    Shape: (n_entities, n_properties)
    Value: 1 where entity has property, 0 otherwise.
    dtype: uint8 — sufficient for binary values, halves memory vs float32.
    """
    prop_to_idx = {p: i for i, p in enumerate(vocab)}
    n_entities  = len(entity_order)
    n_props     = len(vocab)

    row_indices = []
    col_indices = []

    for row_idx, (entity_id, _, _) in enumerate(entity_order):
        for prop in props.get(entity_id, []):
            col_idx = prop_to_idx.get(prop)
            if col_idx is not None:
                row_indices.append(row_idx)
                col_indices.append(col_idx)

    data = np.ones(len(row_indices), dtype=np.uint8)
    matrix = sp.coo_matrix(
        (data, (row_indices, col_indices)),
        shape=(n_entities, n_props),
    ).tocsr()

    return matrix


def print_stats(matrix, out_matrix):
    """Report matrix shape, density, and on-disk / in-memory sizes."""
    n_rows, n_cols = matrix.shape
    nnz     = matrix.nnz
    density = nnz / (n_rows * n_cols) * 100

    # In-memory: data + indices + indptr arrays
    mem_bytes = (
        matrix.data.nbytes
        + matrix.indices.nbytes
        + matrix.indptr.nbytes
    )

    file_bytes = os.path.getsize(out_matrix)

    print("\n--- Feature Matrix Statistics ---")
    print(f"  Shape                : {n_rows:,} rows × {n_cols:,} columns")
    print(f"  Non-zero entries     : {nnz:,}")
    print(f"  Density              : {density:.4f}%  (matrix is {100 - density:.4f}% sparse)")
    print(f"  In-memory size (CSR) : {mem_bytes / 1024 / 1024:.2f} MB")
    print(f"  On-disk size (.npz)  : {file_bytes / 1024 / 1024:.2f} MB")


def save_outputs(matrix, vocab, entity_order, args):
    """Write all three output files, creating parent directories as needed."""
    for path in (args.out_matrix, args.out_columns, args.out_labels):
        os.makedirs(os.path.dirname(path), exist_ok=True)

    # 1. Sparse matrix
    sp.save_npz(args.out_matrix, matrix)
    print(f"Saved matrix  : {args.out_matrix}")

    # 2. Column names (property codes in column order)
    with open(args.out_columns, "w", encoding="utf-8") as fh:
        json.dump(vocab, fh, separators=(",", ":"))
    print(f"Saved columns : {args.out_columns}")

    # 3. Labels CSV in the same row order as the matrix
    with open(args.out_labels, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["entity_id", "class_name", "class_qcode"])
        for entity_id, class_qcode, class_name in entity_order:
            writer.writerow([entity_id, class_name, class_qcode])
    print(f"Saved labels  : {args.out_labels}")


def main():
    args = parse_args()

    for label, path in [("entities CSV", args.entities), ("properties JSON", args.props)]:
        if not os.path.exists(path):
            print(f"ERROR: {label} not found: {path}", file=sys.stderr)
            sys.exit(1)

    # Step 1: load entity order (this defines the row order of the matrix)
    print(f"Loading entities from : {args.entities}")
    entity_order = load_entities(args.entities)
    print(f"  {len(entity_order):,} entities")

    # Step 2: load property sets
    print(f"Loading properties from: {args.props}")
    props = load_properties(args.props)
    print(f"  {len(props):,} entities with property data")

    # Step 3: build sorted property vocabulary (= column names)
    print("\nBuilding property vocabulary...")
    vocab = build_vocabulary(props, entity_order)
    print(f"  {len(vocab):,} unique properties")

    # Step 4: build COO then CSR sparse matrix
    print("\nBuilding sparse matrix (COO → CSR)...")
    matrix = build_csr_matrix(entity_order, props, vocab)

    # Sanity checks — these will raise AssertionError if something went wrong
    assert matrix.shape[0] == len(entity_order), (
        f"Row count mismatch: matrix has {matrix.shape[0]} rows "
        f"but entity list has {len(entity_order)}"
    )
    assert matrix.shape[1] == len(vocab), (
        f"Column count mismatch: matrix has {matrix.shape[1]} columns "
        f"but vocabulary has {len(vocab)}"
    )
    print(f"  Matrix shape: {matrix.shape[0]:,} × {matrix.shape[1]:,}  ✓ assertions passed")

    # Step 5: save
    print()
    save_outputs(matrix, vocab, entity_order, args)

    # Step 6: report
    print_stats(matrix, args.out_matrix)


if __name__ == "__main__":
    main()
