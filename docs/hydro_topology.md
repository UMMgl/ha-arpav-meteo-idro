# Hydrometric station ordering

The ARPAV registry checked on 2026-11-15 lists 115 stations in 49 water bodies.
Of these, 23 water bodies have multiple stations (89 gauges), and 26 have one.
The profiles cover all 89 gauges. Single-station entries keep selection
order. Newly listed or unverified gauges follow the profiled ones in selection order
(there is no manual order since 0.16.0).

| Profile | Covered gauges | Profile | Covered gauges |
| --- | ---: | --- | ---: |
| Adige | 7 | Fratta | 2 |
| Agno | 2 | Gorzone | 2 |
| Alpone | 2 | Guà | 5 |
| Astico | 2 | Livenza | 5 |
| Bacchiglione | 7 | Meschio | 3 |
| Biois | 2 | Monticano | 4 |
| Boite | 3 | Muson dei Sassi | 3 |
| Brenta | 6 | Piave | 11 |
| Canal Bianco | 4 | Po | 6 |
| Chiampo | 2 | Posina | 2 |
| Cordevole | 5 | Retrone | 2 |
| Frassine | 2 | | |

## Verification

- The [ARPAV registry](https://meteo.arpa.veneto.it/meteo/dati_meteo/xml/stazioni_idro.xml)
  supplies station names and IDs. Location identifies the gauged reach on the
  map. The order is taken from directed paths through the hydrographic network.
- The [ARPAV hydrographic graph](https://gaia.arpa.veneto.it/layers/idrografia:geonode:v_idrografia_rete)
  is available through the [ARPAV WFS](https://gaia.arpa.veneto.it/geoserver/ows?service=WFS&version=1.0.0&request=GetCapabilities)
  as `geonode:v_idrografia_rete`. Each stored path references its endpoint
  `HYDROID` values. Consecutive directed reaches were traced through their
  shared map vertices. The stored graph collapses intermediate vertices for
  display. The data are attributed to ARPAV under [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/).
  The Bacchiglione profile carries its existing cartographic references.
- The [Regione Veneto graph specification](https://bur.regione.veneto.it/BurvServices/pubblica/Download.aspx?name=3866_AllegatoE_211894.pdf&storico=False&type=9)
  §6.1.1 allows a conventional direction where the flow direction cannot be
  established. In regulated reaches such as the Canal Bianco, the order
  follows the documented network and [AIPo waterway route](https://www.agenziapo.it/idrovia/idrovia-fissero-tartaro-canalbianco-po-di-levante).
  Canal Bianco reaches carry medium confidence because that route establishes
  connectivity, while flow direction may depend on regulation.
  A verified profile gives connectivity for display. It provides no estimate
  of current flows or gate states.

## Po delta

The Po di Venezia profile orders Ficarolo → Polesella → Cavanella Po, then
passes through the documented Pila/Tolle junction. The two branches are
separate. Their relative display positions imply no upstream/downstream
relationship between the branches.

| ARPAV gauge | Attachment | Evidence |
| --- | --- | --- |
| Pila (561) | Po di Pila, near the terminal distributaries | [AIPo SIAP+Micros inventory](https://www.agenziapo.it/file/16312/download?token=15D4MRyu), Table 1, station 25; [ARPAV 2019 discharge report](https://www.arpa.veneto.it/api/temi-ambientali/idrologia/file-e-allegati/rapporti-e-documenti/idrologia-regionale/idrologia-regionale-la-rete-idrometrica/misure-di-portata/rel_0620_misure_q_arpav_2019.pdf/%40%40download/file/%40actions#page=23), Tavola 05; WFS HYDROID 114007 to 2242 |
| Porto Barricata (552) | Lower Po delle Tolle | ARPAV 2019 Tavola 05; [Regione Veneto decree 377/2013](https://bur.regione.veneto.it/BurvServices/Pubblica/DettaglioDecreto.aspx?id=264573); WFS HYDROID 7637 to 10042 |

ARPAV's [hydrometric station 561](https://meteo.arpa.veneto.it/meteo/dati_meteo/xml/0561.xml)
matches AIPo's Pila gauge coordinates to within about 10 m. ARPAV's
[station 663](https://meteo.arpa.veneto.it/meteo/dati_meteo/xml/0663.xml)
is a separate weather station at the fishing port in the Barbamarco lagoon.

### Porto Levante

ARPAV publishes [station 319](https://meteo.arpa.veneto.it/meteo/dati_meteo/xml/0319.xml)
under Po and identifies it as a Po di Levante gauge in its
[2024 hydrometric report](https://www.arpa.veneto.it/api/temi-ambientali/idrologia/file-e-allegati/rapporti-e-documenti/idrologia-regionale/idrologia-regionale-la-rete-idrometrica/livelli-idrometrici-della-rete-arpav/rel_0225_livelli_2024.pdf/%40%40download/file). Its documented waterway follows the Canal Bianco,
passes the Po-Brondolo junction near Volta Grimana, and reaches Porto Levante.
The ARPAV WFS depicts this lower route on HYDROID 36564 to 8213. The
[Po Delta Park](https://www.parcodeltapo.org/pagina.php?id=20) identifies the control
at Volta Grimana, and [AIPo](https://www.agenziapo.it/idrovia/idrovia-fissero-tartaro-canalbianco-po-di-levante)
documents the waterway from Baricetta to the mouth. The profile places 319 on
that separate route with medium confidence for directional display. In the Po
list it appears after the Po di Venezia stations as a display convention. The
graph has no directed reach from Cavanella Po to Porto Levante.
