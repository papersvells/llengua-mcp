# Estat del projecte i feines pendents

Document de seguiment. Recull què està implementat i verificat, quins límits
coneixem i què queda per fer. No és un pla tancat: les prioritats poden
canviar. Data de la darrera actualització: **22/11/2026**.

Fonts de veritat per al protocol: `pla-mcp-ctilc-critiques.md` (correccions
verificades) i, per a l'abast, `AGENTS.md`.

---

## 1. Estat actual

- **Repositori:** `https://github.com/papersvells/llengua-mcp.git`, branca
  `main`; els canvis del 18/11/2026 (validacions, dispersió, Corpus i filtres)
  ja són committats i pujats a `origin/main`.
- **Tests sense xarxa:** 298 passats, 20 omesos (els live).
- **Tests en directe:** 20, opcionals amb `LLENGUA_LIVE=1`; tots passen.
- **CI:** `.github/workflows/ci.yml` executa `ruff` i els tests sense xarxa a
  Python 3.11, 3.12 i 3.13 a cada push i pull request.
  `.github/workflows/live.yml` executa les proves en directe cada dilluns a les
  06:00 UTC (o manualment des d'Actions), amb un reintent per absorbir talls de
  xarxa puntuals.
- **Ruff:** `ruff format` i `ruff check` nets.
- **Eines MCP:** 30 eines, agrupades per font.

### Eines per font

| Font | Eines | Estat |
|---|---|---|
| Optimot | `optimot_cerca`, `optimot_fitxa` | Implementat i provat en directe |
| Corpus de consultes IEC | `consultes_iec` | Implementat i provat en directe |
| DIEC | `diec_consulta` | Implementat i provat en directe |
| ésAdir | `esadir_consulta`, `esadir_fitxa` | Implementat i provat en directe |
| BDLex | `bdlex_consulta` | Implementat i provat en directe (DCVB inclòs) |
| OIEC | `oiec_cerca`, `oiec_text` | Implementat via `api-oiec.iec.cat` |
| Gramàtiques | `gramatica_cerca`, `gramatica_text` | Implementat (GBU, GEIEC, GIEC) |
| Softcatalà | `cerca_sinonims` | Dades locals versionades (CC BY 4.0) |
| Jané | `jane_cerca` | Implementat i provat en directe (CC BY-NC-ND 3.0) |
| CTILC | `cerca`, `cerca_frase`, `cerca_forma`, `cerca_lema`, `cerca_patro`, `continuar_cerca`, `context`, `dispersio_cronologica`, `dispersio_dialectal`, `dispersio_general`, `collocacions`, `collocacions_forma`, `filtres_disponibles`, `obres`, `xifres`, `etiquetes`, `salut` | Implementat i provat en directe |

### Decisions consolidades

- Un zero només es presenta com a absència si la pàgina dona un comptador
  explícit `0` **i** l'eco coincideix amb la consulta enviada.
- Els IDs de resultat del CTILC es tracten com a `string` (enters de 64 bits).
- Els cursors són locals, amb la consulta original; si el total o el patró
  canvien, es retorna `stale_search`. `search_cursor` vincula eines com la
  dispersió encara que no quedin pàgines; `next_cursor` només serveix per
  paginar.
- La dispersió només es presenta com a vàlida si el patró i els totals quadren.
  Si no, `data_valid` és fals, `periods` queda buit i les dades crues van a
  `unvalidated`.
- Amb filtres, `total` és la «Quantitat filtrada» i `total_unfiltered` el total
  sense filtres. Un resultat filtrat sense files no es presenta com una
  absència: el portal pot retornar un total de control.
- Les xifres de `collocacions` són freqüències de **coaparició dins d'una
  finestra**, no d'adjacència: no es comparen amb `cerca_frase`/`cerca_patro`.
  Cal validar `lema_echo_verified` i recordar que `total` inclou les files de
  puntuació descartades (`excluded_rows`).
- `classtem` accepta un sol subtema per consulta (el portal no en combina dos)
  i els grups sencers van a `classtemGSelec`. És incompatible amb `genere` i
  amb `tipus=LIT`.
- Amb filtre d'autor validat al catàleg global, un resultat sense files és
  `no_matches` (`filtered_empty_verified`) només si la quantitat filtrada és el
  valor de control 1; un total més gran sense files és `unexpected_response`
  (`filtered_empty_unverified`). Un autor inexistent és `invalid_query`, també
  a `cerca_frase`. Si la validació falla, la cerca continua amb
  `author_validation_skipped`.
- Rate limit per host, cache TTL en memòria, User-Agent identificable.
- `opencode.jsonc` és local i està ignorat; l'exemple és
  `opencode.jsonc.example`.

### Comprovacions en directe (18/11/2026)

Expectatives datades, no llindars eterns:

- `00*lema=somriure&01*cg=adj:-` → **2.136** (control de `salut`).
- `00*lema=somriure&01*cg=adj:-` amb variants de patró: 1.829 (subst).
- `somriure` + `maliciós` → 32; `tenir foc al/als ulls` → 0 amb eco verificat.
- `collocacions("somriure")` → **1.159** files al servidor, **1.141**
  aprofitables, **18** de puntuació descartades, **17** categories i **84**
  noms propis a `altres`; top noms: llavi 235, ull 167, home 119; top verbs:
  va 2192, fer 760. Amb `limit=8` es retornen 8 verbs.
- `collocacions_forma("somriures")` → **80** col·locacions, **69**
  aprofitables, **11** de puntuació i **15** categories; top adjectius: forçat
  6 (MI 11,59), irònic 5 (11,27), amable 9 (10,53). Un `zzzz` dona el missatge
  explícit sense comptador (`zero_without_counter`).
- Gramàtiques: GIEC `8.3.3` → «La posició dels pronoms febles», amb l'enllaç
  `https://giec.iec.cat/textgramatica/codi/8.3.3`; GBU codi `28` (només títol)
  → error accionable.
- Dispersió d'una cerca d'una sola pàgina (`somriure maliciós`, 32): hi ha
  `search_cursor` sense `next_cursor`; la dispersió torna `ok` amb
  `data_valid: true` i 10 trams.
- Filtres del CTILC (`somriure` + adj, 2.136): varietat **central** → 1.237;
  autor **Sagarra** → 42; **1960–1961** → 25; gènere **narrativa** → 1.567;
  tipus **LIT** → 1.932; **sense traducció** → 1.899.
  `filtres_disponibles(autors)` → 413 autors. Un autor inventat dona
  `unexpected_response` (total 1, 0 files), no un zero.
- Optimot «tenir que» → fitxa 6754/4 (05.04.2023).
- Corpus de consultes de l'IEC: `consultes_iec("tenir")` → **257** (1.176 en
  total), 7 temes; `tema="Sintaxi"` → **347**; `camp="pregunta"` amb «tenir» →
  **12**. L'endpoint necessita el nonce de la pàgina i `table_id=7`.
- DIEC «maliciós» → 3 accepcions.
- ésAdir «a gust», «hidrosisme» → fitxa i AFI.
- Jané (20/11/2026): 27.547 entrades; `jane_cerca("maliciós")` → 2 accepcions
  numerades; `mode="general"` amb «mala fe» → 3 entrades (arteria, malícia,
  traïdoria); `mode="funcio"` amb «casa» i funció nominal → 92 resultats;
  `zzzqqqxyz` → `no_results` amb comptador 0.
- Filtres del CTILC (20/11/2026): `classtem=@3.2` → 4 ocurrències (de 2.136),
  grup `@3` → 29, `filtres_disponibles(tipus="temes")` → 53 valors; autor
  **Sagarra, Josep M. de** → 42; **Sagarra, Xavier** → `no_matches` amb
  `filtered_empty_verified`; autor inventat → `invalid_query`.

---

## 2. Pendents

### 2.1 Collocacions del CTILC (resolt el 18–19/11/2026)

Implementat a `adapters/ctilc.py` i `parsers/collocacions.py`; verificat en
directe amb `somriure` (lema) el 18/11/2026 i amb `somriures` (forma) el
19/11/2026.

- **Límit intern de 5: resolt.** El parser desa totes les files (la pàgina en
  porta 1.159) i l'adaptador retalla a `limit` (1-10). La resposta indica
  `rows` per categoria i l'avís `collocations_truncated` si s'ha retallat.
  Amb `limit=8` es retornen 8 verbs.
- **Eco del lema: resolt.** Es valida el `<i>` de la pàgina
  (`lema_echo_verified`). Si no coincideix, `unexpected_response`, avís
  `lema_echo_unexpected` i cap categoria. S'accepta el sufix d'homonímia
  (`altre_1`).
- **Desquadre de files: resolt.** `total` 1.159, `counted_rows` 1.141,
  `excluded_rows` 18 (puntuació) i avís `partial_rows`, explicat a `note`.
- **Apartat ALTRES: resolt.** Els 84 noms propis es retornen a `altres`; les 18
  files de puntuació es descarten.
- **Col·locacions d'una forma: resolt el 19/11/2026.** Eina
  `collocacions_forma` sobre `CTILCQCol_FormesAgrup2.asp` (`cadforma`). La
  pàgina té sis columnes per fila (informació mútua, freqüència de coaparició,
  distància mitjana, variància i freqüència del lema) en lloc de dues; el
  parser detecta el format i n'extreu les mètriques. Comprovat amb `somriures`:
  **80** col·locacions, **69** aprofitables, **11** de puntuació, **15**
  categories; adjectius forçat 6 (MI 11,59), irònic 5 (11,27) i amable 9
  (10,53), que el lema `somriure` no aïllava. Sense resultats, el portal només
  dona un missatge sense comptador: es retorna `unexpected_response` amb
  `zero_without_counter`, no una absència verificada.

### 2.2 Gramàtiques (GBU, GEIEC, GIEC) (resolt el 18/11/2026)

- **Fals `no_results`: resolt.** `parse_search_hits` exigeix el camp `texts`
  quan la resposta és un objecte; un objecte sense `texts`, un `texts` que no
  sigui llista o un tipus inesperat són `unexpected_response`.
- **Adapter massa tolerant: resolt.** El total i els hits surten del parser, que
  és l'única font; ja no es converteix un payload desconegut en `[]`.
- **Codi retornat: resolt.** `parse_text` compara `codiText` amb el codi
  sol·licitat i dona error si divergeix. Hi ha test negatiu.
- **Enllaç de la GIEC: resolt.** El bundle Angular confirma
  `textgramatica` → `codi/:codi`; el prefix és
  `https://giec.iec.cat/textgramatica/codi/`. Verificat amb `8.3.3`.
- **Codis de títol: verificat.** `text_by_cody?codi=28` de la GBU retorna
  `contingut: null`; l'eina dona l'error accionable («Aquest apartat no té text
  llegible») i hi ha test.
- **Nodes sense contingut en una cerca:** es retorna `partial` amb l'avís
  `no_readable_sections`, no `no_results`.

### 2.3 Dispersió cronològica (resolt el 18/11/2026)

- **Cursor estable: resolt.** `search()` retorna `search_cursor` sempre que la
  cerca és vàlida (`ok`/`no_matches`), encara que tots els resultats càpiguen en
  una pàgina. `next_cursor` continua existint només quan queden pàgines.
  `dispersio_cronologica` accepta tots dos.
- **Dades no validades: resolt.** Si el patró o els totals no coincideixen,
  `data_valid` és fals, `periods` queda buit, `totals` i els pics són `null`, i
  les dades crues passen a `unvalidated`, amb un `error` explicatiu. No es
  presenten com a resultats.

### 2.4 `salut` (resolt el 18/11/2026)

- **Ja no esborra cursors de l'usuari.** `search()` accepta
  `persist_cursor=False`; `salut` el fa servir i no toca el `CursorStore` ni
  retorna cursors. Un cursor d'usuari amb la mateixa consulta de control
  sobreviu al diagnòstic (test específic).

### 2.5 CTILC: eines ajornades

- **Filtres per autor, títol, any, tipus, gènere, varietat i traducció:
  resolts el 18/11/2026.** `cerca`, `cerca_frase` i `cerca_patro` accepten
  `filtres`; el cursor els desa i `continuar_cerca` els reenvia.
  `filtres_disponibles` llista autors i títols amb recompte. Amb filtres,
  `total` és la «Quantitat filtrada» i `total_unfiltered` la freqüència sense
  filtres; si no hi ha files, el portal pot retornar `1` com a valor de
  control i es tracta com a `unexpected_response`, no com una absència.
- **`classtem` i validació global d'autors: resolts el 20/11/2026 (issue
  [#4](https://github.com/papersvells/llengua-mcp/issues/4) tancada).**
  `classtem` és la classificació temàtica decimal de les obres no literàries;
  el portal l'envia amb `classtemSelec` (un sol subtema) i `classtemGSelec`
  (grups sencers `@3@1`). Comprovat: `@3.2` → 4 ocurrències (de 2.136) i
  `@3` → 29, amb `filters_verified: true`. El portal **no combina dos
  subtemes** en una sola consulta (retorna el total de control 1): l'eina ho
  rebutja i demana un subtema o grups sencers. `filtres_disponibles` accepta
  `tipus="temes"` (panell `filt=lang`, 53 valors amb recompte dins del
  resultat). `genere` i `classtem` són excloents.
  La validació d'autors consulta el catàleg global (`CTILCCorpus_Aut1.asp`):
  un autor inexistent dona `invalid_query` amb suggeriments, i un autor real
  sense cap ocurrència dona `no_matches` amb `filtered_empty_verified` quan la
  quantitat filtrada és el valor de control 1 (un total més gran sense files és
  `unexpected_response` amb `filtered_empty_unverified`). La validació també
  s'aplica a `cerca_frase`. Si la validació no es
  pot fer, la cerca continua amb l'avís `author_validation_skipped`.
- **Obres descarregables: descartat (issue #1 tancada el 19/11/2026).** No es
  farà cap eina de descàrrega d'obres: l'MCP no baixa textos sencers. Les
  metadades per autor i títol ja són a `obres` i el context d'una ocurrència a
  `context`.
- **Exportació CSV: descartada (issue #2 tancada el 19/11/2026).** L'únic
  valor seria extreure moltes files de cop, que és extracció massiva del corpus
  i queda fora d'abast. Per citar i llegir contextos n'hi ha prou amb les
  ocurrències, el total, el cursor i la data que ja retorna la cerca. A més,
  `Qjson_concordancesCSV.asp` no està verificat (500 a totes les variants).
- **Cerca de noms propis: descartada (issue #5 tancada el 20/11/2026).** Per
  decisió de producte no es farà l'eina sobre `CTILCQConc_NomsPropis2.asp`.
  Els noms propis no estan analitzats morfosintàcticament i la cerca és només
  per forma gràfica; no s'hi dedicarà cap eina.

### 2.6 Fonts encara no integrades

- **Corpus de consultes lingüístiques de l'IEC: resolt el 18/11/2026.** Eina
  `consultes_iec`. La pàgina `/cerca-general/` porta el nonce
  `wdtNonceFrontendServerSide_7`; amb els paràmetres DataTables complets,
  l'AJAX de wpDataTables retorna les 1.176 consultes. Es poden filtrar per tema
  (Fonètica, Lèxic, Morfologia, Onomàstica, Ortografia, Sintaxi, Altres) i per
  pregunta. Els intents anteriors donaven zero perquè faltava el nonce i es
  feia servir `table_id=1` (la portada) en lloc de `7`.
- **Critèria.** Descartat el 20/11/2026 (issue
  [#7](https://github.com/papersvells/llengua-mcp/issues/7) tancada). La
  verificació d'aquell dia mostra que l'API REST publica 455 posts i és
  integrable, però s'ha decidit no fer-ho: la cerca de text és sobretot de
  títols («cursiva» → 0) i molt contingut viu en PDFs enllaçats; per a
  ortografia i gramàtica ja cobrim l'OIEC i les gramàtiques.
- **Sinònims Jané: implementat el 20/11/2026 (issue
  [#8](https://github.com/papersvells/llengua-mcp/issues/8) tancada).** Eina
  `jane_cerca` sobre `sinonims.iec.cat` (wpDataTables, com el Corpus de
  consultes): nonce + `admin-ajax.php` amb tres taules (1 lema, 4 general, 5
  funció sintàctica). 27.547 entrades; les accepcions numerades (`1.`, `2.`)
  separen sentits, cosa que resol el punt feble de Softcatalà amb
  `context_no_match` (per exemple, «maliciós»: «1. malpensat, desconfiat,
  malfiat / 2. murri, trapella, viu, caut, recelós»). Llicència CC BY-NC-ND 3.0:
  consulta en directe, entrades sense transformar i atribució a Albert Jané i a
  l'IEC; no es fusiona amb les dades de Softcatalà.
- **El DDLC no forma part de BDLex (verificat el 21/11/2026, issue
  [#9](https://github.com/papersvells/llengua-mcp/issues/9)).** Segons la
  [presentació de BDLex](https://bdlex.iec.cat/scripts/IniPresentacio.asp),
  la base va ser una font complementària per redactar el DDLC, que té
  [un portal propi](https://dcc.iec.cat/ddlcI/scripts/index.html).
  L’enllaç al DDLC a `jane_cerca` apunta a aquest altre recurs.

#### Catàleg de BDLex verificat el 21/11/2026

Els codis dels 15 diccionaris del
[selector de consulta avançada](https://bdlex.iec.cat/scripts/Qorth1av.asp)
coincideixen amb els que accepta `bdlex_consulta`. El portal mostra
`DIEC2e`, `DIEC2` i `DIEC1`, però els valors que envia al motor són `DIEe`,
`DIE2` i `DIEC`, respectivament.

S’han fet quatre cerques exactes per codi, enviant un sol `dict[]` cada
vegada: `key_ext=<mot>&key_ext_type=exact&element=entry&dict[]=<codi>&result_type=ids`.
S’han obert els articles retornats pel seu `entry_id[]`: tots tenien
l’atribut XML `dict` del diccionari demanat. En cada cerca amb resultats,
almenys una fitxa corresponia a la forma o clau normalitzada i contenia
una definició o traducció. Les xifres són **fitxes retornades pel motor**
(poden incloure variants), no accepcions.

| Codi a `dicts` | Obra | `casa` | `pa` | `aigua` | `maliciós` | Verificació |
|---|---|---:|---:|---:|---:|---|
| `DIEe` | DIEC2 en línia | 1 | 1 | 1 | 1 | Verificat |
| `DIE2` | DIEC2 (2007) | 1 | 1 | 1 | 1 | Verificat |
| `DIEC` | DIEC1 (1995) | 1 | 1 | 1 | 1 | Verificat |
| `DGFP` | Ferrer Pastor (1985) | 1 | 3 | 1 | 1 | Verificat |
| `DCVB` | Alcover–Moll | 4 | 5 | 9 | 1 | Verificat |
| `DGLC` | Fabra (1932) | 1 | 1 | 1 | 1 | Verificat |
| `DPCV` | Vallès, *Pal·las* (1927) | 1 | 1 | 1 | 1 | Verificat |
| `DGMG` | Martí i Gadea (1891) | 6 | 4 | 18 | 4 | Verificat |
| `DMCT` | Tarongí (1878, inacabat) | 3 | 0 | 3 | 0 | Verificat |
| `NDMA` | Amengual (1858) | 3 | 1 | 4 | 1 | Verificat |
| `DVCE` | Escrig (1851) | 5 | 1 | 6 | 3 | Verificat |
| `DMCF` | Figuera (1840) | 7 | 5 | 5 | 1 | Verificat |
| `DLCL` | Labèrnia (1839–1840) | 2 | 3 | 4 | 2 | Verificat |
| `DEBJ` | Esteve, Bellvitges i Juglà (1803–1805) | 2 | 3 | 1 | 1 | Verificat |
| `DMFC` | Febrer i Cardona (s. XIX) | 2 | 5 | 3 | 1 | Verificat |
| — (prova amb `DDLC`) | Diccionari descriptiu de la llengua catalana | 0 | 0 | 0 | 0 | Fora del catàleg |

Amb `dict[]=DDLC`, el motor ha retornat un XML buit a cadascuna de les
quatre proves. Aquests zeros sols no demostren que el codi no sigui admès;
la conclusió es basa en el selector i en el catàleg publicat per l’IEC.

### 2.7 Legal i publicació

- Contactar **`dcc@iec.cat`** abans de publicar o integrar l'MCP en un
  producte.
- Citar sempre el CTILC i l'IEC; no usar el logo de l'IEC ni presentar-se com
  a oficial. Quan se citi una resposta del Corpus de consultes, enllaçar la
  consulta concreta.
- No redistribuir extracts extensos ni obres protegides.

### 2.8 ésAdir: el zero de la cerca (resolt el 19/11/2026)

`esadir_consulta("hidrosisme")` retornava `unexpected_response` tot i que la
pàgina diu «Cap resultat»: el contenidor `#resultats` és buit i no hi ha
comptador. Ara el parser reconeix el bloc `.noResultat` com un zero explícit
(`count = 0`), l'adaptador torna `no_results` amb l'avís `zero_results` i
conserva `suggested_fitxa`; ja no apareix `parse_partial`. Hi ha una fixture
(`esadir_zero.html`) i tests de parser i d'adaptador.

### 2.9 Proves d'ús real (resolt el 18/11/2026)

Proves fetes amb preguntes reals (les tres d'acceptació i casos límit) per
detectar problemes que els tests no veuen.

- **DIEC: articles massa llargs.** `diec_consulta("fe")` retornava 56
  accepcions de `fer²` i un article enorme. Ara hi ha `max_senses` (20 per
  defecte, fins a 50), `senses_total` i `senses_truncated`, amb l'avís
  corresponent. Amb `max_senses=20`, `mala fe` (accepció 18 de `fe²`) hi és.
- **ésAdir: la cerca exacta no trobava entrades.** `esadir_consulta("a gust")`
  retornava títols de filmoteca i cap entrada, tot i que `esadir_fitxa("a gust")`
  funciona. Ara les fitxes d'entrada van primer i, si no n'hi ha cap, s'afegeix
  l'avís `no_entry_results` i `suggested_fitxa` per obrir-la directament.
- **Col·locacions massa grans.** `collocacions("altre")` supera el límit de
  4 MB de resposta i fallava amb un error genèric. Ara l'error és accionable:
  indica apujar `freq_min` o triar un lema més específic.
- **Servidor MCP antic a OpenCode.** El procés MCP carregat en iniciar la sessió
  no recarrega el codi: durant aquestes proves responia amb la versió anterior
  a les fases de validació, dispersió, Corpus i filtres. Cal reiniciar l'editor
  o el servidor després de canviar el codi; ho hem documentat al README. Les
  correccions s'han verificat amb l'`App` directa i amb els tests en directe.

### 2.10 Sinònims i Optimot (resolt el 19/11/2026)

- **`cerca_sinonims` ja fa servir el `context`.** Abans l'acceptava i només el
  tornava com a `context_note`. Ara les agrupacions amb una etiqueta de sentit
  que apareix al context (`(cel)`, `(color)`) o amb una forma que hi surt es
  retornen primer; cada grup porta `context_score` i `context_match`, i la
  resposta indica `context_ranked` i `context_matches`. Si cap grup no hi
  coincideix, l'avís és `context_no_match`: el diccionari no porta definicions
  i no sempre es pot desambiguar.
- **`optimot_cerca` ordena i avisa.** Els resultats s'ordenen per coincidència
  amb la consulta (`relevance`: `title`, `snippet`, `tokens` o `none`). Si la
  consulta és multiparaula i el mode `fitxes`/`basica` no hi troba cap
  coincidència, o el portal retorna més de 200 documents, s'afegeixen
  `low_relevance`/`many_results` i `suggested_mode: "frase_exacta"`. Un
  `frase_exacta` sense resultats proposa `fitxes`.

### 2.11 Obres del CTILC (resolt el 19/11/2026)

Eina `obres(autor?, titol?, autor_id?, limit?, offset?)`. Consulta
`CTILCCorpus_Aut1.asp`/`Aut2.asp` (autor) i `CTILCCorpus_Obr2.asp` (títol) i
retorna any, tipus, gènere, classificació temàtica, traducció i varietat, amb
`total`, paginació i `echo_verified`.

- Si un cognom dona més d'un autor, retorna `ambiguous_author` amb `authors` i
  cal continuar amb `autor_id`; un nom exacte es tria sol.
- La llista no es pagina al portal i una cerca massa àmplia pot superar el
  límit de 4 MB: es retorna `too_many_results` amb una pista, no un error.
- Comprovat en directe: `obres(autor="Sagarra, Xavier")` → 1 obra (Diari de
  Barcelona, 1992); `obres(titol="vida")` → 65 obres, 3 retornades amb
  `limit=3`; `obres(autor="sagarra")` → 5 candidats.
- `obres_descarregables` (`CTILCCorpus_Descarr.asp`): **descartat** el
  19/11/2026. No es descarregaran obres des de l'MCP; l'eina `obres` dona les
  metadades.

### 2.12 Dispersió dialectal del CTILC (resolt el 19/11/2026)

Eina `dispersio_dialectal(cursor)`, amb el mateix cursor que la dispersió
cronològica. Consulta `CTILCQDispersionsDial.asp` i llegeix el gràfic
`Proporció`, que porta al tooltip el numerador i el denominador de cada
varietat.

- Retorna per varietat `query_hits`, `corpus_hits`, `per_million` (derivat dels
  enters) i `share_of_query`; a més, `index`, `totals`, `peak_absolute` i
  `peak_relative`.
- Es validen el patró i la suma de les ocurrències; si no quadren, `data_valid`
  és fals, `varieties` queda buit i les dades van a `unvalidated`.
- Comprovat en directe amb `somriure` + adjectiu (2.136 ocurrències): central
  1.237 (57,91% de la cerca; 13,51 per milió), baleàric 364 (33,82 per milió).
  El pic relatiu és baleàric encara que el pic absolut sigui central: els
  subcorpus tenen mides molt diferents.
- Avís: la varietat és la de l'obra, no la del parlant; el corpus és escrit i un
  zero pot ser una mancança.
- Queda pendent la dispersió general (`CTILCQDispersions.asp`).

### 2.13 Cerques bàsiques `Formes2` i `FormesLema2` (resolt el 19/11/2026)

Eines `cerca_forma(forma, mode?, cg?, limit?, offset?)` i
`cerca_lema(lema, mode?, cg?, limit?, offset?)`. Consulten
`CTILCQConc_Formes2.asp` i `CTILCQConc_FormesLema2.asp` amb `seccio=CTILC1`.

- Retornen `total`, el desglossament `forms` (lema, categoria, forma,
  morfologia i recompte) i una pàgina d'`occurrences`, amb `page`, `pages`,
  `has_more` i `next_offset`.
- Modes verificats: 0 coincident, 1 comença per, 2 acaba en, 3 conté.
  El 21/11/2026 també es van verificar 4 `no comença per`, 5 `no acaba en`
  i 6 `no conté` amb `cg="I"` en tots dos endpoints. Els modes negatius
  requereixen `cg` perquè el portal pot retornar un fals zero sense categoria.
  Els controls i els cossos POST consten a `pla-mcp-ctilc-critiques.md` §3.7
  ([#6](https://github.com/papersvells/llengua-mcp/issues/6)).
- La paginació és `iStart`/`iOffset` i no necessita el `resultat`; es pot
  demanar qualsevol pàgina amb `offset`.
- El panell `formesSelec` té ordres diferents: `form|lema CG|CM` a `Formes2` i
  `lema CG|form|CM` a `FormesLema2`.
- Comprovat en directe: `cerca_forma("somriu")` → 2.019 ocurrències i 6 formes;
  `cerca_forma("somriu", mode="comença per")` → 10.628;
  `cerca_lema("somriure")` → 14.290 ocurrències i 122 formes.
- Aquestes pàgines no apliquen els filtres de `cerca`/`cerca_patro`.

### 2.14 Dispersió general del CTILC (resolt el 19/11/2026)

Eina `dispersio_general(cursor)`, amb el mateix cursor que les altres
dispersions. Consulta `CTILCQDispersions.asp` i llegeix els gràfics
`Repartiment` (ocurrències de la cerca) i `Total`/`Totals` (corpus) de cada
atribut.

- Retorna `attributes` amb sis eixos: `any`, `varietat`, `traduccio`, `tipus`,
  `genere` i `classificacio`. Cada eix té `groups`, `totals`, `index`,
  `peak_absolute` i `peak_relative`.
- `genere` cobreix només les obres literàries i `classificacio` les no
  literàries: els seus totals no han de coincidir amb el total general.
- Es validen el patró, el total de la cerca i la suma de l'eix `any`; si no
  quadren, `data_valid` és fals, `attributes` queda buit i les dades van a
  `unvalidated`.
- Comprovat en directe amb `somriure` + adjectiu (2.136): `any` 10 trams,
  `varietat` 6 grups, `traduccio` 2 (1.899 originals / 237 traduccions),
  `tipus` 2 (1.932 literaris / 204 no literaris), `genere` 4 i `classificacio`
  10; els índexs de dispersió del portal també es recullen.
- Nota: `per_million` és la mesura per comparar grups de mides diferents; la
  varietat, el gènere i el tema són de l'obra, i el corpus és escrit.

### 2.15 Acceleració de les respostes (resolt el 21/11/2026)

Issue [#10](https://github.com/papersvells/llengua-mcp/issues/10).

- **Instrumentació.** Totes les eines retornen un bloc `timing` (també quan el
  resultat és un error) amb `elapsed_ms`, `upstream_requests` (intents de xarxa,
  reintents inclosos), `cache_hits` i `from_cache`. `from_cache` només és cert si
  tota la feina ha sortit de la memòria cau HTTP; una eina amb dades locals no
  compta com a encert. S'implementa amb un `ContextVar` al client HTTP
  (`RequestMeter`), de manera que les eines no han de passar comptadors.
- **Escalfament de sinònims.** El servidor carrega l'índex de Softcatalà en
  segon pla en arrencar (`lifespan` del servidor MCP, `asyncio.to_thread`). La
  primera `cerca_sinonims` ja no paga la lectura; si les dades falten, només
  falla aquesta eina. Un `asyncio.Lock` evita carregar-lo dues vegades si la
  primera consulta arriba abans que acabi l'escalfament.
- **Nonce de `consultes_iec`.** Ja es reutilitzava durant 600 s amb un reintent
  si l'AJAX falla. S'hi ha afegit un pany perquè diverses crides simultànies no
  demanin la pàgina del nonce més d'un cop, i perquè dos refrescos concurrents
  no en facin dos.
- **Mesura del flux de 10 crides** (stdio, xarxa real, 21/11/2026; el flux és
  `optimot_cerca`, `diec_consulta`, `esadir_consulta`, `cerca_sinonims`,
  `cerca_frase`, `collocacions`, `consultes_iec`, `diec_consulta("fe", 25)`,
  `bdlex_consulta`, `cerca_sinonims`):

| Estat | Total | Primera `cerca_sinonims` |
|---|---:|---:|
| Abans (19/11/2026) | 13,8 s | 1,0 s |
| Abans, reproduït el 21/11/2026 | 14,116 s | 1,362 s |
| Després, 1a mesura | 12,669 s | 0,002 s |
| Després, 2a mesura | 11,499 s | 0,002 s |

  La resta del temps és xarxa i espaiat: `collocacions` (~2,2 s), `diec_consulta`
  amb 25 accepcions (~3,4 s) i `consultes_iec` (~2,4 s, dues peticions: nonce i
  AJAX). Cap canvi no apuja el ritme per sobre d'1 req/s per host.
- **Guia d'ús eficient** a `AGENTS.md` §15: agrupar consultes independents,
  evitar `salut` per sistema i no repetir cerques equivalents.


### 2.16 Fals zero amb filtres d'autor (resolt el 22/11/2026)

Issue [#11](https://github.com/papersvells/llengua-mcp/issues/11).
`search()` convertia qualsevol total filtrat positiu sense files en
`no_matches` amb `total: 0` si l'autor s'havia validat, no només el valor de
control 1.

- Ara només el total 1 es converteix en `no_matches`
  (`filtered_empty_verified`); un total més gran sense files és
  `unexpected_response` amb `filtered_empty_unverified`.
- `cerca_frase` valida l'autor abans de consultar cap variant i passa
  `filter_query` a `search()`, així que un autor inexistent dona
  `invalid_query` amb suggeriments i el zero filtrat es pot verificar.

Comprovat en directe el 22/11/2026: `Sagarra, Xavier` → `no_matches` (0 de
2.136); `Sagarra, Josep M. de` → 42; `cerca_frase("somriure maliciós")` amb
aquest autor → 1 ocurrència; autor inventat → `invalid_query`.

### 2.17 Eco de les cerques bàsiques (resolt el 22/11/2026)

Issue [#12](https://github.com/papersvells/llengua-mcp/issues/12). Els modes
positius de `cerca_forma` i `cerca_lema` validaven l'eco amb una comprovació
de subcadena sobre un text sense accents: `somriure` acceptava un eco de
`somriures` i el zero es presentava com a verificat.

- Ara es comparen els camps ocults de `fConc` (`cadforma`/`cadlema`, la
  condició i `cg`) i el text visible ha d'acabar exactament amb la consulta,
  amb accents; la comparació de majúscules no distingeix.
- Sense camps ocults, o amb un mode o una categoria diferents, l'eco no es
  considera verificat (`echo_unexpected`); el zero passa a
  `unexpected_response`.
- Les fixtures positives inclouen ara el formulari `fConc`, com la pàgina real.

Comprovat en directe el 22/11/2026: `somriu` (2.019), `Somriu` (2.019),
`somriures` (605), `somri` amb `comença per` (14.731) i `somriure` com a lema
(14.290) donen `echo_verified: true`; `zzzz` dona `no_matches` verificat.

### 2.18 Tots els eixos de la dispersió general (resolt el 22/11/2026)

Issue [#13](https://github.com/papersvells/llengua-mcp/issues/13). Només es
validava l'eix `any`; un altre eix podia sumar un nombre d'ocurrències
diferent del total de la cerca i la resposta continuava amb `data_valid:
true`.

- Els eixos complets (`any`, `varietat`, `traduccio`, `tipus`) han de sumar el
  total de la cerca.
- `genere` i `classificacio` es contrasten amb els subtotals de `tipus`, com ja
  es feia.
- Qualsevol desquadre dona `attribute_totals_mismatch`, invalida la resposta
  (`data_valid: false`, `attributes` buit, dades a `unvalidated`) i deixa
  l'estat en `partial`.

Comprovat en directe el 22/11/2026 amb tres consultes: `somriure` + adjectiu
(2.136), `maliciós` (564) i `xiuxiuejar` (713). En totes, els quatre eixos
complets sumen exactament el total i la resposta continua sent vàlida.

### 2.19 Accents a la cerca de sinònims (resolt el 22/11/2026)

Issue [#14](https://github.com/papersvells/llengua-mcp/issues/14). L'índex de
Softcatalà plegava els accents, així que `mes` i `més` compartien clau i, amb
un `limit` baix, es podien retornar només els grups del sentit equivocat.

- L'índex desa una clau exacta (minúscules, accents conservats) a més de la
  plegada. La consulta exacta té prioritat i no es barreja amb l'altra.
- La variant plegada només s'usa quan la consulta **no porta accents**; llavors
  la resposta porta `match: "accent_insensitive"` i l'avís
  `accent_insensitive_match`.
- Si la consulta porta accents i la forma no existeix, és `no_results`: `més`
  no retorna els grups de `mes`.

Comprovat amb les dades locals el 22/11/2026: `mes` → conjunció i nom;
`més` → adverbis; `dona` → nom; `dóna` → `no_results`; `opinio` → coincidència
aproximada amb avís. La coma escapada de `com més va\, més` és un problema
separat ([#19](https://github.com/papersvells/llengua-mcp/issues/19)).

### 2.20 Comptador absent a wpDataTables (resolt el 22/11/2026)

Issue [#15](https://github.com/papersvells/llengua-mcp/issues/15). Si una
resposta de wpDataTables no portava `recordsFiltered`, el parser feia
`total = len(results)`: amb zero files, l'eina afirmava que no hi havia cap
consulta o cap entrada.

- Els parsers de Consultes IEC i Jané comparteixen ara
  `parsers/wpdatatables.py`. Un comptador absent amb files dona el nombre de
  files i l'avís `records_filtered_missing`; absent i sense files dona
  `total: null`.
- Els adaptadors tracten `total: null` com a `unexpected_response` amb
  `records_filtered_missing`, mai com a `no_results`.
- Un `recordsFiltered: 0` explícit continua sent un zero verificat.

Comprovat en directe el 22/11/2026: `consultes_iec("tenir")` → 257 i
`jane_cerca("maliciós")` → 1, sense avisos; el comptador hi és.

### 2.21 Resultats i codis de l'OIEC (resolt el 22/11/2026)

Issue [#16](https://github.com/papersvells/llengua-mcp/issues/16). Una cerca
amb nodes de títol (sense `contingut`) es presentava com a `no_results`, i
`oiec_text` no comprovava que el `codiText` retornat fos el sol·licitat.

- Si hi ha `total_hits > 0` però cap apartat llegible, l'estat és `partial` amb
  l'avís `no_readable_sections`. Una llista buida continua sent `no_results`.
- `parse_text` compara el codi retornat amb l'esperat. Si en falta o és
  diferent, és `unexpected_response`; no es presenta un altre apartat.
- Comprovat en directe el 22/11/2026: `4.2.1` retorna el seu text; `4.1`, que
  l'API retorna tot nul, dona l'error accionable en lloc d'un text buit.

---

## 3. Comandes útils

```sh
# Tests sense xarxa
.venv/bin/python -m pytest -q

# Tests en directe (opcionals)
LLENGUA_LIVE=1 LLENGUA_DATA_DIR=./data .venv/bin/python -m pytest tests/test_live.py -q

# Format i lint
.venv/bin/ruff format .
.venv/bin/ruff check .

# Consulta manual de col·locacions
LLENGUA_DATA_DIR=./data .venv/bin/python - <<'PY'
import asyncio
from llengua_mcp.app import App
from llengua_mcp.config import Settings

async def main():
    app = App(Settings.from_env())
    try:
        r = await app.ctilc.collocacions("somriure", limit=3)
        print(r["total"], r["returned_categories"])
    finally:
        await app.aclose()

asyncio.run(main())
PY

# Consulta manual amb filtres
LLENGUA_DATA_DIR=./data .venv/bin/python - <<'PY'
import asyncio
from llengua_mcp.app import App
from llengua_mcp.config import Settings
from llengua_mcp.models import CtilcFilters, PatternElement

ELEMENTS = [
    PatternElement(type="lema", value="somriure"),
    PatternElement(type="cg", category="adj"),
]

async def main():
    app = App(Settings.from_env())
    try:
        base = await app.ctilc.search_pattern(ELEMENTS, limit=1)
        filtrat = await app.ctilc.search_pattern(
            ELEMENTS, limit=1, filters=CtilcFilters(varietat=["central"])
        )
        print(filtrat["total"], filtrat["total_unfiltered"], filtrat["filters_verified"])
        valors = await app.ctilc.filtres_disponibles(
            base["search_cursor"], tipus="autors", limit=5
        )
        print(valors["total"], [v["value"] for v in valors["values"]])
    finally:
        await app.aclose()

asyncio.run(main())
PY
```

---

## 4. Properes passes suggerides

Les feines obertes es segueixen al repositori:

1. CTILC: tancades les issues de modes 4–6 amb `cg` ([#6](https://github.com/papersvells/llengua-mcp/issues/6)), `classtem` i validació d'autors ([#4](https://github.com/papersvells/llengua-mcp/issues/4)) i descart de la cerca de noms propis ([#5](https://github.com/papersvells/llengua-mcp/issues/5)).
2. Acceleració: `timing`, escalfament de l'índex i nonce compartit, resolts a §2.15 ([#10](https://github.com/papersvells/llengua-mcp/issues/10)).
3. Fora del repositori, pendents de decisió: contactar amb `dcc@iec.cat` abans
   de publicar (§2.7) i repetir les proves d'ús des d'OpenCode amb dos models.
4. Reiniciar el servidor MCP després de cada canvi i repetir una consulta de
   fum abans de donar per bona una versió.
