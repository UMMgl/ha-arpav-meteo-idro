Sample files of the ARPAV open data (stazioni_idro.xml and station files 0287,
0333, 0334, 0595), downloaded on 15/11/2026 from
https://meteo.arpa.veneto.it/meteo/dati_meteo/xml/ and used unchanged as test
fixtures. Source: ARPAV, automatic data not previously validated, CC BY 4.0
(https://creativecommons.org/licenses/by/4.0/deed.it).

The `arpav_*.json` and `metar_*.json` files are small payloads in the exact
shape served by the ARPAV JSON API (`meteo_meteogrammi_tabella`,
`bollettini_meteo_simboli_en`, `meteo_meteogrammi?rete=MGRAMMIBRI`,
`meteo_brillanza_tabella`) and by the Aviation Weather Center
(`stationinfo`, `metar`), trimmed and with invented station data to exercise
the edge cases (missing fields, empty stations, stale readings). The tests
shift their timestamps to the present because the integration compares them
with the clock. No live service is ever called by the tests.
