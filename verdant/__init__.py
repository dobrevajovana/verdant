"""verdant: match your own terms to the ontologies you choose.

Your terms (species, habitats, parameters, measurement names, sample descriptions, ...)
go in as a CSV / TSV / Excel file, a text file or a Python list; for each ontology you
choose, out come its exact and most related terms.

    import verdant

    matches = verdant.match("my_terms.csv", ontologies=["envo", "pato", "cf", "ncbitaxon", "gbif"])
    verdant.save(matches, "my_terms.matches.csv")        # or .tsv / .sssom.tsv / .json / .xlsx
    verdant.unmatched("my_terms.csv", matches, ["envo", "pato"])   # what each found nothing for

    verdant.ONTOLOGIES                  # the ready ones; any OLS4 ontology ID works too
    verdant.search("air temperature", "cf")   # one term in one ontology, its best terms

From the shell:  verdant my_terms.csv -o envo,pato,cf --out my_terms.matches.csv
"""

from verdant.match import MATCH_TYPES, match, read_terms, unmatched
from verdant.output import save, to_dataframe, to_sssom, to_table
from verdant.sources import ONTOLOGIES, ontology_info, search

__version__ = "0.1.0"

__all__ = ["match", "search", "read_terms", "unmatched", "save", "to_table", "to_sssom", "to_dataframe",
           "ONTOLOGIES", "MATCH_TYPES", "ontology_info", "__version__"]
