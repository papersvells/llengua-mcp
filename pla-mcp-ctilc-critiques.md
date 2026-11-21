# Crítiques i correccions al pla de l'MCP del CTILC

**Revisió:** 18 de novembre de 2026  
**Document revisat:** `pla-mcp-ctilc.md`  
**Base:** <https://ctilc.iec.cat/>  
**Mètode:** lectura crítica del pla + comprovacions HTTP en directe, amb peticions limitades (~1 req/s) i un `User-Agent` de revisió. No s'ha fet cap descàrrega massiva ni s'ha intentat saltar cap protecció.

**Veredicte:** el pla és una base sòlida —identifica bé el flux principal, la gramàtica `NN*clau` i el mecanisme de paginació—, però **no s'ha d'implementar literalment**. Hi ha errors de protocol que produeixen falsos zeros, un model d'estat que es trenca amb els identificadors de 64 bits i diversos golden tests que no proven el que diuen. La feina de reverse engineering és bona; la feina de validació encara és incompleta.

---

## 0. Resum executiu

### Punts forts

- El flux principal (`POST` a `CTILCQConc_Coocur2.asp` amb `seccio=CTILC1` i elements `NN*clau=valor`) és correcte i verificat.
- La gramàtica bàsica (`lema`, `forma`, `formalema`, `cg`, `|`, `<>`, `()`, `qualsevol`) és substancialment correcta.
- La paginació 1-based amb `iStart`/`iOffset` i l'exemple 1.000 + 1.000 + 136 són correctes.
- El consell de **contrastar sempre l'echo** és encertat; de fet, és el que permet detectar els errors d'aquest mateix pla.
- La idea de cachejar i limitar el ritme és necessària, no només cortesa.
- L'apèndix planteja un cas d'ús lingüístic interessant i adequat per a un MCP de corpus.

### Correccions imprescindibles abans de codificar

1. **`01-03*cg=(qualsevol)` no és una clau vàlida.** El servidor la ignora; el `0` del golden test és un **fals zero**. Cal expandir-la a `01*cg`, `02*cg`, `03*cg`.
2. **`00*forma=somriure mofeta` no és el que sembla.** El servidor converteix l'espai en `_` i busca un sol element; els 8 resultats surten de `00*forma=somriure&01*forma=mofeta`. El pla barreja cerca bàsica i cerca per combinacions.
3. **`cg=adj` sol provoca HTTP 500.** Cal `adj:-`; el guionet no és ornamental. El compilador ha de validar-ho.
4. **`<>` i `()` no es poden combinar.** `(<>amb)` retorna HTTP 500. El pla els presenta com a modificadors independents.
5. **L'ID `resultat` és un enter de 64 bits.** En JavaScript/JSON perd precisió; un ID arrodonit retorna el total correcte però **0 files**. Ha de ser `string` a tot arreu.
6. **`ocurrencies(resultat_id)` no és suficient.** Cal un cursor amb la consulta original, `Qlocali` i el patró; `resultat` sol no és un cursor.
7. **`requests`/`httpx` amb un `dict` envien `00%2Alema`** i el servidor respon 500. Cal construir el cos manualment amb `*` literal.
8. **`collocacions` apunta a l'endpoint del formulari, no al de resultats.** Els resultats són a `QCol_LemesAgrup2.asp`, i fan falta `radiE`, `radiD` i `freqMin`.
9. **`fitxa_obra` no és una fitxa d'obra, sinó de localització.** El paràmetre `obra` de la URL no és l'ID canònic de l'obra; cal llegir `Id. obra` de la pàgina.
10. **L'exportació CSV no està verificada i, a les proves, falla amb 500.** No es pot prometre com a tool de la fase 2 sense una captura real del navegador.
11. **`strquery` sí que és un canal CQL intern** (modificar el filtre de tags va canviar el recompte de 2.136 a 1.591), però no és una API general: el CQL simplificat i els rangs `[]{0,3}` retornen 0. L'afirmació «cap endpoint accepta CQL cru» és massa absoluta.
12. **El corpus no és estàtic.** Creix uns 5 milions de paraules l'any; els golden tests amb números fixos quedaran obsolets. Cal registrar data/versió i preveure una deriva.

---

## 1. Matriu de verificació

| Afirmació del pla | Estat | Evidència (18/11/2026) |
|---|---|---|
| `POST` a `Coocur2.asp` amb `seccio=CTILC1` + `NN*` | ✅ | `00*lema=somriure&01*cg=adj:-` → 2.136 |
| `GET` a `Coocur2.asp` dona 500 | ✅ | 500, pàgina ASP genèrica |
| `iStart` 1-based; 1.000/1.000/136 | ✅ | `iStart=1,1001,2001` amb `iOffset=1000` |
| `iStart=0` és equivalent a 1 | ❌ | Retorna 999 files, no 1.000 |
| `resultat` + `Qlocali` dins el JS | ✅ | `resultat=179500525152020580`, `Qlocali=2136` |
| `resultat` és un ID numèric estable | ⚠️ | És global i gran; en JS perd precisió |
| `01-03*cg=(qualsevol)` és vàlid | ❌ | Clau ignorada; echo sense `[]?`; fals zero |
| `forma` admet frases | ❌ | Espai → `_`; `somriure mofeta` → 0 a Coocur i a Formes2 |
| `cg=adj:-` és la forma correcta | ✅ | 2.136; `cg=adj` sol → 500 |
| `<>` i `()` es poden combinar | ❌ | `(<>amb)` → 500 |
| `lema@CG` funciona | ✅ | `somriure@V` → 8.606 |
| `lema:CG` funciona | ❌ | `somriure:V` → 0 |
| `formalema` amb `¬` funciona | ✅ | Dues formes de *somriure* → 3.489 |
| `QCol_*Agrup1.asp` és el endpoint de resultats | ❌ | `Agrup1` és el formulari; resultats a `Agrup2` |
| `FitxaLocalitzacio` és una fitxa d'obra | ⚠️ | És una fitxa de localització amb context i metadades |
| `obra=N` de la URL és l'ID de l'obra | ❌ | `obra=6` → `Id. obra: 8`; `obra=4542` → `Id. obra: 4534` |
| CSV amb `cCSV1` funciona | ❌/⚠️ | Totes les variants provades → 500; cal captura real |
| `strquery` no és un canal CQL executable | ❌ | És executable; modificar tags canvia el recompte |
| `robots.txt` i `sitemap.xml` no existeixen | ✅ | Tots dos 404 |
| IIS 8.5 | ✅ | La pàgina d'error 404 ho diu; la capçalera `Server` és `IEC_HTTP_Server` |
| Corpus >100 M paraules | ✅ | 126.604.218 |
| Corpus anotat morfosintàcticament | ⚠️ | 102.493.057 analitzats; 24,1 M entre noms propis, no analitzables i altres |
| 7.200+ obres, 1832–2022 | ✅/⚠️ | 7.200+ obres; la prosa del lloc diu 1833–2022, però les dades inclouen 1832 |
| Manteniment baix | ❌ | El corpus creix ~5 M paraules/any; els recomptes es mouen |

---

## 2. Errors de protocol i de gramàtica

### 2.1. El rang `01-03*cg` no existeix: el golden test és un fals zero

El pla afirma:

> `00*lema=somriure & 01-03*cg=(qualsevol) & 04*forma=mala & 05*forma=fe` → **0**

La intenció és un interval de 0–3 mots entre *somriure* i *mala fe*. Però el servidor **no interpreta `01-03*cg`**: la clau no es reconeix i s'ignora. L'echo ho delata:

```text
Patró seleccionat: somriure mala fe
```

No hi ha cap `[]?`. El resultat és 0 perquè el patró real és adjacent, no perquè l'interval no tingui ocurrències. La forma correcta és expandir-lo a tres claus:

```text
seccio=CTILC1&00*lema=somriure
&01*cg=(qualsevol)&02*cg=(qualsevol)&03*cg=(qualsevol)
&04*forma=mala&05*forma=fe
```

Aquesta versió sí que mostra l'echo esperat:

```text
Patró seleccionat: somriure []? []? []? mala fe
```

i també retorna **0**. Per tant, la conclusió del pla (0 ocurrències) és correcta, però **el test no prova el que diu**. Si s'implementa literalment, qualsevol consulta amb interval donarà falsos zeros. Cal un test del compilador que verifiqui que `01-03` s'expandeix a tres claus i que l'echo conté tres `[]?`.

### 2.2. `forma` no admet frases; els 8 de `somriure mofeta` són un patró de dos elements

El pla diu:

> forma `somriure mofeta` → **8**

A `Coocur2`, un valor de `forma` amb espai es converteix en un sol token amb guió baix:

```text
00*forma=somriure mofeta   →  echo: somriure_mofeta   →  0
```

Els 8 resultats surten de dos elements:

```text
00*forma=somriure&01*forma=mofeta   →  8
```

I la cerca bàsica de forma tampoc no accepta frases:

```text
POST Formes2.asp  cadforma=somriure mofeta  →  0
```

Conclusió: `cerca_forma` ha de documentar que és **una sola forma gràfica**; per a frases cal `cerca_patro` amb un element per paraula. El golden test ha de dir exactament quin endpoint i quin cos usa.

### 2.3. `cg=adj` sol provoca HTTP 500; `adj:-` és obligatori

El pla descriu `cg` com «categoria lèxica i/o morfològica, format `cat:morf` (p. ex. `adj:-`)». Però no explica que el guionet és necessari. Proves:

```text
00*lema=somriure&01*cg=adj    → HTTP 500
00*lema=somriure&01*cg=V      → HTTP 500
00*lema=somriure&01*cg=adj:-  → 2.136
```

El formulari de Coocur construeix el valor amb `categoria` + `:` + codi morfològic, i quan no hi ha codi posa `-`. El compilador ha de fer el mateix: si l'usuari dona `cg: "adj"` sense morfologia, generar `adj:-`; si dona `cg: "qualsevol"`, generar `qualsevol`; si dona una categoria sola, no enviar-la mai tal qual.

### 2.4. `<>` i `()` no es poden combinar

El pla presenta els modificadors com a independents:

- `<>` — negació
- `()` — opcional

La UI permet marcar les dues caselles alhora, però el servidor no ho accepta:

```text
00*lema=somriure&01*forma=(<>amb)&02*forma=mala  → HTTP 500
```

En canvi, aquestes combinacions sí que funcionen:

```text
00*lema=somriure&01*forma=<>amb          → 13.727
00*lema=somriure&01*forma=<>(amb|de)     → 13.061
00*lema=somriure&01*forma=(amb|de)&02*forma=mala → 0  (echo: somriure (amb | de)? mala)
00*lema=somriure&01*cg=<>adj:-           → 12.154
```

Cal validar `negat && opcional` com a error d'entrada, o transformar-lo en una construcció equivalent si es troba una. No s'ha de deixar passar al servidor perquè el resultat és un 500 genèric.

### 2.5. `iStart` és 1-based, però `iStart=0` té un off-by-one

El pla diu que `iStart` és 1-based i l'exemple és correcte. Però el valor 0 no és equivalent:

| `iStart` | `iOffset` | Files retornades |
|---|---:|---:|
| 0 | 1000 | 999 |
| 1 | 1000 | 1000 |
| 1001 | 1000 | 1000 |
| 2001 | 1000 | 136 |

Conclusió: validar `iStart >= 1`; no acceptar 0. La paginació amb 1, 1001, 2001 és correcta i no duplica IDs d'ocurrència (comprovat: 1000 + 1000 + 136, sense intersecció). Nota: el 999 de `iStart=0` és el que vam comptar amb `class="pclau"`; tant si és un off-by-one del servidor com si és una fila mal formada, reforça la necessitat de validar i de fer servir un parser DOM.

### 2.6. `lema@CG` sí; `lema:CG` no; `formalema` té una altra gramàtica

El pla encerta amb `lema@CG`:

```text
00*lema=somriure@V                    → 8.606   (echo: somriure V)
00*lema=somriure@subst&01*cg=adj:-    → 1.829
```

Però `lema:CG` no funciona:

```text
00*lema=somriure:V   → 0
```

`formalema` és un cas a part. La UI genera:

```text
lema:cg¬forma1:cg|forma2:cg
```

Per exemple:

```text
00*formalema=somriure:V¬somriure:IF|somreia:3II   → 3.489
```

que vol dir: del lema *somriure* amb categoria `V`, només les formes *somriure* (infinitiu) i *somreia* (imperfet 3a singular). El pla diu «separador intern `¬`», però no documenta el `:` de la categoria, el `|` entre formes ni el fet que cada forma porta el seu propi codi morfològic. Cal documentar-ho o, millor, no exposar `formalema` cru: oferir una eina `formes_de_lema` que construeixi el valor.

### 2.7. Categories i codis morfològics: la llista del pla és incompleta

La llista del pla és plana i barreja nivells:

```text
adj, subst, verb, NP, AV, AR, C, CT, DEM, IND, IFX, I, L, LA,
NC, NUM, POS, PFX, PO, P, QUA, REL, SIG, SFX
```

La UI real té, a més, les subcategories:

```text
A, AF, AI, AII, AM, AMP
F, FP, FS, M, MF, MFP, MP, MS
V, VA
```

I `NP` no és una opció fixa: s'insereix dinàmicament per al tipus «nom propi». No és equivalent a `cg=NP` en tots els contextos.

Els codis morfològics també són més rics:

```text
IF, GE, RMS, RFS, RMP, RFP
1PI–6PI, 1II–6II, 1PT–6PT, 1FU–6FU,
1PS–6PS, 1IS–6IS, 1CO–6CO,
2IM–6IM
MS, FS, MP, FP, M, F, S, P,
D, DS, DP, DMS, DFS, DMP, DFP, DM
```

El pla omet tota la sèrie `1II–6II`, els imperatius `2IM–6IM` i la major part dels apreciatius. A més, el formulari bàsic fa servir valors amb guions (`-IF-`, `-MS-`) mentre que Coocur fa servir els codis sense guions (`IF`, `MS`). Són dues gramàtiques diferents; no s'han de confondre.

Recomanació: generar el tagset **des del formulari** (o des d'un recurs estàtic versionat) i exposar-lo com a recurs `ctilc://tagset`, amb etiquetes llegibles. No hard-codejar la llista del pla.

### 2.8. El canal `strquery` és CQL, però no és una API general

El pla diu:

> **Límit de nivell CQP:** cap endpoint accepta CQL cru (sonda via `strquery` → patró buit).

Això és massa absolut. La pàgina de resultats conté un camp ocult `strquery` amb CQL compilat:

```text
[lemma%3D%22somriure(_.)?( .*)?%22 %26 !tag%3D%22NP00000%22]
[tag%3D%22A:.*|AF:.*|AI:.*|AII:.*|AM:.*|AMP:.*%22]
```

I aquest camp **s'executa**. Si li canviem el filtre de tags, el recompte canvia:

```text
original (tags A/AF/AI/AII/AM/AMP)  → 2.136
només [tag="A:.*"]                  → 1.591
```

Per tant, hi ha un canal CQL intern. Ara bé:

- No és una API pública ni documentada.
- El CQL simplificat que vam provar (`[lemma="somriure"]`, amb un `strqueryTXT` genèric) retornava 0; el servidor sembla esperar el format compilat i pre-codificat.
- Els rangs `[]{0,3}` i `[]{2,5}` retornen 0; no hi ha suport pràctic de rangs.
- `strqueryTXT` és necessari per a la visualització, i el servidor pot validar-lo.
- Tampoc no hem pogut confirmar que el motor sigui IMS Corpus Workbench; el que és segur és que accepta un subconjunt de sintaxi CQL. No dependre d'operacions CQP avançades.

Conclusió: el pla encerta a dir que **no s'ha de dependre de CQL cru** i que els rangs s'han d'emular, però l'afirmació «cap endpoint accepta CQL» és falsa. Cal decidir explícitament si s'exposa un `raw_cql` experimental (no recomanat per a la MVP) o si s'amaga completament. Si s'exposa, ha de tenir validació, límits de longitud i advertències.

### 2.9. Un altre fals zero: el test de l'interval no és l'únic

El principi «contrastar sempre l'echo» s'aplica a tots els golden tests. Qualsevol consulta amb una clau desconeguda pot retornar 0 i semblar una absència real. Propostes:

- Sempre retornar `pattern_echo` i `internal_cql` (si es pot) al costat del total.
- Si l'echo no conté el nombre esperat d'elements, marcar `warning: patro_inesperat` i no presentar el 0 com a resultat lingüístic.
- Comparar el nombre d'elements de l'echo amb el nombre d'elements enviats; si no coincideixen, error de compilació.

### 2.10. Detalls menors però rellevants

- «Sense JSON (llevat d'un endpoint CSV)»: un CSV no és JSON. A més, les pàgines contenen arrays JavaScript (`chartData`, `dataArray`) que són dades estructurades; no hi ha una API JSON, però sí dades serialitzades.
- «Tota la lògica de consultes és al client»: el client construeix la petició, però el servidor compila el `strquery`, executa la consulta i cacheja el resultat. És una simplificació excessiva.
- «Motor IMS Corpus Workbench»: és plausible per la sintaxi, però no ho hem pogut confirmar; els rangs CQP no funcionen. No dependre d'operacions avançades de CWB.
- «Etiquetes EAGLES/Parole»: EAGLES i PAROLE són estàndards relacionats però no idèntics. El tag `NP00000` és d'estil EAGLES; cal citar la font del tagset i no barrejar noms.
- «Cap protecció anti-bot detectada»: no hem vist captcha, però això no prova que no hi hagi límits. El servidor pot tancar connexions o retornar 500 sota càrrega; cal assumir que hi és.
- «~14 files per pàgina de 500»: 2.136 − 2.087 = 49; amb 3 pàgines de 1.000 són ~16 per pàgina, no 14. La conclusió (cal un parser tolerant) és correcta, però el número no.

---

## 3. Errors de disseny de l'MCP

### 3.1. `resultat_id` no és un cursor suficient

El pla proposa:

```text
ocurrencies(resultat_id, i_start, i_offset=1000)
```

Però `resultat` sol no n'és prou. Proves:

- `resultat` + `iStart`/`iOffset`, sense `Qlocali` → pàgina sense files (10.841 bytes, 0 `pclau`).
- `resultat` + `Qlocali` + `iStart`/`iOffset` → 1.000 files, però **`Patró seleccionat` buit**.
- `resultat` + `Qlocali` sense cookies → també funciona (el cache sembla global, no lligat a la sessió).

És a dir: el resultat es pot recuperar, però el patró es perd i el resultat depèn d'un cache del servidor que pot expirar. Un MCP no hauria de dependre d'un estat invisible del servidor per a una operació tan bàsica com paginar.

**Proposta:** `ocurrencies(cursor, start?, offset?)` on el cursor conté:

```json
{
  "v": 1,
  "query": {
    "elements": [
      {"type": "lema", "value": "somriure"},
      {"type": "cg", "category": "adj", "morphology": "-"}
    ],
    "filters": {},
    "sort": {"position": 99, "element": "token", "direction": "asc"}
  },
  "pattern_echo": "somriure adj:-",
  "total": 2136,
  "resultat": "179500525152020580",
  "qlocali": "2136",
  "next_start": 1001,
  "created_at": "2026-11-18T13:21:31Z"
}
```

La font de veritat és `query`: es recompila i es re-POSTeja amb `iStart`/`iOffset`. `resultat`/`qlocali` són només una pista de cache. Així la paginació és stateless i no depèn de la precisió de l'ID ni de la vida del cache.

### 3.2. L'ID de 64 bits no cap en un `number` de JavaScript

El pla dona com a exemple `179499746019557630`, un enter de 18 dígits. No tots aquests enters són representables en doble precisió. Exemple real:

```text
ID original:  179500525152020580
ID en float:  179500525152020576
```

Si un client JavaScript/JSON fa `Number(id)` o `JSON.parse` sense cuidado, l'ID es converteix en `...576`. El servidor retorna:

```text
resultat=179500525152020576&Qlocali=2136  →  total 2136, 0 files
```

És a dir: **el total sembla correcte, però no hi ha resultats**. És un error silenciós i perillós.

**Proposta:** `resultat` i `qlocali` han de ser `string` a l'esquema Pydantic, al JSON i al cursor. Mai `int`, mai `Number`. Afegir un test que serialitzi/deserialitzi el cursor i comprovi que l'ID no canvia. Si s'implementa en TypeScript, fer servir `BigInt` o `string`, i assegurar que el transport MCP no el converteixi.

### 3.3. `requests`/`httpx` envien `00%2Alema` i el servidor respon 500

Aquest és el parany d'implementació més important. Si es fa:

```python
requests.post(url, data={"00*lema": "somriure", "01*cg": "adj:-"})
```

`requests` codifica el `*` com `%2A`:

```text
seccio=CTILC1&00%2Alema=somriure&01%2Acg=adj%3A-...
```

I el servidor retorna **HTTP 500**. Amb el cos manual i `*` literal:

```text
seccio=CTILC1&00*lema=somriure&01*cg=adj%3A-...
```

retorna 200 i 2.136. `httpx` fa el mateix amb `data={...}`.

**Proposta:** construir el cos a mà:

```python
from urllib.parse import quote


def camp(i: int, clau: str, valor: str) -> str:
    return f"{i:02d}*{clau}={quote(valor, safe='')}"


body = "&".join(
    [
        "seccio=CTILC1",
        camp(0, "lema", "somriure"),
        camp(1, "cg", "adj:-"),
        "iStart=1",
        "iOffset=50",
    ]
)
```

`quote` ha de codificar `|`, `<>`, `()`, `:`, `@` i `¬`; el `*` de la clau ha de quedar literal. Cal un test que inspeccioni el cos HTTP i comprovi que conté `00*lema=` i no `00%2Alema=`.

### 3.4. `collocacions` apunta a l'endpoint equivocat

El pla diu:

> `collocacions` | `paraula`, `tipus: lema|forma`, `distancia 1-5` | `QCol_*Agrup1.asp`

Però `QCol_LemesAgrup1.asp` i `QCol_FormesAgrup1.asp` són els **formularis**. Els resultats es POSTen a:

```text
CTILCQCol_LemesAgrup2.asp
CTILCQCol_FormesAgrup2.asp
```

A més, `distancia 1-5` no existeix com a paràmetre únic. El formulari té:

- `radiE` (0–5) — radi a l'esquerra
- `radiD` (0–5) — radi a la dreta
- `freqMin` (per defecte 5) — freqüència mínima de coaparició

I el resultat no és una llista plana: està agrupat per categoria gramatical (`verb`, `nom`, `adjectiu`, `adverbi`, `preposició`, `conjunció`, `article`, `contracció`, `demostratiu`, `pronom`, `indefinit`, `possessiu`, `quantitatiu`, `relatiu`, `numeral`, `interjecció`, `locució`, `ALTRES`), amb `lema` i `freqüència de coaparició`.

Per a *somriure* amb radis 3/3 i `freqMin=5`, la pàgina diu **1.159 col·locacions**. Algunes xifres útils:

```text
burleta   61
irònic    70
maliciós  52
sorneguer 40
mofeta    17
```

Aquestes xifres són **finestres de ±3**, no adjacència immediata; per això difereixen de les de l'apèndix (39/40, 39, 31/32, 26, 8). Cal no barrejar-les.

### 3.5. `fitxa_obra` barreja ocurrència i obra; `obra` no és l'ID de l'obra

El pla diu:

> `fitxa_obra` | `id`, `obra` | `FitxaLocalitzacio.asp?id=…&tok=no&seccio=CTILC1&obra=N`

`CTILCQFitxaLocalitzacio.asp` no és una fitxa de l'obra: és una **fitxa de localització** d'una ocurrència. Retorna:

- Títol, autor, varietat, any d'edició, tipus, classificació.
- Ocurrències, lemes i formes de l'obra.
- Lema, categoria gramatical, forma, codi morfològic i posició dins l'obra de l'ocurrència.
- Context de ±50 posicions i el paràgraf complet.

I el paràmetre `obra` de la URL **no és l'ID canònic**:

```text
id=558397&obra=6       →  Id. obra: 8
id=82148513&obra=4542  →  Id. obra: 4534
```

Sembla un índex dins del conjunt de resultats, no un identificador estable. Si es guarda `obra` com a ID de l'obra, es pot apuntar a una obra diferent en una altra consulta.

**Proposta:** separar les eines:

- `fitxa_localitzacio(occurrence_id, obra?)` → metadades de l'obra + context ±50 + paràgraf + ID canònic `Id. obra`.
- `obres(autor?, titol?, parametres?)` → llista d'obres (metadades).
- `obres_descarregables()` → `CTILCCorpus_Descarr.asp`.

### 3.6. `exportar_csv` no està verificat i, a les proves, falla

El pla diu:

> `exportar_csv` | `resultat_id` | `Qjson_concordancesCSV.asp`

La pàgina de resultats té un formulari `fCSV` amb `cCSV1`, `seccioC`, `resultatC`, `iStartC`, `iStopC`, `iOffsetC`, `filtresC`, `contextConcC`, `ordreposNC`, etc. El JavaScript fa:

```js
document.getElementById("cCSV1").value = document.getElementById("cHTML1").innerHTML;
```

Però `cHTML1` és la **capçalera** (botons, títol, patró, total), no la taula de files; les files són a `cHTML2`. A més, les nostres proves amb totes les variants (inner/outer de `cHTML1`, inner de `cHTML2`, sense `cCSV1`, amb `Referer`/`Origin`) van retornar **HTTP 500**.

No afirmo que l'endpoint estigui trencat; potser cal una captura exacta del navegador, una sessió concreta o un `cCSV1` amb un format molt específic. Però **no es pot posar a la fase 2 com si estigués verificat**. Propostes:

- Capturar una exportació real amb les eines de desenvolupador del navegador (request + response) i afegir-la com a fixture.
- Si no es pot reproduir, eliminar la tool de la MVP i oferir només `exportar_json`/`exportar_markdown` generat pel propi MCP a partir de les ocurrències.
- Si es reimplementa: recórrer les pàgines amb `iStartC`/`iStopC`, generar el CSV al MCP, sanititzar la injecció de fórmules (`=`, `+`, `-`, `@`) i documentar la codificació (UTF-8 amb BOM).

### 3.7. `cerca_forma` i `cerca_lema` tenen un altre parser

El pla posa `cerca_forma` i `cerca_lema` a la mateixa taula que `cerca_patro`, però les pàgines bàsiques no tenen `Patró seleccionat`:

- `Formes2.asp` mostra `Forma: Coincident amb ...` / `Començada per ...` i `Freqüència total`.
- `FormesLema2.asp` mostra `Lemes: ...` i `Freqüència total`.
- Les files segueixen tenint `td align='right'`, `td align='center'` amb `class="pclau"`, `td align='left'`.

Cal un parser específic per a les cerques bàsiques o un parser comú que miri el contenidor de resultats, no el text «Patró seleccionat». A més, `cadformacond` té 7 modes:

```text
0 Coincident
1 Començada per
2 Acabada en
3 En qualsevol posició
4 No començada per
5 No acabada en
6 Que no contingui
```

Prova amb `cadforma=somriu`:

```text
mode 0 → 2.019
mode 1 → 10.628
mode 2 → 2.019
mode 3 → 10.630
mode 4 → 0
mode 5 → 0
mode 6 → 0
```

**Verificació del 21/11/2026 ([#6](https://github.com/papersvells/llengua-mcp/issues/6)).**
Els formularis `CTILCQConc_Formes1.asp` i `CTILCQConc_FormesLema1.asp`
envien els modes 4–6 al mateix camp que els positius, sense cap paràmetre
addicional de negació. Els controls es van fer amb aquests cossos POST
(`N` és cadascun dels valors 1–6):

```text
CTILCQConc_Formes2.asp      cadforma=ah&cadformacond=N&cg=I&seccio=CTILC1&iStart=1&iOffset=2
CTILCQConc_FormesLema2.asp  cadlema=ah&cadlemacond=N&cg=I&seccio=CTILC1&iStart=1&iOffset=2
```

| Modes (positiu / negatiu) | Forma | Lema |
|---|---:|---:|
| 1 / 4 (comença per) | 11.334 / 83.380 | 11.437 / 83.277 |
| 2 / 5 (acaba en) | 12.147 / 82.567 | 12.146 / 82.568 |
| 3 / 6 (conté) | 12.277 / 82.437 | 12.243 / 82.471 |

Cada parella suma 94.714 dins de `cg=I`. Les concordances negatives mostren
«Hola» i «Apa», i cap element del panell negatiu compleix el criteri positiu
respectiu (es compara la forma a `Formes2` i el lema a `FormesLema2`, sense
distinció de caixa ni d'accents). L'eco visible i els camps ocults coincideixen.
Repetint el mode 4 amb `somriu` i `cg=` als dos endpoints s'obté un fals zero
amb el missatge de cap coincidència i l'eco correcte. Per això l'MCP només
envia modes negatius amb `cg` i comprova l'eco del terme, el mode i el filtre.
El desglossament no es pagina: amb `iOffset=2`, la resposta negativa per lema
ja pesa uns 2,6 MB.

### 3.8. Falten eines bàsiques

La taula de tools del pla no cobreix:

- `cerca_nom_propi` (`CTILCQConc_NomsPropis2.asp`), que és una cerca bàsica independent i molt senzilla.
- `formes_de_lema` (llistar les formes d'un lema; la UI ho fa amb `tipusel=formeslema` i `strquery`, i és la manera natural de construir `formalema`).
- `context_ocurrencia`/`fitxa_localitzacio` (context ±50 i paràgraf; ara barrejat amb `fitxa_obra`).
- `obres_descarregables` (`CTILCCorpus_Descarr.asp`).
- `etiquetes`/`tagset` (categories i codis morfològics, amb etiquetes llegibles).
- `salut`/`protocol` (comprovar que el lloc respon, que l'echo és correcte i que les URLs no han canviat).
- `filtres_disponibles` (autors, títols, anys, gèneres, varietats; el formulari els carrega amb `CTILCQConcFiltObra_filtres.asp`).

### 3.9. L'esquema de `cerca_patro` no expressa la gramàtica

`{tipus, valor, opcional?, negat?, multi?}` no pot expressar:

- `lema@CG` (lema + categoria).
- `formalema` amb `lema:cg¬forma:cg|...`.
- `cg` amb categoria + morfologia (`V:3II`, `adj:-`).
- `qualsevol` com a element especial.
- Un rang d'opcionals (cal expandir-lo).
- La diferència entre `multi` com a alternança i `multi` com a llista de valors.

**Proposta:** unió discriminada:

```json
{
  "elements": [
    {"type": "lema", "value": "somriure", "cg": "V"},
    {"type": "forma", "value": "mala"},
    {"type": "formalema", "lema": "somriure", "cg": "V",
     "forms": [{"form": "somriure", "cg": "IF"}, {"form": "somreia", "cg": "3II"}]},
    {"type": "cg", "category": "adj", "morphology": "-"},
    {"type": "qualsevol", "optional": true}
  ]
}
```

Regles de validació:

- `negated && optional` → error (el servidor retorna 500).
- `type=forma` amb espais → error amb suggeriment d'usar diversos elements.
- `type=cg` amb `category` però sense `morphology` → generar `category:-`.
- `type=lema` amb `@` ja inclòs → no duplicar.
- Màxim de posicions (per exemple, 10) i de cadena opcional (per exemple, 5) per evitar consultes massa cares.
- `multi` com a `array[string]`; si un valor conté `|`, rebutjar o escapolir (el lloc no té escape).

---

## 4. Robustesa HTTP i parsing

### 4.1. Capçaleres mal formades i EOF de TLS

Algunes respostes grans tenen:

```text
Content-Type: text/html;; Charset=UTF-8
```

(atenció al `;;` i al `Charset` en majúscules), i algunes tanquen la connexió abruptament. `curl` reporta:

```text
curl: (56) OpenSSL SSL_read: ... unexpected eof while reading
```

tot i que el cos contingui la pàgina completa (acaba amb `</html>`). `requests`/`httpx` poden llançar `ChunkedEncodingError`/`RemoteProtocolError` i fer perdre una resposta bona.

**Propostes:**

- Fixar `response.encoding = "utf-8"` explícitament; no confiar en la capçalera.
- Llegir el cos fins a EOF i comprovar que acaba amb `</html>` o que conté els marcadors esperats; si el transport dona error però el cos és complet, acceptar-lo amb `warning: transport_eof`.
- Fer servir un client que toleri EOF (o `curl`/`urllib3` amb lectura manual) si `httpx` no ho permet.
- Timeouts de 30–60 s; reintents només per a errors de connexió, no per a HTTP 500 de consultes invàlides.
- No reintentar POST a cegues: cada reintent pot crear una entrada de cache al servidor i carregar-lo.

### 4.2. Codificació UTF-8

Les pàgines són UTF-8, però la capçalera mal formada pot fer que un client faci servir ISO-8859-1 i trenqui accents, `·`, `ï`, `ç`, etc. Cal:

- `response.encoding = "utf-8"` sempre.
- Normalitzar a NFC.
- No fer `lower()` cec sobre tot el text si es volen preservar les majúscules de l'obra; normalitzar només per a comparacions.
- Decodificar entitats HTML (`&nbsp;`, `&#8203;`) amb `html.unescape`.

### 4.3. Parsing: DOM, no regex; espais d'amplada zero

El regex tolerant del pla és un bon primer pas, però no és suficient:

- `class="pclau"` pot canviar d'ordre d'atributs o de cometes.
- Els nuclis poden contenir `<i>`, `<span>`, `&nbsp;` i **espais d'amplada zero** (`&#8203;`), com a `<>(amb | de)` i `formalema`.
- Les files són en una sola línia HTML; un regex de tres `<td>` pot fallar amb files mal formades.
- La taula de resultats és a `div#cHTML2`, no a `cHTML1`.

**Propostes:**

- Fer servir `selectolax` o `lxml`/`BeautifulSoup` amb selectors:
  - `div#cHTML1` → capçalera, patró, total.
  - `div#cHTML2` → files; `a.pclau` → nucli; `td[align=right]` / `td[align=center]` / `td[align=left]` → contextes.
  - `div#cHTML3` → paginació, filtres, ordenació.
- Netejar: `html.unescape`, treure `<...>`, substituir `\xa0`, eliminar `\u200b`, col·lapsar espais.
- Conservar la puntuació i els accents; no aplicar `strip()` agressiu que trenqui el context.
- Test de fixtures amb una fila mal formada, una fila amb `<i>`, una amb `&#8203;` i una pàgina de 0 resultats.

### 4.4. Mida de les respostes i límits de sortida

Una pàgina de 1.000 files pot pesar ~1 MB de HTML. Retornar-la sencera a un LLM és inviable i car.

**Propostes:**

- Per defecte, 50 files (el `iOffset` per defecte del lloc).
- Màxim configurable 100–200; si l'usuari demana 1.000, retornar un `warning` i truncar, o retornar un cursor per continuar.
- Retornar sempre `total`, `returned`, `has_more` i `next_start`.
- No incloure l'HTML cru a la sortida; només text estructurat.
- Limitar la longitud de cada context (per exemple, 300 caràcters) i oferir `context_50`/`paràgraf` com a tool a part.

### 4.5. Errors 500 genèrics

El servidor retorna una pàgina ASP genèrica de 250 bytes o 4 KB, sense detall. No es pot distingir entre:

- Consulta invàlida (per exemple, `cg=adj`).
- Massa resultats o timeout.
- Error intern.
- Sessió/cache expirat.

**Propostes:**

- Capturar `status`, URL, cos i hash; classificar l'error.
- No reintentar 500 de consultes que ja s'han validat; tornar un error estructurat amb `hint`.
- Un `health`/`protocol` que provi una consulta coneguda (2.136) i detecti canvis.

### 4.6. Sessió, cookies i cache global

El lloc assigna `ASPSESSIONID...` i el `resultat` sembla global (hem pogut recuperar un resultat sense cookies). Això té implicacions:

- No tractar `resultat` com un secret; els IDs són grans però poden ser enumerables.
- No posar consultes sensibles al corpus; el resultat pot quedar cachejat al servidor.
- Usar una `Session` per mantenir cookies, però no dependre'n per a la lògica.
- No compartir IDs entre usuaris com si fossin autenticació.

---

## 5. Problemes metodològics de l'apèndix

### 5.1. Nom vs verb: els 2.136 no són tots «somriure» nominal

`00*lema=somriure&01*cg=adj:-` retorna 2.136, però el lema `somriure` pot ser nom o verb. Si es restringeix la categoria:

```text
lema=somriure@subst + adj:-  → 1.829
lema=somriure@V     + adj:-  →   307
lema=somriure       + adj:-  → 2.136
```

És a dir, **307 ocurrències són verb + adjectiu** (per exemple, *somreia afalagada*), no nom + adjectiu. Si l'objectiu és estudiar *el somriure burleta*, cal `@subst` (o `@M`), no el lema sense categoria. Els recomptes de l'apèndix (40, 39, 31, 26, 8) semblen propers al subconjunt nominal, però el pla no ho diu; el 2.136 i aquests recomptes no són la mateixa consulta.

### 5.2. Adjacència vs finestra de col·locació: les xifres no coincideixen

L'apèndix diu:

> *somriure burleta* (40), *irònic* (39), *maliciós* (31), *sorneguer* (26), *fals* (8), *mofeta* (8)

Els de l'apèndix són recomptes d'**adjacència** (patró `somriure + adjectiu`) i, pel que sembla, del subconjunt nominal. La tool de col·locacions, amb radis ±3 i tot el lema, dona:

```text
burleta   61
irònic    70
maliciós  52
sorneguer 40
mofeta    17
```

No són contradictoris: són mètriques diferents. El problema és que el pla les barreja i no defineix quina mesura fa servir. Per a afirmacions sobre col·locació, la finestra ±3 és més adequada; per a afirmacions sobre seqüències fixes, l'adjacència ho és. Cal explicitar-ho a cada número.

### 5.3. `mala fé` no és un control neutre

`00*forma=mala&01*forma=fe` → 294; `00*forma=mala&01*forma=fé` → 29. Però la forma normativa és **mala fe** (sense accent). Els 29 de `fé` són una grafia no estàndard (o un error/arcaisme), no una variant equivalent. Si es fan servir com a control, cal explicar-ho; si no, no aporten res a la comparació.

### 5.4. Els controls externs no són comparables

L'apèndix diu:

- 0 a ARCA, control «de mala fe» → 4.657.
- 0 a Gallica, control → 132–173.
- 0 al web català.

Problemes:

- ARCA i Gallica tenen corpus, OCR i interfícies diferents; el control «de mala fe» no és el mateix tipus de construcció que «somriure de mala fe».
- El rang 132–173 de Gallica indica inestabilitat; no és una xifra precisa.
- «0 al web català» no és un corpus; els cercadors no indexen tot el web i no permeten concloure absència.
- L'absència en un corpus escrit no implica agramaticalitat; pot ser una construcció oral, dialectal, de registre informal o simplement no recollida.
- El CTILC és un corpus escrit, literari/no literari, amb biaixos de gènere, època i varietat.
- A més, 4 ocurrències de *sourire de mauvaise foi* a Gallica són una base molt petita per concloure que és una expressió francesa establerta; poden ser traduccions o casualitats.

Conclusió: la comparació pot ser suggestiva, però no demostra que el català no ho expressi així. Cal reformular-ho com a hipòtesi i, si es vol provar, fer un estudi amb collocacions, períodes i gèneres.

### 5.5. Recompte cru no és significació

40 ocurrències de *burleta* no proven que sigui una col·locació estable; cal comparar amb l'esperat (freqüència de *burleta* × freqüència de *somriure* / mida del corpus) i calcular una mesura com log-likelihood, MI o t-score. La tool de col·locacions del CTILC dona la freqüència de coaparició, però no la significació; el MCP podria calcular-la o, com a mínim, retornar els totals necessaris per fer-ho.

### 5.6. La conclusió «el català ho expressa adjectivalment» és una hipòtesi

És plausible: *somriure burleta*, *irònic*, *maliciós*, *sorneguer* són construccions ben documentades. Però les dades que presenta el pla no proven que siguin l'única manera ni que la construcció preposicional sigui impossible. Cal separar:

- **Observació:** no s'han trobat ocurrències de la seqüència buscada al CTILC.
- **Hipòtesi:** el català prefereix l'adjectiu.
- **Test:** comparar amb collocacions, corpus orals, premsa, etc.

---

## 6. Propostes concretes

### 6.1. Model de dades i cursor

- `QuerySpec` (Pydantic) amb elements tipats, filtres, ordenació i límits.
- `Cursor` opac (base64 JSON) amb `v`, `query`, `pattern_echo`, `total`, `resultat` (string), `qlocali` (string), `next_start`, `created_at`.
- `Occurrence` amb `left`, `nucleus`, `nucleus_tokens`, `right`, `occurrence_id`, `work` (id canònic, títol, autor, any, varietat).
- `SearchResult` amb `query`, `pattern_echo`, `internal_cql?`, `total`, `returned`, `has_more`, `occurrences`, `warnings`, `source`, `retrieved_at`, `citation`.

### 6.2. Compilador de patrons

- `type=lema`: `lema` o `lema@CG`.
- `type=forma`: una sola forma; si conté espais, error.
- `type=formalema`: `lema:cg¬forma:cg|forma:cg`.
- `type=cg`: `categoria:morfologia`; si falta morfologia, `-`; `qualsevol` és un tipus a part.
- `multi`: `a|b`; `negat`: `<>`; `opcional`: `(...)`.
- `negat && opcional`: error.
- Rang: `01-03` s'expandeix a `01`, `02`, `03`; mai enviar la clau `01-03`.
- Codificació: `quote(value, safe='')`; `*` literal a la clau.
- Test: per a cada element, comprovar que el cos HTTP conté la clau esperada i que l'echo conté el nombre d'elements esperat.

### 6.3. Client HTTP

- `httpx.AsyncClient` (no `requests` síncron dins d'una tool async) amb `follow_redirects=True`, `timeout=30`, `headers`:
  - `User-Agent`: `ctilc-mcp/0.1 (+contacte; recerca)`
  - `Accept-Language: ca`
  - `Content-Type: application/x-www-form-urlencoded` quan calgui.
- Cookies amb `AsyncClient`; no dependre'n.
- Rate limit global: 1 req/s (o 0,5 req/s) amb jitter; cua; no paral·lelisme.
- Reintents: 2 amb backoff exponencial per a errors de connexió/EOF; no per a 500 de consulta.
- Cache: LRU en memòria + SQLite opcional; clau = hash de `QuerySpec` + pàgina + filtres + ordenació + versió de protocol; TTL 1 h per a cerques, 24 h per a bibliografia; no cachejar errors.
- `resultat`/`qlocali` com a `str`.

### 6.4. Parsers

- Coocur: `div#cHTML1` (patró, total), `div#cHTML2` (files), `div#cHTML3` (paginació/filtres).
- Bàsic: `Forma`/`Lema` + `Freqüència total`; mateix `cHTML2`.
- Col·locacions: `div#cHTML2`, seccions per POS, `a.lnkU` + freqüència; `#freq` per al total.
- Dispersions: `var chartData = [...]`; parsejar amb un parser de literals JS (no `json.loads`; hi ha cometes simples, comes finals i, en alguns arrays, expressions com `llistacolorsAny['...']`). `json5` pot ajudar en els arrays simples, però no és suficient per a tots; retornar `{label, query_count, corpus_count, rate}`.
- DadesNum: `arrayToDataTable([...])`; retornar totals i desagregacions.
- Fitxa: metadades + `Id. obra` + context ±50 + paràgraf.
- Sempre: `html.unescape`, treure tags, `\u200b`, `\xa0`, col·lapsar espais.

### 6.5. Tools revisades

| Tool | Entrada | Endpoint | Notes |
|---|---|---|---|
| `cerca_patro` | `QuerySpec` | `Coocur2.asp` | Retorna cursor, echo, total, files |
| `ocurrencies` | `cursor`, `start?`, `limit?` | re-POST `Coocur2.asp` | No depèn només de `resultat` |
| `cerca_forma` | `forma`, `mode`, `cg?` | `Formes2.asp` | Modes 0–3; 4–6 amb `cg` |
| `cerca_lema` | `lema`, `mode`, `cg?` | `FormesLema2.asp` | Retorna ocurrències; per a formes, `formes_de_lema` |
| `cerca_nom_propi` | `forma`, `mode` | `NomsPropis2.asp` | Afegir |
| `formes_de_lema` | `lema`, `cg?` | `Coocur1b`/`strquery` | Per construir `formalema` |
| `collocacions` | `lema/forma`, `radiE`, `radiD`, `freqMin` | `QCol_*Agrup2.asp` | Agrupat per POS |
| `dispersions` | `cursor`, `eix` | `QDispersions*.asp` | Parsejar `chartData` |
| `fitxa_localitzacio` | `occurrence_id`, `obra?` | `FitxaLocalitzacio.asp` | Context ±50 + metadades |
| `obres` | `autor?`, `titol?`, `parametres?` | `Aut1`/`Obr2`/`ObrParam` | Multi-pas; retornar metadades |
| `obres_descarregables` | — | `Descarr.asp` | Afegir |
| `corpus_xifres` | — | `DadesNum.asp` | Retornar totals i cobertura |
| `filtres_disponibles` | `tipus` | `FiltObra_filtres.asp` | Valors per als filtres |
| `etiquetes` | — | recurs estàtic | Categories i morfologia |
| `salut`/`protocol` | — | `Coocur2.asp` | Consulta de control 2.136 |
| `exportar_csv` | `cursor` | `Qjson_concordancesCSV.asp` | Només si es verifica |

### 6.6. Esquema de sortida

```json
{
  "query": { "elements": ["..."], "filters": {}, "sort": {} },
  "pattern_echo": "somriure adj:-",
  "total": 2136,
  "returned": 50,
  "has_more": true,
  "occurrences": [
    {
      "left": "…",
      "nucleus": "somreia afalagada",
      "nucleus_tokens": ["somreia", "afalagada"],
      "right": "…",
      "occurrence_id": "558397",
      "work": {
        "id": "8",
        "title": "Narracions del Delta",
        "author": "Juan Arbó, Sebastià",
        "year": 1965,
        "variety": "nord-occidental"
      }
    }
  ],
  "warnings": [],
  "source": "https://ctilc.iec.cat/scripts/CTILCQConc_Coocur2.asp",
  "retrieved_at": "2026-11-18T13:21:31Z",
  "citation": "CTILC (IEC), consulta feta el 18/11/2026: …"
}
```

### 6.7. Filtres

No exposar el camp `filtres` com a blob. Oferir:

```json
{
  "autor": ["Arbó, Sebastià"],
  "titol": ["Narracions del Delta"],
  "any": {"min": 1960, "max": 1970},
  "tipus": ["LIT"],
  "genere": ["N"],
  "classtem": ["..."],
  "traduccio": false,
  "varietat": ["nord-occidental"]
}
```

i una tool `filtres_disponibles` que llegeixi `CTILCQConcFiltObra_filtres.asp` per a cada tipus. El formulari real fa servir valors amb `@` (`@LIT@`, `@N@`, etc.); el MCP els ha de generar i validar.

### 6.8. Dispersions

- `CTILCQDispersions.asp` (tot), `Cron.asp` (cronològic), `Dial.asp` (dialectal).
- GET funciona; POST també.
- Parsejar `chartData`; hi ha diverses gràfiques a la mateixa pàgina:
  - distribució del corpus;
  - distribució de la consulta;
  - proporció respecte del corpus.
- Retornar `{groups: [{label, query_count, corpus_count, rate}], totals: {query: 2136, corpus: 126604218}}`.
- No confondre la distribució del corpus amb la de la consulta.

### 6.9. Cache, rate limit i logging

- Rate limit global, no per tool; 1 req/s; jitter.
- Cache de resultats i de metadades; TTL; clau completa.
- Logging estructurat: `tool`, `query_hash`, `status`, `latency`, `bytes`, `resultat` (com a string), `warnings`; no loguejar textos sencers.
- Mètriques: errors per tipus, latència, taxa de cache hit, drift de protocol.

### 6.10. Tests

- **Unitaris:** compilador, encoder (`*` literal), parser de files, cursor, IDs com a string.
- **Fixtures:** 50 files, 1.000 files, 0 files, fila mal formada, `<i>`, `&#8203;`, `<>`, `()`, `formalema`, `Forma`, col·locació, dispersió, fitxa.
- **Contracte:** VCR/cassettes; no xarxa a CI.
- **Live:** opcional (`CTILC_LIVE=1`), 1 req/s, amb data; golden tests amb tolerància o re-baseline.
- **Drift:** `salut` comprova que `00*lema=somriure&01*cg=adj:-` retorna un total > 0 i que l'echo és `somriure adj:-`; si canvia, alerta.
- **Propietats:** `cursor` round-trip; cap ID perd precisió; `negat+opcional` rebutjat; `01-03` expandit.

### 6.11. Desplegament i documentació

- Python 3.11+, `mcp` SDK/FastMCP, `httpx`, `selectolax`/`lxml`, `pydantic`, `platformdirs`.
- `pyproject.toml`; `uvx`/`pipx`; transport stdio per defecte; HTTP opcional.
- README: instal·lació, configuració, exemples, límits, citació, avís legal, troubleshooting.
- `LICENSE` per al codi; `NOTICE` per al corpus.
- Variables: `CTILC_USER_AGENT`, `CTILC_CONTACT`, `CTILC_RATE`, `CTILC_CACHE_DIR`, `CTILC_LIVE`.
- Versió de protocol i changelog.

---

## 7. Golden tests corregits

Tots amb `seccio=CTILC1` al davant. Els cossos són en forma llegible: els valors (`|`, `<>`, `()`, `:`, `@`, `¬`, accents) s'han de URL-encodar en enviar-los, però el `*` de la clau ha de quedar **literal**. Recomptes del **18/11/2026**; el corpus creix, així que cal registrar la data i el total del corpus (126.604.218) amb cada execució.

```text
# G1 — baseline
00*lema=somriure&01*cg=adj:-
# total 2136; echo: somriure adj:-; 307 verb + 1829 nom

# G2 — només nom
00*lema=somriure@subst&01*cg=adj:-
# total 1829

# G3 — només verb
00*lema=somriure@V&01*cg=adj:-
# total 307

# G4 — adjacent amb alternança
00*lema=somriure&01*forma=amb|de&02*forma=mala&03*forma=fe
# total 0; echo: somriure (amb | de) mala fe

# G5 — interval 0-3 correcte
00*lema=somriure&01*cg=(qualsevol)&02*cg=(qualsevol)&03*cg=(qualsevol)&04*forma=mala&05*forma=fe
# total 0; echo: somriure []? []? []? mala fe

# G6 — interval incorrecte (NO USAR)
00*lema=somriure&01-03*cg=(qualsevol)&04*forma=mala&05*forma=fe
# total 0; echo: somriure mala fe  ← fals zero; la clau s'ignora

# G7 — forma simple
00*forma=mala&01*forma=fe
# total 294; echo: mala fe

# G8 — accent no estàndard
00*forma=mala&01*forma=fé
# total 29; echo: mala fé; explica que no és la forma normativa

# G9 — comodí + forma
00*cg=qualsevol&01*forma=de&02*forma=mala&03*forma=fe
# total 75; echo: [] de mala fe

# G10 — frase en dos elements
00*forma=somriure&01*forma=mofeta
# total 8; echo: somriure mofeta

# G11 — frase en un sol element (NO USAR)
00*forma=somriure mofeta
# total 0; echo: somriure_mofeta; l'espai es converteix en _

# G12 — lema + categoria
00*lema=somriure@V
# total 8606; echo: somriure V

# G13 — lema:CG (NO USAR)
00*lema=somriure:V
# total 0

# G14 — negació de forma
00*lema=somriure&01*forma=<>amb
# total 13727; echo: somriure <>amb

# G15 — negació d'alternança
00*lema=somriure&01*forma=<>(amb|de)
# total 13061; echo: somriure <>(amb | de)

# G16 — negació de categoria
00*lema=somriure&01*cg=<>adj:-
# total 12154; echo: somriure <>adj:-

# G17 — combinació invàlida
00*lema=somriure&01*forma=(<>amb)&02*forma=mala
# HTTP 500; no enviar

# G18 — categoria sense morfologia (NO USAR)
00*lema=somriure&01*cg=adj
# HTTP 500; generar adj:- 

# G19 — morfologia
00*lema=somriure&01*cg=V:3II
# total 49; echo: somriure V:3II

# G20 — formalema
00*formalema=somriure:V¬somriure:IF|somreia:3II
# total 3489; echo amb espai d'amplada zero

# G21 — paginació
00*lema=somriure&01*cg=adj:-&iStart=1&iOffset=1000     # 1000
00*lema=somriure&01*cg=adj:-&iStart=1001&iOffset=1000  # 1000
00*lema=somriure&01*cg=adj:-&iStart=2001&iOffset=1000  # 136
# 1-based; sense duplicats d'ID d'ocurrència

# G22 — cerca bàsica de lema
POST FormesLema2.asp  cadlema=somriure&cadlemacond=0&cg=
# total 14290; capçalera Lemes, no Patró seleccionat

# G23 — cerca bàsica de forma
POST Formes2.asp  cadforma=somriure&cadformacond=0&cg=
# total 7529; capçalera Forma

# G24 — modes de truncament
POST Formes2.asp  cadforma=somriu&cadformacond=0  # 2019
POST Formes2.asp  cadforma=somriu&cadformacond=1  # 10628
POST Formes2.asp  cadforma=somriu&cadformacond=2  # 2019
POST Formes2.asp  cadforma=somriu&cadformacond=3  # 10630
POST Formes2.asp  cadforma=somriu&cadformacond=4  # 0
POST Formes2.asp  cadforma=somriu&cadformacond=5  # 0
POST Formes2.asp  cadforma=somriu&cadformacond=6  # 0
```

Notes:

- Els recomptes són exactes per a la data; no els converteixis en constants eternes.
- `G6` ha de fallar el test si s'envia; el compilador ha de produir `G5`.
- `G11` ha de fallar la validació; `cerca_forma` no accepta espais.
- `G17` i `G18` han de fallar la validació abans d'arribar al servidor.
- `G20` ha de netejar `\u200b` abans de mostrar l'echo.
- `G21` ha de verificar que els IDs d'ocurrència no es repeteixen entre pàgines.

---

## 8. Legal, ètica i privacitat

El pla diu:

> Ús privat i de recerca: sense fricció detectada.  
> No fer descàrregues massives; cachejar i limitar el ritme.  
> Si el servidor MCP es publiqués o integrés en producte: contactar prèviament `dcc@iec.cat`.

És un bon punt de partida, però cal matisar-lo:

- **No hem trobat una prohibició explícita** a les pàgines del CTILC, però tampoc una autorització general per a l'extracció automatitzada. «Sense fricció detectada» no és el mateix que «permès».
- `robots.txt` i `sitemap.xml` retornen 404; **l'absència de `robots.txt` no és permís**. Si el lloc afegeix un `robots.txt` o uns termes d'ús, cal respectar-los.
- El corpus inclou obres amb drets d'autor. Els extracts per a recerca poden ser acceptables, però **no s'han de redistribuir massivament** ni incorporar-se a productes comercials sense autorització.
- La pàgina de presentació diu que les obres descarregables són de domini públic i es poden usar lliurement per a ús privat o de recerca; això no cobreix tot el corpus ni les consultes.
- El `resultat` cachejat al servidor pot quedar accessible per ID; no hi posis consultes sensibles.
- L'MCP ha de:
  - identificar-se amb un `User-Agent` i un contacte;
  - citar el CTILC i l'IEC;
  - no usar el logo de l'IEC ni presentar-se com a oficial;
  - limitar el ritme i la mida de les respostes;
  - no oferir descàrregues massives per defecte;
  - incloure un `NOTICE` amb copyright i citació;
  - contactar `dcc@iec.cat` abans de publicar o integrar en un producte.
- Citació recomanada:
  > Corpus Textual Informatitzat de la Llengua Catalana (CTILC), Institut d'Estudis Catalans, <https://ctilc.iec.cat/>, consulta feta el 18/11/2026.
- Privacitat: logs mínims; no registrar textos sencers de les consultes; si es guarden, TTL curt i accés restringit.

---

## 9. Pla d'implementació revisat

La proposta de fases del pla és raonable, però optimista. Una estimació més realista:

1. **Fase 0 — protocol i fixtures (1 dia):** capturar peticions/respostes reals, crear fixtures, escriure el compilador i el client HTTP amb el `*` literal, tests unitaris.
2. **Fase 1 — MVP (2–3 dies):** `cerca_patro`, `ocurrencies` amb cursor, parser de Coocur, golden tests, `salut`.
3. **Fase 2 — cerques bàsiques i context (2 dies):** `cerca_forma`, `cerca_lema`, `cerca_nom_propi`, `fitxa_localitzacio`, `formes_de_lema`.
4. **Fase 3 — anàlisi (2–3 dies):** `collocacions`, `dispersions`, `corpus_xifres`, `filtres_disponibles`, `obres`.
5. **Fase 4 — exportació i documentació (1–2 dies):** CSV si es verifica, README, `NOTICE`, exemples, proves amb preguntes reals.
6. **Manteniment:** drift de protocol, re-baseline de golden tests, actualització del tagset, revisió legal.

Un sol fitxer de 300–500 línies no és realista per a 10 eines, 5 parsers, cursor, cache, validació i tests. Més aviat 1.200–1.800 línies de codi + tests + documentació; millor dividir en mòduls:

```text
ctilc_mcp/
  __init__.py
  server.py        # eines MCP
  client.py        # HTTP, rate limit, cache
  compiler.py      # QuerySpec -> NN*clau
  parsers/
    coocur.py
    basic.py
    collocations.py
    dispersions.py
    fitxa.py
    dades.py
  models.py        # Pydantic
  tagset.py
  tests/
```

---

## 10. Decisions obertes

1. **Abast:** és un MCP personal/de recerca o un producte publicat? Canvia el règim legal, la documentació i la necessitat de contactar l'IEC.
2. **CQL cru:** s'exposa `raw_cql` experimental o no? Recomanació: no a la MVP; si es fa, amb validació i límits.
3. **CSV:** es verifica amb una captura de navegador o s'elimina de la MVP?
4. **Filtres:** es vols exposar filtres estructurals complets o només els més habituals (autor, any, gènere, varietat)?
5. **Sortida:** 50 files per defecte; quantes com a màxim? Quant context per ocurrència?
6. **Idioma de les eines:** català (actual) o anglès? Es poden mantenir noms catalans i documentar-los en anglès.
7. **Desplegament:** stdio, HTTP o tots dos? Quin client MCP es vol suportar primer?
8. **Llicència:** MIT/Apache-2.0 per al codi; `NOTICE` per al corpus.

---

## Apèndix A. Evidències puntuals

- `GET /scripts/CTILCQConc_Coocur2.asp` → **500**; `POST` amb `00*lema=somriure&01*cg=adj:-` → **200**, 2.136.
- Capçalera d'alguns resultats: `Content-Type: text/html;; Charset=UTF-8`; `Server: IEC_HTTP_Server`; `Set-Cookie: ASPSESSIONID...`.
- Respostes grans: `curl` error 56 (`unexpected eof while reading`) amb cos complet de ~1 MB que acaba en `</html>`.
- `requests` amb `data={"00*lema": ...}` → cos `00%2Alema` → **500**; cos manual `00*lema` → **200**.
- `resultat=179500525152020580` → 2.136; `resultat=179500525152020576` → total 2.136, **0 files**.
- `iStart=0` → 999; `iStart=1` → 1.000; `iStart=1001` → 1.000; `iStart=2001` → 136.
- `01-03*cg=(qualsevol)` → echo `somriure mala fe`, 0; expandit → echo `somriure []? []? []? mala fe`, 0.
- `00*forma=somriure mofeta` → 0, echo `somriure_mofeta`; `00*forma=somriure&01*forma=mofeta` → 8.
- `00*lema=somriure&01*cg=adj` → 500; `adj:-` → 2.136.
- `00*lema=somriure&01*forma=(<>amb)&02*forma=mala` → 500.
- `00*lema=somriure@V` → 8.606; `00*lema=somriure:V` → 0.
- `00*formalema=somriure:V¬somriure:IF|somreia:3II` → 3.489; echo amb `&#8203;`.
- `QCol_LemesAgrup1.asp` → formulari; `QCol_LemesAgrup2.asp` → 1.159 col·locacions per a *somriure* (radis 3/3, `freqMin=5`).
- `FitxaLocalitzacio.asp?id=558397&obra=6` → `Id. obra: 8`; `id=82148513&obra=4542` → `Id. obra: 4534`.
- `Qjson_concordancesCSV.asp` amb `cCSV1` (inner/outer de `cHTML1`, inner de `cHTML2`, sense `cCSV1`, amb `Referer`/`Origin`) → **500**.
- `strquery` original → 2.136; `strquery` amb només `[tag="A:.*"]` → 1.591; `[]{0,3}` → 0.
- `CTILCQDadesNum.asp`: total 126.604.218; analitzats 102.493.057; noms propis 2.344.195; no analitzables 4.875.907; altres 16.891.059.
- `robots.txt` i `sitemap.xml` → 404; la pàgina 404 diu «IIS 8.5».

---

## Apèndix B. Citacions del pla que cal corregir

- «`01-03*cg=(qualsevol)`» → no existeix; expandir.
- «`forma somriure mofeta` → 8» → és un patró de dos elements; `cerca_forma` dona 0.
- «`QCol_*Agrup1.asp`» → els resultats són a `Agrup2.asp`.
- «`fitxa_obra`» → és `fitxa_localitzacio`; `obra` no és l'ID canònic.
- «`exportar_csv` ... `resultat_id`» → no verificat; 500 a les probes.
- «cap endpoint accepta CQL cru» → hi ha `strquery`, executable, però no és una API general.
- «manteniment baix» → el corpus creix ~5 M paraules/any; cal drift.
- «995 parelles diferents, 879 adjectius» → en la nostra anàlisi, 995 és el nombre de parelles úniques case-sensitive; 982 case-insensitive; 879 és el nombre de segons tokens únics. Cal definir la mètrica.
- «40, 39, 31, 26, 8» → adjacència/nominal; les col·locacions ±3 donen 61, 70, 52, 40, 17.
- «0 al web català» → no és un corpus; no es pot concloure absència.
- «El català ho expressa adjectivalment» → hipòtesi, no conclusió.
