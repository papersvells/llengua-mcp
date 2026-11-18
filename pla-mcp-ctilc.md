# Pla: servidor MCP per al CTILC (Institut d'Estudis Catalans)

**Data:** 18 de novembre de 2026  
**Estat:** protocol de la web reverse-engineered i provat en directe; implementació pendent  
**Base:** https://ctilc.iec.cat/

## 1. Objectiu

Construir un servidor MCP (Model Context Protocol) que permeti a un agent LLM consultar el **CTILC** (Corpus textual informatitzat de la llengua catalana: >100 milions de mots, 7.200+ obres, 1832–2022, anotat morfosintàcticament) sense navegador: només HTTP pla, amb resultats estructurats.

## 2. Arquitectura observada

- Servidor **IIS 8.5 (Windows) + ASP clàssic**. Sense API moderna, sense JSON (llevat d'un endpoint CSV), sense autenticació ni tokens.
- **Tota la lògica de consultes és al client**: el JavaScript de cada pàgina construeix les peticions; el protocol és observable llegint el codi font.
- El motor intern és un motor de corpus anotat amb **sintaxi tipus CQP** (IMS Corpus Workbench) i **etiquetes EAGLES/Parole** (p. ex. `NP00000` = nom propi). Evidències:
  - L'echo del patró retorna sintaxi CQP: `somriure []? []? []? mala fe`.
  - L'enllaç «Reportar un error» fuga la consulta interna: `[lemma="somriure(_.)?( .*)?" & !tag="NP00000"] [tag="A:.*|AF:.*|AI:.*"]`.
- **Cache server-side de resultats**: cada consulta generada rep un `resultat` (ID numèric, p. ex. `179499746019557630`) i `Qlocali` (recompte). Les pàgines de resultats, filtres i dispersions el reutilitzen.
- Sense `robots.txt` ni `sitemap.xml`; `/scripts/` no llista directori (redirigeix a la consulta per defecte). Cap protecció anti-bot detectada (a diferència d'ARCA o Gallica).

## 3. Mapa d'endpoints

**Consulta bàsica**
- `CTILCQConc_FormesLema1.asp` — Lema → POST a `..._2.asp`
- `CTILCQConc_Formes1.asp` — Forma → POST a `CTILCQConc_Formes2.asp` amb camps `cadforma`, `cadformacond` (admet truncaments)
- `CTILCQConc_NomsPropis1.asp` — Nom propi

**Consulta complexa (Combinacions)**
- `CTILCQConc_Coocur0.asp` — pàgina marc (frames + iframes)
- `CTILCQConc_Coocur1.asp` — frameset; `..._1b.asp` — formulari d'elements; `..._1a.asp` — constructor del patró (via `location.search`)
- `CTILCQConc_Coocur2.asp` — **resultats** (POST obligatori; GET → error 500)

**Col·locacions**
- `CTILCQCol_LemesAgrup1.asp`, `CTILCQCol_FormesAgrup1.asp`

**Anàlisi de resultats**
- `CTILCQDispersions.asp`, `CTILCQDispersionsCron.asp`, `CTILCQDispersionsDial.asp`
- `CTILCQjson_concordancesCSV.asp` — exportació CSV (POST; form `fCSV` amb `cCSV1` = HTML de la taula + camps d'ordre `*NC`)

**Bibliogràfic / corpus**
- `CTILCQDadesNum.asp` — el corpus en xifres
- `CTILCCorpus_Aut1.asp`, `CTILCCorpus_Obr1.asp`, `CTILCCorpus_ObrParam.asp` — obres per autor / títol / paràmetres
- `CTILCCorpus_Descarr.asp` — obres descarregables (domini públic, format editable)
- `CTILCQFitxaLocalitzacio.asp?id=…&tok=no&seccio=CTILC1&obra=N` — fitxa de l'obra d'una ocurrència

## 4. Gramàtica de patrons (provada)

POST a `CTILCQConc_Coocur2.asp`, body `application/x-www-form-urlencoded`:

```
seccio=CTILC1&00*lema=somriure&01*cg=adj%3A-&02*forma=mala&03*forma=fe
```

- `seccio=CTILC1` — constant (corpus complet 1832–2022; altres seccions desconegudes).
- **Elements posicionals** `NN*clau=` amb `NN` = 00, 01, 02… per cada posició del patró:
  - `lema=` — lema (totes les formes); admet `lema@CG` (lema + categoria)
  - `forma=` — forma gràfica exacta
  - `formalema=` — subconjunt de formes d'un lema (separador intern `¬`)
  - `cg=` — categoria lèxica i/o morfològica, format `cat:morf` (p. ex. `adj:-`, `A:MP`, `V:3PT`); `qualsevol` = comodí
- **Modificadors de valor:**
  - `|` — alternança multi-valor (`amb%7Cde`)
  - `<>` — negació (`%3C%3Eamb` = «tot menys amb»)
  - `( )` — element opcional (`%28qualsevol%29` → `[]?`); **cadena d'opcionals = interval de 0-N mots**
- **Codificacions:** `|`→%7C, `<`→%3C, `>`→%3E, `(`→%28, `)`→%29, `:`→%3A (recomanat).
- Categories vistes al desplegable: `adj`, `subst`, `verb`, `NP` (nom propi), `AV`, `AR`, `C`, `CT`, `DEM`, `IND`, `IFX`, `I`, `L`, `LA`, `NC`, `NUM`, `POS`, `PFX`, `PO`, `P`, `QUA`, `REL`, `SIG`, `SFX`; codis morfològics: `IF`, `GE`, participis `RMS/RFS/RMP/RFP`, persones `1PI`–`6IS`, `1PT`–`6PT`, `1FU`–`6FU`, `1PS`–`6PS`, `1CO`–`6CO`, imperatius, `M/F/S/P/D`…

**Límit de nivell CQP:** cap endpoint accepta CQL cru (sonda via `strquery` → patró buit). Tot s'ha de compilar a la gramàtica anterior. Els rangs `[]{2,5}` s'emulen amb cadenes de `(qualsevol)`.

## 5. Flux de la consulta Combinacions (provat pas a pas)

1. **POST** a `CTILCQConc_Coocur2.asp` amb `seccio=CTILC1` + elements `NN*`.
2. La resposta HTML conté:
   - `Patró seleccionat: …` (echo, sintaxi interna CQP visible)
   - `Freqüència total: N`
   - `resultat` (ID de cache) i `Qlocali` (recompte) dins el JS `obreDispersions(...)`
   - Taula d'ocurrències (KWIC): per fila, tres cel·les amb enllaç a la fitxa de l'obra:
     ```html
     <td align='right'>…context esquerre…</td>
     <td align='center'><a … class="pclau">nucli (mots matchejats)</a></td>
     <td align='left'>…context dret…</td>
     ```
3. **Paginació:** re-POST amb els mateixos paràmetres + `iStart` (1-based) i `iOffset` (50/500/1000). Exemple verificat: 2.136 ocurrències = pàgines `iStart=1,1001,2001` amb `iOffset=1000`.
4. **Filtres** (camps del form `fConc`): `autSelec`, `titSelec`, `anySelec`, `tipusSelec`, `genSelec`, `classtemSelec`, `classtemGSelec`, `tradSelec`, `varSelec`, `filtres`, `mostrat`, `aleatoriVal`, `aleatoriSel`, `resultat_orig`.
5. **Ordenació:** camps `ordreposN`, `ordreelemN`, `ordreadN` (i `*NC` per al CSV).
6. **CSV:** POST a `CTILCQjson_concordancesCSV.asp` amb `cCSV1` (HTML de la taula `cHTML1`) + camps d'ordre `*NC`.
7. **Dispersions:** POST amb `tipusorig="Coocurrències"`, `cadlema`, `cadlemacondtxt`, `resultat`, `Qlocali`, `seccio` a `CTILCQDispersions{,Cron,Dial}.asp`.

## 6. Parsing dels resultats (pegues verificades)

- **Regex tolerant** per als nuclis (alguns porten etiquetes internes i dobles espais!):
  ```js
  [...html.matchAll(/class="pclau">([\s\S]*?)<\/a>/g)]
    .map(m => m[1].replace(/<[^>]*>/g," ").replace(/&nbsp;/g," ").replace(/\s+/g," ").trim())
  ```
  Amb un regex no tolerant es perden ~14 files per pàgina de 500 (semblen «amagades», però són un bug de parsing — 2.087 vs 2.136 en el cas provat).
- Comptador i patró:
  ```js
  t.match(/Patró seleccionat<\/b>:&nbsp;&nbsp;([\s\S]*?)<\/td>/)
  t.match(/Freqüència total<\/b>:&nbsp;&nbsp;(\d+)/)
  ```
- Contexts esquerre/dret: tres `<td>` per fila amb `align='right'` / `'center'` / `'left'`.
- Fitxa d'obra: extreure `obra=N` i `id=` de l'`onClick` de cada enllaç.
- Els «zeros» són zeros reals del corpus quan el patró echo és correcte (contrastar sempre l'echo).

## 7. Disseny de l'MCP

### Tools proposades

| Tool | Entrada | Endpoint |
|---|---|---|
| `cerca_patro` | `elements: [{tipus, valor, opcional?, negat?, multi?}]`, `filtres?` | POST `Coocur2.asp` → `{patro_echo, freq_total, resultat_id, nuclis[]}` |
| `ocurrencies` | `resultat_id`, `i_start`, `i_offset=1000` | re-POST paginat |
| `collocacions` | `paraula`, `tipus: lema\|forma`, `distancia 1-5` | `QCol_*Agrup1.asp` |
| `dispersions` | `resultat_id`, `eix: tot\|cron\|dial` | `QDispersions*.asp` |
| `cerca_forma` | `forma` (truncaments admesos) | POST `Formes2.asp` (`cadforma`, `cadformacond`) |
| `cerca_lema` | `lema`, `categoria?` | `FormesLema2.asp` |
| `obres` | `autor?`, `titol?`, `parametres?` | `Corpus_Aut1/Obr1/ObrParam.asp` |
| `fitxa_obra` | `id`, `obra` | `FitxaLocalitzacio.asp` |
| `exportar_csv` | `resultat_id` | `Qjson_concordancesCSV.asp` |
| `corpus_xifres` | — | `QDadesNum.asp` |

`cerca_patro` compila els elements a `NN*clau=valor` amb l'encoding de l'apartat 4.

### Implementació

- **Stack:** Python + `FastMCP` + `requests` + `selectolax`/`BeautifulSoup` (o TypeScript + `@modelcontextprotocol/sdk`). Un únic fitxer ~300–500 línies.
- **Cap navegador**: tot són POST/GET d'HTML renderitzat al servidor.
- **Cache local** (TTL, per query+pàgina) + reutilització del `resultat_id` server-side.
- **Rate limit cortès:** ~1 petició/segon, reintent amb backoff si `500`.
- **Golden tests** (valors verificats aquesta sessió — serveixen de regressió):
  - `00*lema=somriure & 01*cg=adj:-` → **2.136** ocurrències (995 parelles diferents, 879 adjectius)
  - `00*lema=somriure & 01*forma=amb|de & 02*forma=mala & 03*forma=fe` → **0**
  - `00*lema=somriure & 01-03*cg=(qualsevol) & 04*forma=mala & 05*forma=fe` → **0**
  - `00*forma=mala & 01*forma=fe` → **294**; `mala fé` → 29
  - `00*cg=qualsevol & 01*forma=de & 02*forma=mala & 03*forma=fe` → **75** (nuclis coneguts: *actuar, homes, crítica, litigants…*)
  - forma `somriure mofeta` → **8**

### Fases

1. **Fase 1 (MVP, ~1 dia):** `cerca_patro` + `ocurrencies` + parsing + golden tests.
2. **Fase 2 (+1–2 dies):** filtres, `collocacions`, `dispersions`, `exportar_csv`.
3. **Fase 3 (+1 dia):** `obres`/`fitxa_obra`/`corpus_xifres`, documentació, proves amb preguntes reals.
4. **Manteniment:** baix (site estable des de fa anys); re-executar golden tests si canvien URLs.

## 8. Cortesia i marc legal

- Ús privat i de recerca: sense fricció detectada.
- No fer descàrregues massives; cachejar i limitar el ritme.
- Si el servidor MCP es publiqués o integrés en producte: contactar prèviament `dcc@iec.cat`.

## Apèndix: cas d'ús que va motivar el pla

Verificació de la frase «somriure de/amb mala fe» (totes les formes del lema, amb i sense interval de 0–3 mots): **0 al CTILC**, 0 a ARCA (premsa 1860–1938, control «de mala fe» → 4.657), 0 a Gallica (control «de mala fe» → 132–173) i 0 al web català; attestation només en francès (*sourire de mauvaise foi*, 4 a Gallica) i marginalment en castellà modern. El català ho expressa adjectivalment: *somriure burleta* (40), *irònic* (39), *maliciós* (31), *sorneguer* (26), *fals* (8), *mofeta* (8)…
