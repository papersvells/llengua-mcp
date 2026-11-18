# Estat del projecte i feines pendents

Document de seguiment. Recull què està implementat i verificat, quins límits
coneixem i què queda per fer. No és un pla tancat: les prioritats poden
canviar. Data de la darrera actualització: **18/11/2026**.

Fonts de veritat per al protocol: `pla-mcp-ctilc-critiques.md` (correccions
verificades) i, per a l'abast, `AGENTS.md`.

---

## 1. Estat actual

- **Repositori:** `https://github.com/papersvells/llengua-mcp.git`, branca
  `main`; els retocs de validació del 18/11/2026 ja són committats.
- **Tests sense xarxa:** 131 passats, 7 omesos (els live).
- **Tests en directe:** 7, opcionals amb `LLENGUA_LIVE=1`; tots passen.
- **Ruff:** `ruff format` i `ruff check` nets.
- **Eines MCP:** 21 eines, agrupades per font.

### Eines per font

| Font | Eines | Estat |
|---|---|---|
| Optimot | `optimot_cerca`, `optimot_fitxa` | Implementat i provat en directe |
| DIEC | `diec_consulta` | Implementat i provat en directe |
| ésAdir | `esadir_consulta`, `esadir_fitxa` | Implementat i provat en directe |
| BDLex | `bdlex_consulta` | Implementat i provat en directe (DCVB inclòs) |
| OIEC | `oiec_cerca`, `oiec_text` | Implementat via `api-oiec.iec.cat` |
| Gramàtiques | `gramatica_cerca`, `gramatica_text` | Implementat (GBU, GEIEC, GIEC) |
| Softcatalà | `cerca_sinonims` | Dades locals versionades (CC BY 4.0) |
| CTILC | `cerca`, `cerca_frase`, `cerca_patro`, `continuar_cerca`, `context`, `dispersio_cronologica`, `collocacions`, `xifres`, `etiquetes`, `salut` | Implementat i provat en directe |

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
- Les xifres de `collocacions` són freqüències de **coaparició dins d'una
  finestra**, no d'adjacència: no es comparen amb `cerca_frase`/`cerca_patro`.
  Cal validar `lema_echo_verified` i recordar que `total` inclou les files de
  puntuació descartades (`excluded_rows`).
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
- Gramàtiques: GIEC `8.3.3` → «La posició dels pronoms febles», amb l'enllaç
  `https://giec.iec.cat/textgramatica/codi/8.3.3`; GBU codi `28` (només títol)
  → error accionable.
- Dispersió d'una cerca d'una sola pàgina (`somriure maliciós`, 32): hi ha
  `search_cursor` sense `next_cursor`; la dispersió torna `ok` amb
  `data_valid: true` i 10 trams.
- Optimot «tenir que» → fitxa 6754/4 (05.04.2023).
- DIEC «maliciós» → 3 accepcions.
- ésAdir «a gust», «hidrosisme» → fitxa i AFI.

---

## 2. Pendents

### 2.1 Collocacions del CTILC (resolt el 18/11/2026)

Implementat a `adapters/ctilc.py` i `parsers/collocacions.py`; verificat en
directe amb `somriure` el 18/11/2026.

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
- **Pendent:** col·locacions d'una forma (`CTILCQCol_FormesAgrup2.asp`); només
  hi ha col·locacions de lema.

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

- Cerques bàsiques dedicades amb `Formes2` / `FormesLema2` (ara `cerca` va per
  `Coocur2` amb un sol element).
- Dispersió dialectal i general.
- Obres i obres descarregables.
- Filtres per autor, any, gènere i varietat: el formulari els té, però cal
  verificar-los amb fixtures abans de publicar-los.
- **Exportació CSV:** `Qjson_concordancesCSV.asp` no està verificat i a les
  proves va retornar 500. No implementar com a eina estable fins a capturar
  una exportació real.

### 2.6 Fonts encara no integrades

- **Corpus de consultes lingüístiques de l'IEC.** Investigat i aturat: el
  contingut (1.176 consultes) sembla només accessible via JavaScript, però la
  conclusió «no és possible sense navegador» **no està establerta**. Cal
  capturar la petició real del navegador (XHR) abans de descartar-ho. Les
  crides provades a wpDataTables retornaven `recordsTotal: 1176` i
  `recordsFiltered: 0`.
- **Critèria.** Només explorat parcialment. L'API REST `/wp-json/wp/v2/types`
  respon; no hi ha evidència que no tingui contingut cercable. Cal revisar-ho
  abans de descartar-ho.
- **Sinònims Jané.** No implementat. Revisar si aporta alguna cosa respecte de
  Softcatalà.
- **Cobertura del DDLC a BDLex.** Afirmada en converses anteriors sense
  verificació específica; comprovar-ho si es vol citar.

### 2.7 Legal i publicació

- Contactar **`dcc@iec.cat`** abans de publicar o integrar l'MCP en un
  producte.
- Citar sempre el CTILC i l'IEC; no usar el logo de l'IEC ni presentar-se com
  a oficial.
- No redistribuir extracts extensos ni obres protegides.

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
```

---

## 4. Properes passes suggerides

1. Fer servir les eines amb preguntes reals i corregir el que falli abans
   d'afegir fonts noves.
2. Decidir si es reprèn el Corpus de consultes amb una captura real de
   navegador, o si es descarta definitivament.
