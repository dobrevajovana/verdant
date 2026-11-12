"""Match your own terms (species, habitats, parameters, measurement names, ...) to the
ontologies you choose.

    import verdant
    matches = verdant.match("my_terms.csv", ontologies=["envo", "pato", "cf", "ncbitaxon"])
    verdant.save(matches, "my_terms.matches.csv")

Each term is searched in each chosen ontology on its own:

    exactMatch     a term's label or synonym is the name (plurals and 'sp.' aside)
    closeMatch     most of their words are shared (overlap >= 0.6)
    relatedMatch   some words are shared (overlap >= ``min_score``)

Up to ``per_ontology`` matches per term and ontology; when there is an exact one, only it.
In the taxonomies (NCBITaxon, GBIF) only exact names count: a near name is another taxon.
"""

from __future__ import annotations

import csv
import io
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from verdant.sources import TAXONOMIES, ontology_info, query_text, search

NAME_COLUMNS = ("name", "label", "term", "parameter", "measurement", "variable", "scientific_name", "scientificname",
                "species", "taxon", "habitat", "biome", "text", "value", "description")
ID_COLUMNS = ("id", "subject_id", "identifier", "accession", "code")
CATEGORY_COLUMNS = ("category", "group", "type", "kind", "field")
MATCH_TYPES = ("skos:exactMatch", "skos:closeMatch", "skos:relatedMatch")


# --- your terms ---------------------------------------------------------------------

def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text).lower()).strip("_")[:60] or "term"


def _pick(columns, wanted) -> str | None:
    low = {str(c).strip().lower(): c for c in columns}
    return next((low[w] for w in wanted if w in low), None)


def read_terms(data, column: str | None = None) -> list[dict]:
    """``[{"id", "label", "category"}]`` from a CSV / TSV / Excel file, a text file with one
    term per line, a list of strings or dicts, or a pandas DataFrame. The name column is
    found by its header (name, label, term, parameter, measurement, species, ...) or given
    with ``column=``; ``id`` and ``category`` columns are used when present. Repeats once."""
    if hasattr(data, "to_dict") and hasattr(data, "columns"):            # pandas DataFrame
        rows = data.fillna("").astype(str).to_dict("records")
    elif isinstance(data, (list, tuple)):
        rows = [r if isinstance(r, dict) else {"name": r} for r in data]
    else:
        path = Path(data)
        if path.suffix.lower() in (".xlsx", ".xls"):
            import pandas as pd
            rows = pd.read_excel(path, dtype=str).fillna("").to_dict("records")
        else:
            text = path.read_text(encoding="utf-8-sig")
            lines = [ln for ln in text.splitlines() if ln.strip() and not ln.startswith("#")]
            delim = "\t" if path.suffix.lower() in (".tsv", ".txt") or text.count("\t") > text.count(",") else ","
            first = lines[0] if lines else ""
            header = _pick(next(csv.reader([first], delimiter=delim)), NAME_COLUMNS + ID_COLUMNS) if lines else None
            if column is None and header is None and (delim not in first or path.suffix.lower() == ".txt"):
                rows = [{"name": ln.strip()} for ln in lines]                 # one term per line, no header
            else:
                rows = list(csv.DictReader(io.StringIO("\n".join(lines)), delimiter=delim))
    if not rows:
        return []
    cols = list(rows[0])
    id_col, cat_col = _pick(cols, ID_COLUMNS), _pick(cols, CATEGORY_COLUMNS)
    name_col = column or _pick(cols, NAME_COLUMNS)
    if name_col is None:      # the first column with words in it that is not the ID
        name_col = next((c for c in cols if c != id_col and any(re.search(r"[A-Za-z]{3}", str(r.get(c) or "")) for r in rows[:20])), None)
    if name_col is None or name_col not in cols:
        raise ValueError(f"No name column found; give one with column= (columns: {', '.join(map(str, cols))}).")
    out, seen = [], set()
    for r in rows:
        label = str(r.get(name_col) or "").strip()
        if not label or label.lower() == "nan":
            continue
        tid = (str(r.get(id_col) or "").strip() if id_col and id_col != name_col else "") or _slug(label)
        if tid in seen:
            continue
        seen.add(tid)
        out.append({"id": tid, "label": label, "category": (str(r.get(cat_col) or "").strip() or None) if cat_col else None})
    return out


# --- matching ---------------------------------------------------------------------------

def _ontologies(ontologies) -> list[str]:
    if isinstance(ontologies, str):
        ontologies = re.split(r"[,\s]+", ontologies)
    return list(dict.fromkeys(o.strip().lower() for o in ontologies or [] if o and o.strip()))


def _matches(term: dict, ontology: str, short: str, hits: list[dict], per_ontology: int, min_score: float) -> list[dict]:
    exact = [h for h in hits if h["exact"]]
    if ontology in TAXONOMIES or exact:
        chosen = exact[:1]
    else:
        chosen = [h for h in hits if h["score"] >= min_score][:per_ontology]
    out = []
    for rank, h in enumerate(chosen, 1):
        if h["exact"]:
            kind, conf = "skos:exactMatch", 1.0 if h["same"] else 0.95
        elif h["score"] >= 0.6:
            kind, conf = "skos:closeMatch", round(0.5 + 0.4 * h["score"], 3)
        else:
            kind, conf = "skos:relatedMatch", round(0.3 + 0.4 * h["score"], 3)
        out.append({"term_id": term["id"], "term": term["label"], "category": term.get("category"),
                    "match_type": kind, "ontology": short, "match_id": h["id"], "match_curie": h["curie"],
                    "match_label": h["label"], "confidence": conf, "word_overlap": h["score"], "rank": rank,
                    "definition": h.get("definition"), "searched_for": query_text(term["label"])})
    return out


def match(data, ontologies, *, column: str | None = None, per_ontology: int = 3,
          min_score: float = 0.34, progress=None, workers: int = 6) -> list[dict]:
    """Matches for every term in ``data`` in each of ``ontologies``: one dict per match with
    term_id, term, category, match_type, ontology, match_id, match_curie, match_label,
    confidence, word_overlap, rank, definition, searched_for.

    ``ontologies``: a list or a comma-separated string of IDs (``verdant.ONTOLOGIES`` or any
    OLS4 ontology). ``progress(done, total)`` is called as terms are looked up."""
    chosen = _ontologies(ontologies)
    if not chosen:
        raise ValueError("Choose at least one ontology, e.g. ontologies=['envo', 'ncbitaxon'].")
    terms = data if isinstance(data, list) and data and isinstance(data[0], dict) and {"id", "label"} <= set(data[0]) \
        else read_terms(data, column)
    shorts = {}
    for o in chosen:
        info = ontology_info(o)
        if info is None:
            raise ValueError(f"Unknown ontology “{o}”: use one of verdant.ONTOLOGIES or an OLS4 ontology ID.")
        shorts[o] = info["short"]

    tasks = [(t, o) for o in chosen for t in terms]
    out, done = [], 0
    with ThreadPoolExecutor(max_workers=2 if "wikidata" in chosen else workers) as pool:
        for t, o, hits in pool.map(lambda task: (*task, search(task[0]["label"], task[1])), tasks):
            done += 1
            if progress:
                progress(done, len(tasks))
            if hits:
                out.extend(_matches(t, o, shorts[o], hits, per_ontology, min_score))
    return out


def unmatched(data, matches: list[dict], ontologies) -> dict[str, list[str]]:
    """Per ontology, the terms that got no match in it."""
    terms = data if isinstance(data, list) and data and isinstance(data[0], dict) and "label" in data[0] else read_terms(data)
    got = {(m["term_id"], m["ontology"].lower()) for m in matches}
    out = {}
    for o in _ontologies(ontologies):
        short = (ontology_info(o) or {}).get("short", o).lower()
        out[o] = [t["label"] for t in terms if (t["id"], short) not in got]
    return out
