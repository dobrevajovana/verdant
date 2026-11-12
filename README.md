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
pip install "verdy[embeddings]"   # to also compare by embedding similarity (SentenceTransformers, cosine)
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
| `cosine` | embedding similarity (0..1) with `verdy[embeddings]` installed; empty otherwise. A match is kept on it from `min_cosine` (default 0.70); from 0.80 it is a closeMatch |
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
