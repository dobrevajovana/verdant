<p align="center"><img src="logo.svg" width="160" alt="verdant logo: an old tree with spectacles, a moustache and a green coat"></p>

# verdant

**Match your own terms to the ontologies you choose.**

Your terms go in: species, habitats, measured parameters, variable names, sample descriptions.
You pick the ontologies. For each term and ontology, verdant gives back the exact match, or the
most closely related terms when there is no exact one.

```python
import verdant

matches = verdant.match("my_terms.csv", ontologies=["envo", "pato", "cf", "ncbitaxon", "gbif"])
verdant.save(matches, "my_terms.matches.csv")      # .csv  .tsv  .sssom.tsv  .json  .xlsx
```

```
verdant my_terms.csv -o envo,pato,cf --out my_terms.matches.csv
```

## Install

```
pip install git+https://github.com/dobrevajovana/verdant.git
pip install "verdant[excel] @ git+https://github.com/dobrevajovana/verdant.git"    # to read and write Excel
```

Python 3.10 or newer; the only dependency is `requests`.

## Your terms

`verdant.match` (and `verdant.read_terms`) take:

* a CSV / TSV / Excel file. The term column is found by its header (`name`, `label`, `term`,
  `parameter`, `measurement`, `variable`, `species`, `scientific_name`, `habitat`, ...) or given with
  `column="..."`. An `id` column and a `category` column are kept when present;
* a text file with one term per line;
* a Python list of strings or dicts, or a pandas DataFrame.

Terms are cleaned before the search: a unit in brackets (`air temperature [K]`), underscores
(`air_temperature`), a leading code (`1330 Atlantic salt meadows`), plurals.

## The ontologies

`verdant.ONTOLOGIES` (or `verdant --list`):

| ID | What | For |
|---|---|---|
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

How the search works:
* At most `per_ontology` matches (default 3) per term and ontology. When there is an exact match, only that one is given.
* In the taxonomies (NCBITaxon, GBIF), only exact names count, because a near name is another taxon.
* `verdant.unmatched(terms, matches, ontologies)` lists, per ontology, the terms it found nothing for.

Every answer is cached in `~/.cache/verdant` (or `VERDANT_CACHE`), so a second run makes no requests.

## Example

`python examples/match_terms.py` matches [examples/terms.csv](examples/terms.csv) (species, habitats and
parameters) against six ontologies. It writes [examples/terms.matches.csv](examples/terms.matches.csv)
and [examples/terms.matches.sssom.tsv](examples/terms.matches.sssom.tsv). Part of the result:

| term | ontology | match | | confidence |
|---|---|---|---|---|
| Lynx lynx | NCBITaxon | exactMatch | NCBITaxon:13125 *Lynx lynx* | 1.0 |
| Lynx lynx | GBIF | exactMatch | GBIF:2435240 *Lynx lynx* | 1.0 |
| Lynx lynx | Wikidata | exactMatch | wikidata:Q43375 Eurasian lynx | 1.0 |
| Elphidium sp. | NCBITaxon | exactMatch | NCBITaxon:1747686 *Elphidium sp.* | 1.0 |
| 1330 Atlantic salt meadows | Wikidata | exactMatch | wikidata:Q105574174 Glauco-Puccinellietalia | 1.0 |
| Spartina swards | Wikidata | exactMatch | wikidata:Q61744273 Spartinion maritimae | 1.0 |
| Peat bog | ENVO | exactMatch | ENVO:00000044 peatland (a synonym) | 1.0 |
| Sea cliffs and shingle or stony beaches | ENVO | relatedMatch | ENVO:00000088 sea cliff · ENVO:00000545 shingle beach | 0.46 |
| air_temperature | CF | exactMatch | CF:air_temperature | 1.0 |
| air_temperature | ENVO | exactMatch | ENVO:09200001 temperature of air | 1.0 |
| air_temperature | PATO | relatedMatch | PATO:0000146 temperature | 0.5 |
| salinity | PATO | exactMatch | PATO:0085001 salinity | 1.0 |
| cloud liquid water content | CF | closeMatch | CF:atmosphere_mass_content_of_cloud_liquid_water | 0.82 |
| chlorophyll a concentration | ENVO | relatedMatch | ENVO:3100008 concentration of chlorophyll a in liquid water | 0.5 |

## One term at a time

```python
verdant.search("cloud liquid water content", "cf")    # the source's best terms, best first
verdant.read_terms("my_terms.csv")                    # what verdant read from your file
verdant.to_dataframe(matches)                         # pandas
```

## Tests

```
pip install -e ".[test]" && python -m pytest -q
```

The tests stub every web service, so they run offline.
