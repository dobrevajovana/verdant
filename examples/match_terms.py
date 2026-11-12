"""Match examples/terms.csv (species, habitats and measured parameters) to six ontologies.

    python examples/match_terms.py

Writes examples/terms.matches.csv and examples/terms.matches.sssom.tsv.
"""

from pathlib import Path

import verdant

HERE = Path(__file__).resolve().parent
ONTOLOGIES = ["envo", "ncbitaxon", "gbif", "pato", "cf", "wikidata"]

matches = verdant.match(HERE / "terms.csv", ONTOLOGIES,
                        progress=lambda done, total: print(f"\r{done} of {total} lookups", end=""))
print()
verdant.save(matches, HERE / "terms.matches.csv")
verdant.save(matches, HERE / "terms.matches.sssom.tsv")

print(f"{len(matches)} matches for {len({m['term_id'] for m in matches})} terms")
for m in matches:
    print(f"  {m['term']:28} {m['ontology']:9} {m['match_type'][5:]:12} {m['confidence']:<5} {m['match_curie']:28} {m['match_label']}")
for ontology, terms in verdant.unmatched(HERE / "terms.csv", matches, ONTOLOGIES).items():
    if terms:
        print(f"  nothing in {ontology} for: {', '.join(terms)}")
