"""ENA IDs and free text in, matches in the chosen ontologies out.

    python examples/predict.py

examples/input.csv mixes ENA accessions (a sample, a run, a sample) with free text.
The accessions are looked up in ENA for their organism and environment fields; every
name is then searched in Natura 2000, GOLD, ENVO, NCBITaxon, PATO and CF. The matches
go to examples/input.matches.csv and examples/input.matches.sssom.tsv.
"""

from pathlib import Path

import verdant

HERE = Path(__file__).resolve().parent
ONTOLOGIES = ["natura2000", "gold", "envo", "ncbitaxon", "pato", "cf"]

matches = verdant.match(HERE / "input.csv", ONTOLOGIES, per_ontology=2,
                        progress=lambda done, total: print(f"\r{done} of {total} lookups", end=""))
print()
verdant.save(matches, HERE / "input.matches.csv")
verdant.save(matches, HERE / "input.matches.sssom.tsv")

print(f"{len(matches)} matches -> examples/input.matches.csv")
for m in matches:
    print(f"  {m['term_id']:22} {m['term'][:26]:26} {m['ontology']:10} {m['match_type'][5:]:12} {m['match_curie'][:26]:26} {m['match_label'][:42]}")
if verdant.match.unresolved:
    print("  nothing found in ENA for:", ", ".join(verdant.match.unresolved))
