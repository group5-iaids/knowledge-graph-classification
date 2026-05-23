# Group 5B — Knowledge Graph Entity Classification

**Course:** IAIDS Even 2025/2026 — Universitas Indonesia
**Dataset:** Wikidata5m

---

## Dataset Download

The raw data files are **not included** in this repo (each is several GB). Download them manually from the official source and place them in the project root:

| File | Description | Link |
|------|-------------|------|
| `wikidata5m_all_triplet.txt` | All (head, relation, tail) triples | [https://deepgraphlearning.github.io/project/wikidata5m](https://deepgraphlearning.github.io/project/wikidata5m) |
| `wikidata5m_entity.txt` | Entity ID → label mapping | Same as above |
| `wikidata5m_relation.txt` | Relation ID → label mapping | Same as above |

After downloading, place all three `.txt` files in the **project root** (same level as `README.md`).

---

## Folder Structure

```
group assignment/
├── src/
│   └── filter_entities.py      # Task B: Wikidata5m filtering script
├── data/
│   └── raw/
│       └── entities_filtered.csv   # Output of filter_entities.py
├── Group5_B_Notebook.ipynb     # Main analysis notebook
├── .gitignore
└── README.md
```

---

## How to Run the Filtering Script

```bash
# Default (reads wikidata5m_all_triplet.txt from current directory)
python src/filter_entities.py

# Custom path
python src/filter_entities.py --input path/to/wikidata5m_all_triplet.txt
```

Output is saved to `data/raw/entities_filtered.csv`.

---

## Team Members

| No | Name | NPM | Role |
|----|------|-----|------|
| 1 | Gunata Prajna Putra Sakri | 2406453461 | |
| 2 | Melanton Gabriel Siregar | 2406365364 | |
| 3 | Muhammad Vegard Fathul Islam | 2406365332 | |
| 4 | Roben Joseph Buce Tambayong | 2406453594 | |

---

## Requirements

```
pandas
numpy
scipy
matplotlib
seaborn
scikit-learn
```

Install with:
```bash
pip install pandas numpy scipy matplotlib seaborn scikit-learn
```
