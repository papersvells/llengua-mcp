# Estat del projecte i feines pendents

Document de seguiment. Recull què està implementat i verificat, quins límits
coneixem i què queda per fer. No és un pla tancat: les prioritats poden
canviar. Data de la darrera actualització: **18/11/2026**.

Fonts de veritat per al protocol: `pla-mcp-ctilc-critiques.md` (correccions
verificades) i, per a l'abast, `AGENTS.md`.

---

## 1. Estat actual

- **Repositori:** `https://github.com/papersvells/llengua-mcp.git`, branca
  `main`, darrer commit `85a05d5` («Afegeix collocacions del CTILC»).
- **Tests sense xarxa:** 108 passats, 6 omesos (els live).
- **Tests en directe:** 6, opcionals amb `LLENGUA_LIVE=1`.
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
  canvien, es retorna `stale_search`.
- Les xifres de `collocacions` són freqüències de **coaparició dins d'una
  finestra**, no d'adjacència: no es comparen amb `cerca_frase`/`cerca_patro`.
- Rate limit per host, cache TTL en memòria, User-Agent identificable.
- `opencode.jsonc` és local i està ignorat; l'exemple és
  `opencode.jsonc.example`.

### Comprovacions en directe (18/11/2026)

Expectatives datades, no llindars eterns:

- `00*lema=somriure&01*cg=adj:-` → **2.136** (control de `salut`).
- `00*lema=somriure&01*cg=adj:-` amb variants de patró: 1.829 (subst).
- `somriure` + `maliciós` → 32; `tenir foc al/als ulls` → 0 amb eco verificat.
- `collocacions("somriure")` → **1.159** col·locacions, 18 categories;
  top noms: llavi 235, ull 167, home 119; top verbs: va 2192, fer 760.
- Optimot «tenir que» → fitxa 6754/4 (05.04.2023).
- DIEC «maliciós» → 3 accepcions.
- ésAdir «a gust», «hidrosisme» → fitxa i AFI.

---

## 2. Pendents

### 2.1 Collocacions del CTILC (acabat de fer, cal polir)

Implementat a `adapters/ctilc.py` i `parsers/collocacions.py`.

- **Límit intern de 5.** El parser només desa `MAX_PER_CATEGORY = 5` items per
  categoria, però l'eina accepta `limit` fins a 10. Amb `limit=8` es retornen
  silenciosament 5. Cal fer que el parser desi prou items (o que el límit
  intern i el de l'eina coincideixin) i validar-ho amb un test.
- **Sense validació d'eco del lema.** No es comprova que el `<i>` de la pàgina
  coincideixi amb el lema consultat. Si el servidor retorna una altra pàgina,
  el resultat es presenta com a bo.
- **Desquadre `counted_rows` vs `total`.** Amb `somriure`: total 1.159,
  files comptades 1.141. La diferència són les files de puntuació de l'apartat
  ALTRES que es descarten. El codi té un `pass` sense efecte: cal convertir-ho
  en un avís explícit (`partial_rows`) o documentar-ho a la resposta.
- **Apartat ALTRES parcialment filtrat.** Es descarta la puntuació (`,`, `.`,
  `—`, `#NA#`…) perquè no comença per lletra, i els noms propis queden amb
  `pos: null`. Revisar si val la pena separar-los en una clau pròpia en lloc
  de barrejar-los amb les categories gramaticals.
- **Col·locacions d'una forma** (`CTILCQCol_FormesAgrup2.asp`) no
  implementades; només hi ha col·locacions de lema.

### 2.2 Gramàtiques (GBU, GEIEC, GIEC)

- **Fals `no_results`.** `parse_search_hits` fa
  `payload.get("texts") or []`: un diccionari sense `texts` (error de l'API,
  canvi de format) es converteix en una llista buida i es presenta com a «cap
  resultat». Cal distingir «resposta sense `texts`» de «llista buida».
- **Adapter massa tolerant.** Si la resposta no és ni diccionari ni llista,
  l'adaptador també acaba retornant `[]` en lloc d'un error estructurat.
- **Sense verificació del codi retornat.** `parse_text` no comprova que
  `codiText` coincideixi amb el `codi` sol·licitat. El test simulat de la GIEC
  demana `8.3.3` i rep `28.1` i passa igualment. Cal validar-ho i afegir-hi un
  test negatiu.
- **Enllaç del portal de la GIEC.** El prefix actual és
  `https://giec.iec.cat/textgramatica/` sense `/codi/`, però la configuració
  oficial referencia `https://giec.iec.cat/textgramatica/codi/`. Verificar la
  ruta real del frontal (l'SPA retorna 200 per qualsevol ruta, així que no
  serveix com a prova).
- **Codis que són només títol.** L'OIEC va tornar `null` per a `4.1` (títol).
  A les gramàtiques pot passar el mateix: el missatge d'error ja ho insinua,
  però cal provar-ho amb codis de títol reals i documentar-ho.

### 2.3 Dispersió cronològica

- **Requereix `next_cursor`.** `dispersio_cronologica(cursor)` només accepta el
  `next_cursor` d'una cerca, que no existeix quan tots els resultats caben en
  una pàgina. Cal un cursor estable independent de la paginació (o acceptar el
  cursor inicial sempre que es desi).
- **Dades sense validar no s'han de presentar com a bones.** Quan el patró o el
  total no coincideixen, els camps s'inclouen igualment a la resposta. Cal
  decidir si s'ometen o es marquen clarament com a no vàlids.

### 2.4 `salut`

- **Esborra cursors de l'usuari.** Fa servir `self.cursors._entries` per
  eliminar tots els cursors amb la mateixa consulta de control. Si l'usuari ha
  fet exactament aquella cerca, perd el cursor. Cal un cursor propi de `salut`
  o no esborrar res.

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

1. Tancar els retocs de les col·locacions (límit, eco, avís de files
   parcials) amb tests.
2. Reforçar la validació de les gramàtiques (`texts` absent, `codiText`
   divergent) i verificar l'enllaç de la GIEC.
3. Fer servir les eines amb preguntes reals i corregir el que falli abans
   d'afegir fonts noves.
4. Decidir si es reprèn el Corpus de consultes amb una captura real de
   navegador, o si es descarta definitivament.
