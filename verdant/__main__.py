"""Command line:  verdant TERMS -o envo,pato,cf [--column NAME] [--out FILE]

    verdant my_terms.csv -o envo,ncbitaxon,gbif --out my_terms.matches.csv
    verdant my_terms.csv -o pato,cf,uo                       # print a table instead
    verdant --list                                           # the ready ontologies
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from verdant.match import match, read_terms, unmatched
from verdant.output import save, to_table
from verdant.sources import ONTOLOGIES


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="verdant", description="Match your terms to the ontologies you choose.")
    ap.add_argument("terms", nargs="?", help="CSV / TSV / Excel with a name column, or a text file with one term per line")
    ap.add_argument("-o", "--ontologies", help="comma-separated IDs: see --list; any OLS4 ontology ID works too")
    ap.add_argument("--column", help="the column holding the terms (found by its header otherwise)")
    ap.add_argument("--out", type=Path, help="write here: .csv, .tsv, .sssom.tsv, .json or .xlsx (default: print)")
    ap.add_argument("--per-ontology", type=int, default=3, help="at most this many matches per term and ontology (3)")
    ap.add_argument("--min-score", type=float, default=0.34, help="least word overlap for a related match (0.34)")
    ap.add_argument("--list", action="store_true", help="list the ready ontologies")
    args = ap.parse_args(argv)
    if args.list:
        for k, v in ONTOLOGIES.items():
            print(f"{k:11} {v}")
        return 0
    if not args.terms or not args.ontologies:
        ap.error("give a TERMS file and --ontologies (or --list)")
    try:
        terms = read_terms(args.terms, args.column)
        matches = match(terms, args.ontologies, per_ontology=args.per_ontology,
                        min_score=args.min_score,
                        progress=lambda d, t: print(f"\r{d} of {t} lookups", end="", file=sys.stderr))
    except ValueError as exc:
        ap.error(str(exc))
    print(file=sys.stderr)
    if args.out:
        save(matches, args.out)
        print(f"{len(matches)} matches for {len({m['term_id'] for m in matches})} of {len(terms)} terms -> {args.out}",
              file=sys.stderr)
    else:
        sys.stdout.write(to_table(matches, "\t"))
    for o, missing in unmatched(terms, matches, args.ontologies).items():
        if missing:
            print(f"nothing in {o} for: {', '.join(missing)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
