"""verdant.match with every web service stubbed.

Run:  python -m pytest -q
"""

import csv
import json

import pytest

import verdant
from verdant import sources

ENVO = "http://purl.obolibrary.org/obo/ENVO_"
TAXON = "http://purl.obolibrary.org/obo/NCBITaxon_"
PATO = "http://purl.obolibrary.org/obo/PATO_"
CF = b"""<?xml version="1.0"?><standard_name_table>
<entry id="air_temperature"><canonical_units>K</canonical_units><description>Air temperature is the bulk temperature of the air.</description></entry>
<entry id="wind_speed"><canonical_units>m s-1</canonical_units><description>Speed is the magnitude of velocity.</description></entry>
<alias id="surface_air_temperature"><entry_id>air_temperature</entry_id></alias>
</standard_name_table>"""


@pytest.fixture
def services(monkeypatch, tmp_path):
    """OLS4 (ENVO, NCBITaxon, PATO), GBIF, Wikidata and the CF table, answering from these tables."""
    monkeypatch.setattr(sources, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(sources, "_cf_terms", None)
    (tmp_path / "cache").mkdir()
    (tmp_path / "cache" / "cf-standard-name-table.xml").write_bytes(CF)
    ols = {("envo", "estuary"): [{"iri": ENVO + "00000045", "label": "estuary", "obo_id": "ENVO:00000045"}],
           ("envo", "lagoon"): [{"iri": ENVO + "00000038", "label": "lagoon", "obo_id": "ENVO:00000038"}],
           ("envo", "coastal"): [{"iri": ENVO + "1", "label": "coastal water", "obo_id": "ENVO:1"}],
           ("ncbitaxon", "lynx lynx"): [{"iri": TAXON + "13125", "label": "Lynx lynx", "obo_id": "NCBITaxon:13125"}],
           ("ncbitaxon", "estuaries"): [{"iri": TAXON + "1", "label": "estuaries bacterium"}],
           ("pato", "temperature"): [{"iri": PATO + "0000146", "label": "temperature", "obo_id": "PATO:0000146"}],
           ("envo", "urban biome"): [{"iri": ENVO + "01000249", "label": "urban biome", "obo_id": "ENVO:01000249",
                                      "is_defining_ontology": True}],
           ("envo", "air"): [{"iri": ENVO + "00002005", "label": "air", "obo_id": "ENVO:00002005", "is_defining_ontology": True}],
           ("gold", "air"): [{"iri": "https://w3id.org/gold.path/3962", "label": "Environmental > Air > Outdoor Air",
                              "is_defining_ontology": False},
                             {"iri": "https://w3id.org/gold.vocab/Air", "label": "Air", "is_defining_ontology": False}]}
    calls = []

    def fake(url, **p):
        calls.append(url)
        if url.endswith("/portal/api/search"):                         # ENA samples
            acc = p["query"].split('"')[1]
            return [{"sample_accession": "SAMD1", "scientific_name": "air metagenome", "broad_scale_environmental_context":
                     "urban biome", "local_environmental_context": "air", "environmental_medium": "air",
                     "isolation_source": "missing"}] if acc in ("SAMD1", "ERS1") else []
        if url.endswith("/portal/api/filereport"):                     # ENA runs and projects
            return {"ERR1": [{"sample_accession": "SAMD1"}], "PRJEB1": [{"sample_accession": "SAMD1"},
                    {"sample_accession": "SAMD1"}]}.get(p["accession"], [])
        if "/ontologies/" in url:
            oid = url.rsplit("/", 1)[1]
            return {"config": {"title": oid, "preferredPrefix": {"ncbitaxon": "NCBITaxon"}.get(oid, oid.upper())}} \
                if oid in ("envo", "ncbitaxon", "pato", "gold") else {}
        if url.endswith("/search"):
            return {"response": {"docs": ols.get((p["ontology"], p["q"].lower()), [])}}
        if "species/match" in url:
            return {"usageKey": 2435240, "canonicalName": "Lynx lynx", "matchType": "EXACT"} if p["name"] == "Lynx lynx" \
                else {"matchType": "NONE"}
        if "MapServer" in url:                                          # Natura 2000 (Article 17)
            if "/5/" in url:
                return {"features": [{"attributes": {"reference_habitatlist.habitat_code": "1130",
                                                     "reference_habitatlist.label": "Estuaries"}}]}
            return {"features": [{"attributes": {"reference_specieslist.species_code": "1361",
                                                 "reference_specieslist.species_name": "Lynx lynx",
                                                 "reference_specieslist.taxonomical_group": "Mammals"}}]}
        if "wikidata" in url:
            return {"search": [{"id": "Q43375", "label": "Eurasian lynx", "aliases": ["Lynx lynx"]}]} if p["search"] == "Lynx lynx" \
                else {"search": [{"id": "Q9", "label": "some moth", "aliases": ["coastal lagoons moth"]}]}
        return {}
    monkeypatch.setattr(sources, "_json", fake)
    return calls


def test_read_terms_from_many_inputs(tmp_path):
    (tmp_path / "a.csv").write_text("id,Parameter,group\nx1,air temperature (°C),parameter\nx2,Estuaries,habitat\nx2,again,habitat\n")
    (tmp_path / "b.txt").write_text("Lynx lynx\n\nEstuaries\n")
    (tmp_path / "c.tsv").write_text("code\tlabel\n1130\tEstuaries\n")
    assert verdant.read_terms(tmp_path / "a.csv") == [
        {"id": "x1", "label": "air temperature (°C)", "category": "parameter"}, {"id": "x2", "label": "Estuaries", "category": "habitat"}]
    assert [t["label"] for t in verdant.read_terms(tmp_path / "b.txt")] == ["Lynx lynx", "Estuaries"]
    assert verdant.read_terms(tmp_path / "c.tsv")[0] == {"id": "1130", "label": "Estuaries", "category": None}
    assert [t["id"] for t in verdant.read_terms(["Lynx lynx", {"name": "Coastal lagoons"}])] == ["lynx_lynx", "coastal_lagoons"]
    with pytest.raises(ValueError):
        verdant.read_terms(tmp_path / "a.csv", column="nope")


def test_only_the_chosen_ontologies(services):
    ms = verdant.match(["Lynx lynx", "Estuaries", "Coastal lagoons"], ["envo"])
    assert {m["ontology"] for m in ms} == {"ENVO"}
    by = {(m["term"], m["match_label"]): m for m in ms}
    assert by[("Estuaries", "estuary")]["match_type"] == "skos:exactMatch"            # plural aside
    assert by[("Coastal lagoons", "lagoon")]["match_type"] == "skos:relatedMatch"
    assert not any(m["term"] == "Lynx lynx" for m in ms)
    assert not any("wikidata" in c or "gbif" in c for c in services)                  # not chosen, not asked


def test_taxonomies_take_exact_names_only(services):
    ms = verdant.match(["Lynx lynx", "Estuaries"], "ncbitaxon, gbif, wikidata")
    got = {(m["term"], m["ontology"]): m for m in ms}
    assert got[("Lynx lynx", "NCBITaxon")]["match_curie"] == "NCBITaxon:13125"
    assert got[("Lynx lynx", "GBIF")]["match_curie"] == "GBIF:2435240"
    assert got[("Lynx lynx", "Wikidata")]["match_type"] == "skos:exactMatch"          # by its alias
    assert ("Estuaries", "NCBITaxon") not in got                                     # 'estuaries bacterium' is not it
    assert ("Estuaries", "Wikidata") not in got                                      # an alias alone is no near match
    assert verdant.unmatched(["Lynx lynx", "Estuaries"], ms, "ncbitaxon,gbif") == {"ncbitaxon": ["Estuaries"], "gbif": ["Estuaries"]}


def test_parameters_in_cf_and_pato(services):
    ms = verdant.match(["air temperature [K]", "wind speed", "surface air temperature"], ["cf", "pato"])
    got = {(m["term"], m["ontology"], m["match_curie"]): m["match_type"] for m in ms}
    assert got[("air temperature [K]", "CF", "CF:air_temperature")] == "skos:exactMatch"      # units in brackets aside
    assert got[("surface air temperature", "CF", "CF:air_temperature")] == "skos:exactMatch"  # a CF alias
    assert got[("wind speed", "CF", "CF:wind_speed")] == "skos:exactMatch"
    assert got[("air temperature [K]", "PATO", "PATO:0000146")] == "skos:relatedMatch"
    assert next(m for m in ms if m["match_curie"] == "CF:air_temperature")["definition"].startswith("[K]")


def test_leading_codes_units_and_underscores():
    from verdant.sources import query_text
    assert query_text("1330 Atlantic salt meadows") == "Atlantic salt meadows"
    assert query_text("air temperature [K]") == "air temperature" and query_text("air_temperature") == "air temperature"
    assert query_text("16S rRNA gene") == "16S rRNA gene"


def test_unknown_or_no_ontology(services):
    with pytest.raises(ValueError, match="nosuch"):
        verdant.match(["Lynx lynx"], ["nosuch"])
    with pytest.raises(ValueError):
        verdant.match(["Lynx lynx"], [])


def test_outputs(services, tmp_path):
    ms = verdant.match(["Lynx lynx", "Estuaries"], ["envo", "ncbitaxon"])
    for f in ("m.csv", "m.tsv", "m.json", "m.sssom.tsv"):
        verdant.save(ms, tmp_path / f)
    rows = list(csv.DictReader(open(tmp_path / "m.csv")))
    assert {r["match_curie"] for r in rows} == {"ENVO:00000045", "NCBITaxon:13125"}
    assert json.loads((tmp_path / "m.json").read_text()) == ms
    sssom = (tmp_path / "m.sssom.tsv").read_text()
    assert "semapv:LexicalMatching" in sssom and "#   ENVO: http://purl.obolibrary.org/obo/ENVO_" in sssom


def test_cache_makes_no_second_request(services):
    verdant.match(["Estuaries"], ["envo"])
    n = len(services)
    verdant.match(["Estuaries"], ["envo"])
    assert len(services) == n


def test_command_line(services, tmp_path, capsys):
    from verdant.__main__ import main
    (tmp_path / "n.csv").write_text("name\nLynx lynx\nEstuaries\n")
    assert main(["--list"]) == 0 and "ncbitaxon" in capsys.readouterr().out
    assert main([str(tmp_path / "n.csv"), "-o", "envo,ncbitaxon", "--out", str(tmp_path / "o.csv")]) == 0
    err = capsys.readouterr().err
    assert "2 matches for 2 of 2 inputs" in err and "nothing in envo for: Lynx lynx" in err
    assert (tmp_path / "o.csv").exists()


def test_ids_are_looked_up_in_ena_and_the_ontologies(services):
    import importlib
    r = importlib.import_module("verdant.resolve")
    assert [r.kind(x) for x in ("SAMD1", "ERS1", "ERR1", "PRJEB1", "ENVO:00000045", "air")] == \
        ["sample", "sample", "run", "project", "name", "name"]
    assert r.resolve("SAMD1") == [("scientific_name", "air metagenome"), ("broad_scale_environmental_context", "urban biome"),
                                  ("local_environmental_context", "air"), ("environmental_medium", "air")]    # 'missing' left out
    assert r.resolve("ERR1") == r.resolve("SAMD1")
    assert r.resolve("air temperature") == [("name", "air temperature")]
    assert r.resolve("SAMD999") == []


def test_ids_in_predictions_out(services, tmp_path):
    (tmp_path / "ids.csv").write_text("sample_accession\nSAMD1\nEstuaries\nPRJEB1\nSAMD999\n")
    ms = verdant.match(tmp_path / "ids.csv", ["envo", "gold", "natura2000"])
    rows = {(m["term_id"], m["term"], m["ontology"], m["match_curie"] or m["match_id"]): m for m in ms}
    air = rows[("SAMD1", "air", "ENVO", "ENVO:00002005")]
    assert air["category"] == "local_environmental_context|environmental_medium" and air["match_type"] == "skos:exactMatch"
    assert ("SAMD1", "urban biome", "ENVO", "ENVO:01000249") in rows
    assert any(k[0] == "SAMD1" and k[2] == "GOLD" and "Air" in rows[k]["match_label"] for k in rows)   # GOLD kept
    assert rows[("estuaries", "Estuaries", "Natura2000", "n2k:1130")]["match_type"] == "skos:exactMatch"
    assert verdant.match.unresolved == ["SAMD999"]
    assert not any(m["term_id"] == "PRJEB1" for m in ms)            # a project's rows carry its samples' IDs


def test_free_text_and_ena_ids_together(services):
    ms = verdant.match(["SAMD1", "Estuaries"], ["envo"])
    assert {(m["term_id"], m["term"]) for m in ms} >= {("SAMD1", "air"), ("SAMD1", "urban biome"), ("estuaries", "Estuaries")}
    sssom = verdant.to_sssom(ms)
    assert "biosample:SAMD1\t" in sssom and "term:estuaries" in sssom
