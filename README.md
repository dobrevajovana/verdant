<p align="center"><img src="https://raw.githubusercontent.com/dobrevajovana/verdy/main/logo.png" width="200" alt="VERDY logo: a green forest spirit with a flower crown, braided leafy hair and berry nodes linked by vines"></p>

# VERDY

[![PyPI](https://img.shields.io/pypi/v/verdy)](https://pypi.org/project/verdy/)
[![Python package](https://github.com/dobrevajovana/verdy/actions/workflows/python-package.yml/badge.svg)](https://github.com/dobrevajovana/verdy/actions/workflows/python-package.yml)

*Part of **VERDANT**: **V**ocabulary **E**nrichment & **R**esolution of **D**iversity **A**nnotations via **N**eural **T**echnology
(BioHackathon Europe 2026).*

**Meet VERDY, your warrior for ontology matching.** Give it your ENA IDs or free-text terms, choose the ontologies, and it predicts the matching terms in each.

1. **Input:** a file (or Python list) of ENA IDs and/or free text. The IDs can be samples, runs or projects. The free text can be species, habitats, parameters or measurement names.
2. **ENA lookup:** each ENA ID is looked up in [ENA](https://www.ebi.ac.uk/ena/portal/api) for its sample's organism and environment fields (`scientific_name`, `broad_scale_environmental_context`, `local_environmental_context`, `environmental_medium`, ...). Free text is used as it is.
3. **Search:** every name is searched in each ontology you choose (for example `natura2000`, `gold`, `envo`).
4. **Output:** a file with the exact match, or the most closely related terms, per name and ontology.

```python
import verdy

matches = verdy.match("my_input.csv", ontologies=["natura2000", "gold", "envo", "ncbitaxon"])
verdy.save(matches, "my_input.matches.csv")      # .csv  .tsv  .sssom.tsv  .json  .xlsx
```

```
verdy my_input.csv -o natura2000,gold,envo --out my_input.matches.csv
```

## Install

```
pip install verdy
pip install "verdy[excel]"     # to read and write Excel
pip install git+https://github.com/dobrevajovana/verdy.git    # the latest, unreleased version
```

Python 3.10 or newer; the only dependency is `requests`.

## Input

`verdy.match` takes a CSV / TSV / Excel file, a text file with one value per line, a Python list or a pandas DataFrame.
The column is found by its header (`name`, `term`, `parameter`, `species`, ..., or `id`, `accession`, `sample_accession`, `run_accession`)
or given with `column="..."`. One file can mix both kinds of value:

| value | what happens |
|---|---|
| `SAMD00132352`, `SAMEA...`, `SAMN...`, `ERS...` | an ENA sample: its fields are looked up in ENA and each value is searched |
| `ERR9966617`, `SRR...`, `ERX...` | a run or experiment: its sample, as above |
| `PRJEB54740`, `PRJNA...` | a project: all its samples, each row under the sample's own accession |
| anything else | free text, searched as it is (units in brackets, underscores and a leading code are set aside) |

`fields=` chooses other ENA sample fields to search (see ENA's `returnFields?result=sample`).
After a run, `verdy.match.unresolved` lists the IDs ENA did not know.

## How it works

```
 your file                 1. read            2. ENA lookup                 3. clean
 ──────────               ─────────          ──────────────────            ─────────────────────
 SAMD00132352      ──►    one value   ──►    ENA ID? ask ENA for the  ──►  "air temperature [K]"
 ERR9966617               per row            sample's fields:               -> "air temperature"
 air_temperature                             scientific_name,               "air_temperature"
 Lynx lynx                                   env. context, medium...        -> "air temperature"
                                             free text: kept as is          "1330 Atlantic salt meadows"
                                                                            -> "Atlantic salt meadows"

 4. search each chosen ontology        5. score every term found         6. keep the best
 ─────────────────────────────         ─────────────────────────         ───────────────────────
 OLS4: exact search, then word    ──►  shared words between the    ──►   exact? keep only it
 searches; GBIF matcher; Wikidata      name and the term's label         else up to 3 close /
 search; CF and Natura 2000 lists      and synonyms (0..1)               related matches
                                                                         -> your output file
```

1. **Read.** VERDY takes one value per row from the column it finds (or the one you name with `column=`).
2. **ENA lookup.** A value that is an ENA accession is sent to the ENA Portal API:
   - a sample (SAM…, ERS…) gives its descriptive fields;
   - a run or experiment (ERR…, SRR…, ERX…) gives the fields of its sample;
   - a project (PRJEB…, ERP…) gives every sample in it.

   The fields are the organism (`scientific_name`), the broad-scale and local environmental context, the environmental medium, the biome, feature and material, the isolation source and the host. Empty values such as "missing" or "not applicable" are dropped. A value that occurs in several fields of one sample (for example "air" as both local context and medium) is searched once, and all its fields are listed in `category`. Any value that is not an ENA accession is free text and goes straight to step 3.
3. **Clean.** VERDY removes a unit or note in brackets, underscores and a leading code before searching. Plurals and "sp." are ignored when comparing words.
4. **Search** each ontology you chose, on its own:
   - **OLS4 ontologies** (ENVO, NCBITaxon, PATO, GOLD, ChEBI, any OLS4 ID): first OLS4's exact search on the name as written. OLS4 only returns terms that contain every word of a query, so VERDY then also searches the singular form, pairs of key words and single key words. Obsolete terms are dropped, and so are terms another ontology only imports.
   - **GBIF:** the GBIF Backbone name matcher.
   - **Wikidata:** the Wikidata item search.
   - **CF Standard Names:** the official table, downloaded once and searched locally, aliases included.
   - **Natura 2000:** the habitat type and species lists of the EEA Article 17 report, fetched once and searched locally. A habitat can also be found by its code (`1330`).
5. **Score.** Each term found is compared word by word with the name, using its label and synonyms. For a GOLD path, the comparison uses its last step: "Environmental > Air > Outdoor Air" counts as "Outdoor Air". The word overlap runs from 0 (no word shared) to 1 (the same words).
   - **Exact match:** the term has the same words as the name. A short all-capital abbreviation counts only when your name is written that way, so "air" doesn't match a chemical whose synonym is "AIR".
6. **Keep the best.**
   - **Exact match found:** only that one is kept (`skos:exactMatch`, confidence 1.0 as written, 0.95 up to plurals).
   - **Otherwise:** up to `per_ontology` (default 3) of the best terms are kept: `skos:closeMatch` from overlap 0.6, `skos:relatedMatch` from `min_score` (default 0.34).
   - **Taxonomies (NCBITaxon, GBIF):** only exact names count, because a name one word off is a different taxon.

Every answer from every source is cached in `~/.cache/verdy` (or `VERDY_CACHE`), so running the same file again makes no requests. Lookups run in parallel, with fewer at a time for Wikidata, which limits its users. A service that does not answer is retried twice and then skipped, rather than stopping the run. VERDY matches on words, not meaning; the `definition` column helps you check related matches.

## The ontologies

`verdy.ONTOLOGIES` (or `verdy --list`):

| ID | What | For |
|---|---|---|
| `natura2000` | Natura 2000 habitat types and species (EEA Article 17 lists, fetched live) | habitats by name or code, protected species |
| `envo` | Environment Ontology | habitats, environments, materials, environmental measurements |
| `gold` | GOLD ecosystem classification | sample ecosystems |
| `ncbitaxon` | NCBI Taxonomy | organisms |
| `gbif` | GBIF Backbone Taxonomy | organisms |
| `pato` | Phenotype And Trait Ontology | qualities: temperature, salinity, humidity, ... |
| `oba` | Ontology of Biological Attributes | traits and measurable attributes |
| `cf` | CF Standard Names | climate, weather and ocean variables |
| `uo` | Units of measurement | units |
| `chebi` | Chemical Entities of Biological Interest | chemicals |
| `obi` | Ontology for Biomedical Investigations | assays, instruments, protocols |
| `uberon`, `po`, `go` | anatomy, plants, biological processes | |
| `wikidata` | Wikidata | anything with a name |

**Any other ontology in [OLS4](https://www.ebi.ac.uk/ols4/ontologies) works as well:** pass its ID
(for example `foodon`, `pco` or `ms`).

## What comes out

One row per match:

| column | |
|---|---|
| `term_id`, `term`, `category` | your term |
| `match_type` | `skos:exactMatch`: a label or synonym is the term (plurals and `sp.` aside) · `skos:closeMatch`: most words shared · `skos:relatedMatch`: some words shared |
| `ontology`, `match_curie`, `match_id`, `match_label` | the matched term |
| `confidence` | 1.0 exact as written, 0.95 exact up to plurals, then by word overlap |
| `word_overlap`, `rank` | how many words they share (0..1), and the place among this term's matches |
| `definition` | the term's definition (units first, for CF) |
| `searched_for` | the term after cleaning |

`verdy.unmatched(terms, matches, ontologies)` lists, per ontology, the terms it found nothing for.

## Example

`python examples/predict.py` runs [examples/input.csv](examples/input.csv), which has three ENA accessions and four free-text terms, against
Natura 2000, GOLD, ENVO, NCBITaxon, PATO and CF. It writes [examples/input.matches.csv](examples/input.matches.csv). Part of the result:

| input | name searched (from) | ontology | match |
|---|---|---|---|
| SAMD00132352 | urban biome (broad_scale_environmental_context) | ENVO | exactMatch ENVO:01000249 urban biome |
| SAMD00132352 | air (local_environmental_context, environmental_medium) | ENVO · GOLD | exactMatch ENVO:00002005 air · GOLD:Air |
| SAMD00132352 | air metagenome (scientific_name) | NCBITaxon | exactMatch NCBITaxon:655179 |
| ERR9966617 | temperate forest | ENVO | exactMatch ENVO:01001805 temperate forest |
| ERR9966617 | mountain | ENVO | exactMatch ENVO:00000081 mountain |
| SAMEA110429224 | Human (host_scientific_name) | NCBITaxon | exactMatch NCBITaxon:9606 Homo sapiens |
| Lynx lynx | | Natura 2000 · NCBITaxon | exactMatch n2k:1361 · NCBITaxon:13125 |
| Atlantic salt meadows | | Natura 2000 | exactMatch n2k:1330 |
| air_temperature | | CF · ENVO | exactMatch CF:air_temperature · ENVO:09200001 temperature of air |
| salinity | | PATO | exactMatch PATO:0085001 |

## One term at a time

```python
verdy.search("cloud liquid water content", "cf")    # the source's best terms, best first
verdy.resolve("SAMD00132352")                      # what ENA says about an ID
verdy.read_terms("my_input.csv")                    # what VERDY read from your file
verdy.to_dataframe(matches)                         # pandas
```

## Tests

```
pip install -e ".[test]" && python -m pytest -q
```

The tests stub every web service, so they run offline.

## Licence

MIT, see [LICENSE](LICENSE).
