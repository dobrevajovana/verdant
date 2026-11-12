"""VERDY: predict matches for your ENA IDs or free-text terms in the ontologies you choose.

Part of VERDANT: Vocabulary Enrichment & Resolution of Diversity Annotations via Neural Technology.

Input (a CSV / TSV / Excel file, a text file or a Python list) holds ENA IDs (samples,
runs, projects) and/or free text (species, habitats, parameters, measurements). ENA IDs
are looked up in ENA for their organism and environment fields; every name is searched in
each ontology you choose; out come its exact and most related terms.

    import verdy

    matches = verdy.match("my_input.csv", ontologies=["natura2000", "gold", "envo", "ncbitaxon"])
    verdy.save(matches, "my_input.matches.csv")        # or .tsv / .sssom.tsv / .json / .xlsx
    verdy.match.unresolved                             # ENA IDs ENA did not know
    verdy.unmatched("my_input.csv", matches, ["envo"]) # names an ontology found nothing for

    verdy.ONTOLOGIES                       # the ready ones; any OLS4 ontology ID works too
    verdy.search("air temperature", "cf")  # one name in one ontology, its best terms
    verdy.resolve("SAMD00132352")          # what ENA says about an ID

From the shell:  verdy my_input.csv -o natura2000,gold,envo --out my_input.matches.csv
"""

from verdy.match import MATCH_TYPES, match, read_terms, resolve_terms, unmatched
from verdy.resolve import SAMPLE_FIELDS, resolve
from verdy.output import save, to_dataframe, to_sssom, to_table
from verdy.sources import ONTOLOGIES, ontology_info, search

__version__ = "0.1.1"

predict = match          # the same: IDs or names in, predicted matches out

__all__ = ["match", "predict", "resolve", "resolve_terms", "SAMPLE_FIELDS", "search", "read_terms", "unmatched", "save", "to_table", "to_sssom", "to_dataframe",
           "ONTOLOGIES", "MATCH_TYPES", "ontology_info", "__version__"]
