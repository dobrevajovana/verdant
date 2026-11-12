"""Predict matches for your IDs or terms in the ontologies you choose.

    import verdy
    matches = verdy.match("my_samples.csv", ontologies=["natura2000", "gold", "envo"])
    verdy.save(matches, "my_samples.matches.csv")

1. An ENA ID (sample, run or project) is looked up in ENA for its sample's organism
   (scientific_name), broad_scale_environmental_context, local_environmental_context,
   environmental_medium, ...; any other value is free text and is searched as it is.
2. Each name is searched in each chosen ontology on its own:

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

from verdy.resolve import SAMPLE_FIELDS, kind, resolve
from verdy.sources import TAXONOMIES, ontology_info, query_text, search

NAME_COLUMNS = ("name", "label", "term", "parameter", "measurement", "variable", "scientific_name", "scientificname",
                "species", "taxon", "habitat", "biome", "text", "value", "description")
ID_COLUMNS = ("id", "subject_id", "identifier", "accession", "sample_accession", "run_accession", "study_accession",
              "sample_id", "sample", "key", "source", "code")
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
    value per line, a list of strings or dicts, or a pandas DataFrame. The column read is
    given with ``column=``, or found by its header: a name column (name, label, term,
    parameter, measurement, species, ...) if there is one, else an ID column (id, accession,
    sample_accession, run_accession, ...). Repeats once."""
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
    name_col = column or _pick(cols, NAME_COLUMNS) or id_col
    if name_col is None:      # the first column with words in it
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


# --- IDs to names --------------------------------------------------------------------

def resolve_terms(terms: list[dict], fields=SAMPLE_FIELDS, workers: int = 6) -> tuple[list[dict], list[str]]:
    """Terms whose value is an ID become one term per name found for it (``id`` the ID,
    ``category`` the field(s) it came from); the IDs nothing was found for come second."""
    ids = [t for t in terms if kind(t["label"]) != "name"]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        found = dict(zip((t["label"] for t in ids), pool.map(lambda t: resolve(t["label"], fields), ids)))
    out, unresolved = [], []
    for t in terms:
        if t["label"] not in found:
            out.append(t)
            continue
        names = found[t["label"]]
        if not names:
            unresolved.append(t["label"] + (" (no answer from its source)" if names is None else ""))
            continue
        merged: dict[tuple[str, str], list[str]] = {}
        for field, value in names:
            sample, _, field = field.rpartition(":")         # a project's values come per sample
            merged.setdefault((sample or t["label"], value), []).append(field)
        for (tid, value), fs in merged.items():
            out.append({"id": tid, "label": value, "category": "|".join(dict.fromkeys(fs)),
                        **({"input": t["label"]} if tid != t["label"] else {})})
    return out, unresolved


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


def match(data, ontologies, *, column: str | None = None, per_ontology: int = 3, min_score: float = 0.34,
          fields=SAMPLE_FIELDS, progress=None, workers: int = 6) -> list[dict]:
    """Matches for every ID or term in ``data`` in each of ``ontologies``: one dict per match
    with term_id (your ID, or the term), term (the name searched), category (the field it
    came from), match_type, ontology, match_id, match_curie, match_label, confidence,
    word_overlap, rank, definition, searched_for.

    ``ontologies``: a list or a comma-separated string of IDs (``verdy.ONTOLOGIES`` or any
    OLS4 ontology). ``fields``: which ENA sample fields to search for a sample, run or project.
    ``progress(done, total)`` is called as names are looked up. IDs nothing was found for
    are in ``match.unresolved`` after the call."""
    chosen = _ontologies(ontologies)
    if not chosen:
        raise ValueError("Choose at least one ontology, e.g. ontologies=['envo', 'ncbitaxon'].")
    terms = data if isinstance(data, list) and data and isinstance(data[0], dict) and {"id", "label"} <= set(data[0]) \
        else read_terms(data, column)
    terms, match.unresolved = resolve_terms(terms, fields, workers)
    shorts = {}
    for o in chosen:
        info = ontology_info(o)
        if info is None:
            raise ValueError(f"Unknown ontology “{o}”: use one of verdy.ONTOLOGIES or an OLS4 ontology ID.")
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
