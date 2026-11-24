# Referència tècnica


### Variables d'entorn

| Variable | Per defecte | Ús |
|---|---|---|
| `LLENGUA_USER_AGENT` | `llengua-mcp/0.1` | Identificació del client |
| `LLENGUA_CONTACT` | buit | Contacte afegit al `User-Agent` |
| `LLENGUA_RATE` | `1.0` | Peticions per segon i per host (màxim 1.0) |
| `LLENGUA_TIMEOUT` | `45` | Temps màxim per petició, en segons |
| `LLENGUA_MAX_BYTES` | `4000000` | Mida màxima d'una resposta |
| `LLENGUA_MAX_OCCURRENCES` | `50` | Files màximes per pàgina del CTILC |
| `LLENGUA_CACHE_TTL` | `3600` | Validesa de la cache i dels cursors |
| `LLENGUA_DATA_DIR` | dades d'usuari | Dades locals de sinònims, anglès-català i DIRELEX |
| `LLENGUA_CACHE_DIR` | cache d'usuari | Reservat per a cache persistent |

Les variables numèriques han de tenir valors vàlids: `LLENGUA_TIMEOUT` ha de
ser un nombre finit superior a zero; `LLENGUA_MAX_BYTES`,
`LLENGUA_MAX_OCCURRENCES` i `LLENGUA_CACHE_TTL` han de ser enters entre `1` i
el màxim enter de la plataforma. Un valor invàlid provoca un error que indica
la variable. `LLENGUA_RATE` ha de ser finit i després s'ajusta a l'interval
`0.2–1.0`; les comes decimals també s'hi admeten. Si `LLENGUA_RATE` és present
però invàlid, no s'utilitza el valor de reserva `CTILC_RATE`.

## Exemples d'ús

La resposta dona primer la conclusió i després el detall que les fonts ja
consultades permeten: què funciona i per què, quines alternatives canvien el
matís, l'origen documentat i l'ús escrit al CTILC. Si hi ha concordances, es
distingeixen els testimonis que es mostren del total verificat; si hi ha
dispersió validada, es pot explicar on es concentra l'ús. No es fan més
peticions només per afegir detall ni es confon la freqüència amb la correcció.

- **Corregir una construcció**: `optimot_cerca("tenir que", mode="frase_exacta")`
  i `optimot_fitxa(ref)` per justificar *he d'anar* en lloc de *tinc que anar*.
  Si la cerca exacta no dona res, `optimot_cerca("perífrasi d'obligació")`.
- **Veure com s'ha resolt un dubte semblant**: `consultes_iec("tenir que")` o,
  si només vols preguntes, `consultes_iec("tenir", camp="pregunta")`.
- **Comparar dues formulacions**: `diec_consulta("maliciós")` per al sentit i
  `cerca_patro` amb `lema=somriure@subst` + `cg=adj` per als contextos reals.
- **Trobar alternatives**: `cerca_sinonims("maliciós", context="un somriure maliciós")`
  i triar les opcions que conserven el sentit.
- **Trobar un equivalent anglès → català**: `engcat_cerca("bank")` i triar
  l'accepció segons el context. Cerca la forma sencera, sense descompondre
  locucions ni traduir frases. Si no coincideixen les majúscules i minúscules,
  prova sense distingir-les i ho indica amb `match: "case_insensitive"`.
- **Triar alternatives lèxiques**: `direlex_cerca("alegria")` retorna les
  accepcions i els apartats de l'article. Les dades locals del DIRELEX tenen
  llicència CC BY-NC 4.0, per a ús no comercial; no és una font normativa.
- **Consultar solucions de traducció**: `pamies_cerca("bank", glossaris=true)`
  cerca la llista de Xavier Pàmies i, opcionalment, els glossaris literaris.
  Pot retornar compostos; els fragments limitats no substitueixen la font.
- **Consultar frases fetes**: `dsff_cerca("fet una fera")` cerca una expressió
  al DSFF de M. Teresa Espinal. Separa sinònims, altres relacions i variants;
  `valor_antonim` indica un sentit oposat al concepte. La llicència de l'edició
  electrònica és CC BY-NC-SA 4.0 (ús no comercial).
- **TLS del DSFF**: el client dedicat incorpora l'intermediari GEANT TLS RSA 1
  que el servidor no envia. La verificació del domini i de la cadena fins a
  una arrel del sistema continua activa, sense acceptar cadenes parcials.
  No afecta les altres fonts ni segueix redireccions.
- **Documentar una forma antiga o dialectal**: `bdlex_consulta("engrunar")`, o
  cercar per definició: `bdlex_consulta(definicio="esclafar")`.
- **Explicar una regla d'ortografia**: `oiec_cerca("guionet")` i, amb el codi,
  `oiec_text("4.4.2.2")` per llegir l'apartat sencer.
- **Explicar una regla gramatical**: `gramatica_cerca("perífrasi verbal")` i,
  amb el codi, `gramatica_text("28.1")`.
- **Comprovar una expressió**: `cerca_frase("tenir foc al ulls", variants=["tenir foc als ulls"])`.
  Cada variant es retorna per separat; els totals no se sumen.
- **Veure les formes d'un lema i la seva morfologia**: `cerca_lema("somriure")`
  retorna el desglossament de formes amb categoria i codi morfològic, a més
  d'una pàgina d'ocurrències. Per cercar una forma per prefix:
  `cerca_forma("somriu", mode="comença per")`.
- **Veure en quines èpoques apareix**: cerca i, amb el `search_cursor`,
  `dispersio_cronologica(cursor)`.
- **Veure en quines varietats apareix**: `dispersio_dialectal(cursor)` dona per
  varietat `query_hits`, `corpus_hits`, `per_million` i `share_of_query`.
- **Creuar tots els atributs**: `dispersio_general(cursor)` dona la distribució
  per any, varietat, traducció, tipus, gènere literari i classificació temàtica
  en una sola consulta.
- **Restringir a un autor, any o varietat**: `cerca_patro(..., filtres={...})`
  amb `autor`, `titol`, `any_min`/`any_max`, `tipus`, `genere`, `classtem`,
  `varietat` o `traduccio`. Per triar autors, títols o temes vàlids,
  `filtres_disponibles(cursor)` (amb `tipus="temes"` per al `classtem`).
- **Saber quines paraules hi van a prop**: `collocacions("somriure")` — quins
  noms, adjectius o verbs hi coapareixen dins d'una finestra de ±3 mots. Amb
  `collocacions_forma("somriures")` s'aïlla una forma i el lema no barreja el
  nom i el verb; cada resultat porta la informació mútua, la freqüència de
  coaparició, la distància mitjana i la variància.
- **Consultar les obres d'un autor o d'un títol**: `obres(autor="Sagarra")`;
  si hi ha diversos autors, la resposta dona els candidats i cal triar-ne un
  amb `autor_id`. `obres(titol="vida")` retorna any, tipus, gènere,
  classificació, traducció i varietat.

## Com interpretar els resultats

- **`status`**: `ok`, `no_matches` / `no_results`, `partial`, `invalid_query`,
  `upstream_error`, `unexpected_response`, `stale_search`, `ambiguous_author`,
  `too_many_results` o `unavailable`.
  Un error no es converteix mai en `total: 0`.
- **Anglès-català**: `total` i `returned` compten accepcions, no equivalents.
  `no_matches` vol dir que no hi ha coincidències a la revisió consultada;
  `unavailable` indica que l'índex no està instal·lat o no es pot llegir.
  Es conserva el text literal dels equivalents i el resultat inclou `data_revision`.
- **DIRELEX**: `encapcalament` manté junts els mots alternatius i les marques
  originals de cada sentit. Els apartats `c` poden contenir antònims o mots
  relacionats, no necessàriament sinònims. `partial` adverteix de fragments que
  el parser no ha pogut classificar. Les remissions no es resolen automàticament.
- **CTILC**: `echo_verified` exigeix que coincideixin els camps enviats i el
  patró visible. Un zero explícit només és `no_matches` si el comptador sencer
  és vàlid, la pàgina dona el missatge de cap coincidència i no hi ha files de
  concordança, ni tan sols d'incompletes. Si no, és `unexpected_response`.
  Si és `false`, el resultat no es pot presentar com una absència lingüística.
- **`timing`**: cada resposta, també les d'error, porta un bloc amb
  `elapsed_ms`, `upstream_requests` (intents de xarxa, reintents inclosos),
  `cache_hits` i `from_cache`. `from_cache` només és cert quan tota la feina ha
  sortit de la memòria cau HTTP; una eina que treballa amb dades locals no
  compta com a encert de cau. Serveix per veure on se'n va el temps d'una
  sessió, no per interpretar el resultat.
- **`next_cursor`**: continua la mateixa cerca. És local i caduca; si el total
  o el patró canvien, o no es confirma la posició de la pàgina, l'eina retorna
  `stale_search` sense lliurar files ni avançar el cursor. Les
  continuacions del mateix cursor se serialitzen: dues crides concurrents no
  retornen la mateixa pàgina.
- **`search_cursor`**: vincula la cerca amb eines com la dispersió. N'hi ha
  sempre que la cerca sigui vàlida, encara que tots els resultats càpiguen en
  una pàgina; `next_cursor` només hi és si queden pàgines.
- **Dispersió cronològica**: passa el `search_cursor` (o el `next_cursor`)
  d'una cerca concreta. Retorna per tram `hits`, `corpus_units` i `per_million`
  (ocurrències per milió, derivades dels enters del gràfic, mai del percentatge
  arrodonit). Es validen el patró i la suma dels trams; si no coincideixen,
  `data_valid` és fals, `periods` queda buit i les dades sense validar són a
  `unvalidated`. Amb pocs testimonis, parla de concentració observada. Si la
  cerca tenia filtres, la dispersió no els aplica (`filters_not_applied`).
- **Dispersió dialectal**: `share_of_query` és el percentatge de les ocurrències
  de la cerca en cada varietat; `per_million` és la taxa per milió de paraules
  d'aquella varietat i és la mesura per comparar varietats de mides diferents.
  No comparis `query_hits` en brut. La varietat és la de l'obra, no la del
  parlant; un zero pot ser una mancança del corpus. Si `data_valid` és fals,
  `varieties` queda buit i les dades són a `unvalidated`.
- **Dispersió general**: `attributes` conté sis eixos (`any`, `varietat`,
  `traduccio`, `tipus`, `genere`, `classificacio`), cadascun amb `groups`,
  `totals`, `index` i pics. Els quatre eixos complets han de sumar el total de
  la cerca; `genere` cobreix només les obres literàries i `classificacio` les
  no literàries, i es contrasten amb els subtotals de `tipus`. Un desquadre
  (`attribute_totals_mismatch`) invalida la resposta. Compara amb
  `per_million`, no amb `query_hits`.
- **Cerques bàsiques**: `cerca_forma` i `cerca_lema` retornen `total`, el
  desglossament `forms` (lema, categoria, forma i morfologia) i una pàgina
  d'`occurrences`. `mode` pot ser `coincident`, `comença per`, `acaba en`,
  `conté`, `no comença per`, `no acaba en` o `no conté`; els modes negatius
  requereixen `cg`. Per paginar, passa `offset`. L'eco es valida amb els camps
  ocults (`cadforma`/`cadlema`, condició i `cg`) i amb el text visible, que ha
  d'acabar exactament amb la consulta, accents inclosos: un eco de `somriures`
  no valida una cerca de `somriure` ni un zero verificat.
  Aquestes pàgines no apliquen els filtres de `cerca`/`cerca_patro`.
- **Filtres del CTILC**: amb filtres, `total` és la «Quantitat filtrada» i
  `total_unfiltered` la freqüència sense filtres; `filters_verified` ha de ser
  cert. Si el portal no retorna files, el total pot ser un valor de control
  (1): no es presenta com una absència. Si el filtre és d'autor, el nom s'ha
  validat contra el catàleg global i la quantitat filtrada és exactament el
  valor de control 1, es retorna `no_matches` amb `filtered_empty_verified`;
  un total més gran sense files és `unexpected_response` amb
  `filtered_empty_unverified`. `classtem` filtra les obres no literàries per tema
  (grup `3` o subtema `3.2`); no es combina amb `genere` ni amb `tipus=LIT`.
  Un valor de filtre inventat pot donar el total de control; comprova'l amb
  `filtres_disponibles`.
- **Optimot**: el nombre de resultats és un recompte de documents del portal, no
  una freqüència d'ús. Cal obrir la fitxa abans de citar-ne el criteri. Els
  resultats s'ordenen per coincidència amb la consulta (`relevance`) i, si el
  mode és poc precís, `suggested_mode` proposa una alternativa (per exemple,
  `frase_exacta`).
- **Consultes de l'IEC**: són respostes curades, no la norma. Cita la consulta i
  enllaça la font que citen (GIEC, DIEC, Optimot). `camp="pregunta"` limita la
  cerca al títol de la consulta i sol ser més precís que la cerca global. Si el
  portal no retorna el comptador `recordsFiltered` i no hi ha files, la resposta
  és `unexpected_response` amb `records_filtered_missing`, no un zero verificat.
- **DIEC**: cal citar l'entrada i l'accepció. No trobar-hi una forma no la fa
  incorrecta. Els articles llargs es retallen a `max_senses` (20 per defecte);
  si `senses_truncated` és cert, apuja'l per veure les locucions finals.
- **ésAdir**: és estil de la CCMA, no la norma de l'IEC. Una cerca sense resultats
  no demostra que una forma sigui incorrecta. Un `no_results` amb
  `zero_results` és un zero verificat. Si el portal anuncia resultats però no
  se'n pot llegir cap fila, l'eina retorna `unexpected_response`, no un zero
  ni un suggeriment de fitxa. Si apareix `no_entry_results`, la cerca
  no ha trobat cap fitxa d'entrada (pot retornar títols de filmoteca): obre
  `suggested_fitxa` amb `esadir_fitxa` abans de concloure res.
- **BDLex**: agrupa diccionaris de períodes i abasts diferents. Cal citar el
  diccionari concret de cada entrada (`dictionary` / `dictionary_label`) i no
  tractar una forma antiga o dialectal com a adequada per a un text formal
  actual. Una absència tampoc no la fa incorrecta. El
  [DDLC](https://dcc.iec.cat/ddlcI/scripts/index.html) és un recurs separat:
  BDLex es va fer servir per redactar-lo, però `bdlex_consulta` no el consulta.
- **OIEC**: l'ortografia normativa. Cita sempre el codi d'apartat (`codi_text`)
  i el títol de la secció. Un resultat amb només títols és `partial` (no
  `no_results`), i `oiec_text` valida que el codi retornat coincideixi amb el
  sol·licitat: si no, dona error en lloc de presentar un altre apartat.
- **Gramàtiques**: per a un dubte d'ús, la GBU; la GEIEC és la versió en línia;
  la GIEC, la descripció exhaustiva. Cita el codi i el títol. Si el codi retornat
  falta, és buit o no coincideix amb el sol·licitat, l'eina dona error; un total
  sense cap apartat llegible és `partial`, no `no_results`.
- **Col·locacions**: `total` és el recompte del servidor i inclou les files de
  puntuació descartades (`excluded_rows`); `counted_rows` en són les
  aprofitables. `rows` de cada categoria és el nombre disponible abans de
  retallar-lo a `limit`, i `altres` recull els noms propis sense categoria. Cal
  que `lema_echo_verified` sigui cert abans de fer servir les dades.
- **Obres**: `total` és el nombre d'obres que dona el portal i `returned` la
  pàgina; `has_more` i `next_offset` serveixen per continuar. Si el `status` és
  `ambiguous_author`, la llista `authors` porta els candidats i cal repetir la
  consulta amb `autor_id`. `translation` indica una obra traduïda.
- **Sinònims**: són propostes de significat. Cada grup indica `relation`
  (`synonym` o `antonym`); un antònim no es presenta mai com a sinònim. La cerca
  distingeix els accents: `mes` i `més` no comparteixen grups. Si només hi ha
  una coincidència sense accents, `match` és `accent_insensitive` i hi ha
  l'avís `accent_insensitive_match`; si la forma accentuada no existeix, no es
  cau a la variant sense accent. Les comes i els dos punts escapats del fitxer
  (`com més va\, més`) es llegeixen com a part del terme. Amb `context`, els
  grups que hi coincideixen (etiqueta de sentit o formes que hi surten) es
  retornen primer; `context_no_match` vol dir que no s'ha pogut prioritzar cap
  grup. Cal triar les opcions segons la frase i explicar-ne el matís.
- **Jané**: les accepcions numerades (`1.`, `2.`) separen sentits; tria la que
  encaixa en la frase. `mode="general"` cerca el mot també dins les llistes de
  sinònims (no és una cerca per frases) i `mode="funcio"` el cerca per funció
  sintàctica. Cada entrada porta els femenins, les notes d'ús i els enllaços a
  DIEC, DDLC, CTILC, BDLex, DCVB, CiT i TERMCAT. Complementa Softcatalà; no
  barregis les dades dels dos diccionaris. Si falta el comptador
  `recordsFiltered` i no hi ha files, és `unexpected_response` amb
  `records_filtered_missing`, no un zero verificat.

## Límits coneguts

- La revisió automàtica de paràgrafs sencers no forma part de l'abast.
- Les cerques bàsiques del CTILC (`Formes2`, `FormesLema2`) no apliquen els
  filtres de la consulta combinada. Els modes `no comença per`, `no acaba en`
  i `no conté` requereixen `cg`: sense categoria el portal pot donar un fals
  zero. Fes servir una categoria concreta (p. ex. `cg="I"`); `limit` no
  redueix el desglossament que el portal envia i una cerca molt àmplia pot
  superar el límit de mida.
- `obres` cerca per autor o per títol, no les dues coses alhora. Una cerca molt
  àmplia pot superar el límit de resposta (4 MB per defecte); aleshores retorna
  `too_many_results` i cal concretar el títol o l'autor.
- L'exportació CSV del CTILC no s'implementa: extreure moltes files de cop és
  extracció massiva del corpus i queda fora d'abast. Per citar contextos, les
  cerques ja retornen les ocurrències amb el total, el cursor i la data.
- El Corpus de consultes de l'IEC es llegeix amb el nonce de la pàgina i
  l'endpoint AJAX de wpDataTables. Si el portal canvia el nonce o la taula,
  l'eina retorna un error accionable; no se'n fan descàrregues massives.
  Critèria no s'integra (descartat el 20/11/2026): encara que l'API REST
  publica el contingut, la cerca és feble i molt text viu en PDFs enllaçats.
- BDLex no té una API pública documentada: l'adaptador usa el motor de la
  plataforma. Si el servei canvia, caldrà revisar el parser. Les respostes es
  retallen (entrades, accepcions, exemples, subentrades i fonètica) per no
  abocar articles sencers.
- No s'exposa CQL cru ni el camp intern `strquery`.

## Cortesia i aspectes legals

- Límit per defecte: una petició per segon i per host, també per a variants,
  reintents i fitxes. La cache respecta `Cache-Control: no-store`.
- No es fan descàrregues massives ni se salten proteccions.
- No es descarrega l'àudio d'ésAdir de `/back/`, que `robots.txt` bloqueja.
- No es presenten extracts llargs ni se subscriu el projecte com a oficial de
  l'IEC o la CCMA.
- Contacte recomanat abans de publicar o integrar el servei: `dcc@iec.cat`
  (CTILC) i les adreces de contacte de cada font.
- Les dades de sinònims són de Softcatalà i tenen llicència CC BY 4.0; cal
  citar-les. Vegeu `NOTICE`.
- El diccionari de sinònims d'Albert Jané (IEC) és CC BY-NC-ND 3.0: ús no
  comercial, entrades sense transformar i atribució a l'autor i a l'IEC. Les
  respostes inclouen `license` i `attribution`; no es fusionen amb les dades de
  Softcatalà.

## Citació

> Corpus Textual Informatitzat de la Llengua Catalana (CTILC), Institut
> d'Estudis Catalans, <https://ctilc.iec.cat/>, consulta feta el DD/MM/AAAA.

Cada resposta inclou `source` i `retrieved_at`; les eines que en retornen també
porten `citation`. `jane_cerca` substitueix la cita per `license` i
`attribution`, que la llicència del diccionari exigeix.

## Desenvolupament

```sh
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/ruff format .
.venv/bin/ruff check .
.venv/bin/pytest
```

Els tests no fan xarxa i són els que s'executen a cada push. Les proves en
directe són optatives: el workflow `live.yml` les llança un cop per setmana, i
també les pots executar a mà:

```sh
LLENGUA_LIVE=1 .venv/bin/pytest tests/test_live.py
```

### Integració contínua

- `.github/workflows/ci.yml`: `ruff format --check`, `ruff check` i `pytest`
  sense xarxa a Python 3.11, 3.12 i 3.13, a cada push i pull request.
- `.github/workflows/live.yml`: les proves en directe, cada dilluns a les 06:00
  UTC o manualment des de la pestanya Actions, amb un reintent si falla una
  prova per un tall de xarxa puntual. Un error persistent és un avís que una
  font ha canviat el format o no respon.
