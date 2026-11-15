# Hydrometric station ordering

The ARPAV registry checked on 2026-11-15 lists 115 stations in 49 water bodies.
Of these, 23 water bodies have multiple stations (89 gauges), and 26 have one.
The profiles cover 86 of those 89 gauges. Single-station entries keep selection
order. Newly listed or unverified gauges can also be ordered manually.

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
| Canal Bianco | 4 | Po | 3 of 6 |
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
  A verified profile gives connectivity for display. It provides no estimate
  of current flows or gate states.

## Po delta

The profile orders Ficarolo → Polesella → Cavanella Po and retains the
documented junction towards the Po di Pila and Po delle Tolle. The three
terminal gauges (Porto Levante, Porto Barricata and Pila) remain in selection
order because automatic ordering requires a verified attachment to a
hydraulic reach. The [Po Delta Park description](https://www.parcodeltapo.org/pagina.php?id=20)
identifies the Volta Grimana control on the Po di Levante, and the
[Regione Veneto note on Pila](https://www.regione.veneto.it/article-detail?articleId=14324024)
describes the access channel to the fishing port.
