"""ENA IDs to the names worth searching for (ENA Portal API).

    resolve("SAMD00132352") -> [("scientific_name", "air metagenome"),
                                ("broad_scale_environmental_context", "urban biome"), ...]
    resolve("ERR10002200")  -> the run's sample, as above
    resolve("PRJEB54740")   -> every sample of the project, as "<sample>:<field>"

Samples (SAMN/SAMEA/SAMD..., ERS/SRS/DRS...), runs and experiments (ERR/SRR/DRR...,
ERX/SRX/DRX...) and projects (PRJEB/PRJNA/PRJDB..., ERP/SRP/DRP...). Anything else is
free text and is searched as it is.
"""

from __future__ import annotations

import re

from verdant import sources
from verdant.sources import Cache

ENA_API = "https://www.ebi.ac.uk/ena/portal/api"
# ENA sample fields that say what a sample is; ``fields=`` chooses others (see ENA's returnFields).
SAMPLE_FIELDS = ("scientific_name", "broad_scale_environmental_context", "local_environmental_context",
                 "environmental_medium", "environment_biome", "environment_feature", "environment_material",
                 "isolation_source", "host_scientific_name", "host_body_site", "tissue_type")
EMPTY = {"", "missing", "not applicable", "not collected", "not provided", "na", "n/a", "unknown", "none"}

SAMPLE = re.compile(r"^(SAM[NED][A-Z]?\d+|[EDS]RS\d+)$", re.I)
RUN = re.compile(r"^[EDS]R[RX]\d+$", re.I)
PROJECT = re.compile(r"^(PRJ[EDN][A-Z]\d+|[EDS]RP\d+)$", re.I)


def kind(identifier: str) -> str:
    """What sort of ID this is, or 'name' when it is not one."""
    s = str(identifier or "").strip()
    for name, pattern in (("sample", SAMPLE), ("run", RUN), ("project", PROJECT)):
        if pattern.match(s):
            return name
    return "name"


def ena_sample(accession: str, fields=SAMPLE_FIELDS) -> list[tuple[str, str]] | None:
    """The sample's (field, value) pairs from ENA; [] when ENA does not know it."""
    acc = accession.upper()
    fields = tuple(fields)

    def fetch():
        d = sources._json(f"{ENA_API}/search", result="sample", format="json", fields=",".join(fields),
                          query=f'sample_accession="{acc}" OR secondary_sample_accession="{acc}"')
        return d if d is None else (d[0] if isinstance(d, list) and d else {})
    row = Cache("resolve_ena_sample").get(f"{acc}|{','.join(fields)}", fetch)
    if row is None:
        return None
    return [(f, str(row.get(f)).strip()) for f in fields if str(row.get(f) or "").strip().lower() not in EMPTY]


def ena_samples_of(accession: str) -> list[str] | None:
    """The sample accessions of an ENA run, experiment or project."""
    acc = accession.upper()

    def fetch():
        d = sources._json(f"{ENA_API}/filereport", accession=acc, result="read_run", fields="sample_accession",
                          format="json", limit=0)
        return d if d is None else list(dict.fromkeys(r["sample_accession"] for r in d or [] if r.get("sample_accession")))
    return Cache("resolve_ena_runs").get(acc, fetch)


def resolve(identifier, fields=SAMPLE_FIELDS) -> list[tuple[str, str]] | None:
    """``[(field, name), ...]`` to search for: an ENA ID's sample fields (None when ENA did not
    answer, [] when it does not know the ID), or free text as it is."""
    s = str(identifier or "").strip()
    k = kind(s)
    if k == "name":
        return [("name", s)] if s else []
    if k == "sample":
        return ena_sample(s, fields)
    if k in ("run", "project"):
        samples = ena_samples_of(s)
        if samples is None:
            return None
        out = []
        for acc in samples:
            got = ena_sample(acc, fields)
            if got:
                out += [(f"{acc}:{f}" if k == "project" else f, v) for f, v in got]
        return out
