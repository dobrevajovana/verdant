"""Matches out: a table (CSV / TSV), SSSOM, JSON, or a pandas DataFrame."""

from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path

COLUMNS = ["term_id", "term", "category", "match_type", "ontology", "match_curie", "match_label", "confidence",
           "word_overlap", "rank", "match_id", "definition", "searched_for"]
PREFIXES = {"ENVO": "http://purl.obolibrary.org/obo/ENVO_", "NCBITaxon": "http://purl.obolibrary.org/obo/NCBITaxon_",
            "PATO": "http://purl.obolibrary.org/obo/PATO_", "OBA": "http://purl.obolibrary.org/obo/OBA_",
            "UO": "http://purl.obolibrary.org/obo/UO_", "CHEBI": "http://purl.obolibrary.org/obo/CHEBI_",
            "OBI": "http://purl.obolibrary.org/obo/OBI_", "UBERON": "http://purl.obolibrary.org/obo/UBERON_",
            "PO": "http://purl.obolibrary.org/obo/PO_", "GO": "http://purl.obolibrary.org/obo/GO_",
            "GBIF": "https://www.gbif.org/species/", "wikidata": "http://www.wikidata.org/entity/",
            "CF": "http://vocab.nerc.ac.uk/standard_name/", "GOLD": "https://w3id.org/gold.vocab/",
            "GOLD.path": "https://w3id.org/gold.path/", "n2k": "https://w3id.org/verdy/natura2000/"}   # local: Natura 2000 has no URIs of its own


def to_table(matches: list[dict], sep: str = ",") -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS, delimiter=sep, extrasaction="ignore", lineterminator="\n")
    w.writeheader()
    w.writerows(matches)
    return buf.getvalue()


def _subject(term_id: str) -> str:
    """Your ID as a CURIE: ENA accessions with their registry prefix, other IDs as they are,
    free text under term:."""
    t = str(term_id)
    if re.match(r"^SAM[NED][A-Z]?\d+$", t):
        return "biosample:" + t
    if re.match(r"^([EDS]R[RXSP]|PRJ[EDN][A-Z])\d+$", t):
        return "ena.embl:" + t
    if re.match(r"^[A-Za-z][\w.]*:\S+$", t) or t.startswith("http"):
        return t
    if re.match(r"^Q\d+$", t):
        return "wikidata:" + t
    return "term:" + re.sub(r"\s+", "_", t)


def to_sssom(matches: list[dict], name: str = "matches") -> str:
    """SSSOM TSV: lexical matches with their confidence, subjects as ``term:<term_id>``."""
    used = {m["match_curie"].split(":", 1)[0] for m in matches if ":" in m["match_curie"]}
    header = ["# curie_map:", "#   term: https://w3id.org/verdy/term/",
              "#   biosample: https://www.ebi.ac.uk/biosamples/samples/", "#   ena.embl: https://www.ebi.ac.uk/ena/browser/view/"] + \
        [f"#   {p}: {u}" for p, u in PREFIXES.items() if p in used] + [
        "#   skos: http://www.w3.org/2004/02/skos/core#", "#   semapv: https://w3id.org/semapv/vocab/",
        f"# mapping_set_id: https://w3id.org/verdy/{re.sub(r'[^A-Za-z0-9_.-]+', '-', name)}.sssom.tsv",
        "# mapping_set_description: Lexical matches found by verdy; not reviewed."]
    fields = ["subject_id", "subject_label", "subject_category", "predicate_id", "object_id", "object_label",
              "mapping_justification", "confidence", "object_source", "mapping_tool", "comment"]
    buf = io.StringIO()
    buf.write("\n".join(header) + "\n")
    w = csv.DictWriter(buf, fieldnames=fields, delimiter="\t", lineterminator="\n")
    w.writeheader()
    for m in matches:
        w.writerow({"subject_id": _subject(m["term_id"]), "subject_label": m["term"],
                    "subject_category": m.get("category") or "", "predicate_id": m["match_type"],
                    "object_id": m["match_curie"], "object_label": m["match_label"] or "",
                    "mapping_justification": "semapv:LexicalMatching", "confidence": m["confidence"],
                    "object_source": m["ontology"], "mapping_tool": "verdy",
                    "comment": f"word overlap {m['word_overlap']}; rank {m['rank']}"})
    return buf.getvalue()


def to_dataframe(matches: list[dict]):
    import pandas as pd
    return pd.DataFrame(matches, columns=COLUMNS)


def save(matches: list[dict], path) -> Path:
    """By the extension: .csv, .tsv, .sssom.tsv, .json (or .xlsx with pandas)."""
    path = Path(path)
    if path.name.endswith(".sssom.tsv"):
        path.write_text(to_sssom(matches, path.name[: -len(".sssom.tsv")]), encoding="utf-8")
    elif path.suffix.lower() == ".json":
        path.write_text(json.dumps(matches, indent=1, ensure_ascii=False), encoding="utf-8")
    elif path.suffix.lower() == ".xlsx":
        to_dataframe(matches).to_excel(path, index=False)
    else:
        path.write_text(to_table(matches, "\t" if path.suffix.lower() == ".tsv" else ","), encoding="utf-8")
    return path
