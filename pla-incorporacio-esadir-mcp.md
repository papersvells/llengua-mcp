# Pla d’incorporació d’ésAdir al futur MCP de llengua

**Data de les proves:** 18 de novembre de 2026  
**Objecte:** avaluar com integrar [ésAdir](https://www.esadir.cat/) —el portal lingüístic de la CCMA— en el futur MCP del CTILC, com a font de consulta d’estil, lèxic, gramàtica, pronunciació, topònims i noms propis.  
**Abast:** només consulta i citació. No s’ha de confondre ésAdir amb la norma de l’IEC ni amb un corrector automàtic.

---

## 1. Veredicte

**Sí, és viable incorporar ésAdir**, però com a **font de consulta i estil**, no com a autoritat normativa única ni com a motor de correcció.

- Les fitxes són pàgines HTML estables i es poden parsejar.
- La cerca funciona per HTTP, però és **inconsistent per a lemes multiparaula** i barreja resultats de seccions molt diferents.
- Les URL de fitxa són la via més fiable quan es coneix l’entrada; la cerca serveix per descobrir-ne.
- No hi ha una API JSON pública de cerca; sí un autocomplete JSON limitat.
- L’àudio de pronunciació és sota `/back/`, que `robots.txt` bloqueja: **no s’ha de descarregar**; només enllaçar o mostrar la URL.

Per tant, l’adaptador ha de combinar:

1. **Cerca** per descobrir candidats.
2. **Fitxa directa** per llegir l’entrada.
3. **Cache local** de termes resolts.
4. **Citació i etiquetes d’autoritat** clares.

---

## 2. Quin paper ha de tenir ésAdir

| Necessitat | Font preferent | Paper d’ésAdir |
|---|---|---|
| Norma, ortografia, lèxic general | Optimot / IEC | Complement: etiquetes “recollit al DIEC”, “no recollit al DIEC”, ús general |
| Estil de mitjans, ràdio i TV | ésAdir | **Font principal** |
| Pronunciació | ésAdir / DIEC | **Font principal** per a AFI i àudio |
| Topònims i noms propis | ésAdir | **Font principal** |
| Ús real en textos | CTILC | No hi intervé |
| Correcció automàtica | Motor local | Només evidència per als dubtes |

**Regla d’or:** una absència a ésAdir no significa que una forma sigui incorrecta. ésAdir és un portal d’estil i de consulta, no un diccionari exhaustiu.

---

## 3. Proves fetes

Totes amb `GET`, `User-Agent` de revisió i ritme lent. Els recomptes són orientatius i poden canviar.

| Prova | Paràmetres principals | Resultat observat |
|---|---|---|
| Cerca exacta `foc` | `critericerca=foc&condiciocerca=0` | 56 elements; majoritàriament fitxes de Filmoteca |
| Cerca exacta `foc` + Lèxic | `lstTipusElement=lexic#pagina#general` | 0 resultats |
| Cerca exacta `al` | `condiciocerca=0` | 546 elements |
| Cerca exacta `al` + Gramàtica | `lstTipusElement=gramatica#pagina#general` | 242 elements, amb paginació |
| Cerca exacta `Barcelona` + Topònims | `lstTipusElement=toponim#pagina#general` | 351 elements |
| Cerca exacta `Grammy` + Noms propis | `lstTipusElement=nompropi#pagina#general` | Redirigeix a la fitxa `Grammy` |
| Cerca exacta `a gust` | `condiciocerca=0` | 6 elements, sobretot pel·lícules; **no** retorna la fitxa `a gust` |
| Cerca exacta `hidrosisme` + Lèxic | `lstTipusElement=lexic#pagina#general` | 0 elements |
| Cerca exacta `marxa a vista` | `condiciocerca=0` | 0 elements |
| Fitxa directa `a gust` | `/entrades/fitxa/node/a_gust` | 200; fitxa completa |
| Fitxa directa `hidrosisme` | `/entrades/fitxa/node/hidrosisme` | 200; AFI i enllaços d’àudio |
| Fitxa directa `marxa a vista` | `/entrades/fitxa/node/marxa-a-vista` | 200; fitxa completa |
| Autocomplete `a gust` | `/ajax/autocomplete?term=a%20gust` | `[]` |
| Autocomplete `foc` | `/ajax/autocomplete?term=foc` | Noms de topònims, no fitxes |
| Feed de canvis | `/canvis/feed` | Atom vàlid amb títol, data i URL |
| `sitemap.xml` | `/sitemap.xml` | Retorna HTML, **no** un sitemap |
| `robots.txt` | `/robots.txt` | Permet la cerca; bloqueja `/admin/`, `/phpmyadmin/`, `/back/`, `/cache/` |

### Conclusió de les proves

- La cerca exacta **no és fiable** per a lemes amb espais: `a gust`, `hidrosisme` i `marxa a vista` existeixen com a fitxes, però la cerca no les troba o no les posa primer.
- La cerca per **contingut** és més útil per descobrir, però barreja Filmoteca, Topònims, Noms propis, Gramàtica i la resta del llibre d’estil.
- Els filtres de secció funcionen, però depenen de `lstTipusElement` i de valors com `lexic#pagina#general`; no són un paràmetre estable i cal provar-los.
- Les **fitxes directes** són la font de veritat. Cal resoldre el terme a una URL de fitxa abans de llegir.
- L’autocomplete només retorna cadenes, sovint de topònims; no serveix per resoldre una entrada.
- El **feed** serveix per detectar canvis recents, no per construir un índex complet.

---

## 4. Troballes tècniques

### 4.1. Cerca

```text
GET https://www.esadir.cat/cerca/resavancada
  ?critericerca=al
  &condiciocerca=0
  &criteri=General
  &lstTipusElement=gramatica#pagina#general
  &marca=1
```

Valors de `condiciocerca`:

| Valor | Significat |
|---:|---|
| 0 | coincident |
| 1 | aproximat |
| 2 | comença per |
| 3 | conté |
| 4 | acaba en |

- `criteri`: `General` o `Pelis`.
- `lstTipusElement`: seccions separades per `#`, amb `#pagina#general` al final. Exemples: `lexic#pagina#general`, `gramatica#pagina#general`, `toponim#pagina#general`, `nompropi#pagina#general`.

Mapa de seccions observat:

| Secció visible | Valor per a `lstTipusElement` |
|---|---|
| Lèxic | `lexic` |
| Gramàtica | `gramatica` |
| Topònims | `toponim` |
| Noms propis | `nompropi` |
| Convencions | `convencions` |
| Doblatge | `traduccio` |
| Altres llengües | `altresllengues` |
| Enllaços | `enllac` |

Cal validar aquest mapa amb fixtures; els noms interns poden canviar.
- Paginació: `page=2`, `page=3`…; la consulta sembla quedar a la sessió, així que cal mantenir la `PHPSESSID` o repetir la cerca.
- Resultats: blocs “Coincidències en el títol de les fitxes”, “Coincidències en el cos de les fitxes” i “Resultats a la resta del llibre d’estil”.
- Cada resultat té títol, apartat i, sovint, enllaç a la fitxa.

### 4.2. Fitxes

Patrons observats:

```text
/entrades/fitxa/node/a_gust
/entrades/fitxa/node/hidrosisme
/entrades/fitxa/node/marxa-a-vista
/entrades/fitxa/id/5104
/toponims/...
/nomspropis/...
/filmoteca/fitxa/node/...
```

L’estructura de la pàgina:

- `main > h1`: títol de l’entrada.
- `#etiquetes`: targetes com “ús general”, “recollit al DIEC”, “no recollit al DIEC”.
- `#pronuncia`: AFI, sovint amb variants `[or.]` i `[occ.]`.
- Paràgrafs de definició i exemples.
- Enllaços relacionats i, de vegades, enllaços d’àudio.
- L’àudio es genera amb JavaScript:

```js
javascript:reprodueixSo('//www.esadir.cat/back/filelib/so/hidrosisme-or.mp3')
```

`robots.txt` bloqueja `/back/`: **no descarreguis aquests MP3**. La fitxa pot retornar la URL com a metadada, però l’MCP no ha de fer la petició.

### 4.3. Metadades i sessions

- `Content-Type: text/html; charset=utf-8`.
- `Set-Cookie: PHPSESSID=...`.
- `Cache-Control: no-store, no-cache, must-revalidate`.
- Cal `requests.Session`/`httpx.AsyncClient` amb cookies; no confiar en cache HTTP.
- El lloc respon per HTTP/2; `httpx` ho pot gestionar.
- `sitemap.xml` no és un sitemap: no l’utilitzis.
- `/canvis/feed` és Atom i sí que és útil per a “novetats” i per invalidar cache de fitxes recents.

---

## 5. Disseny de l’adaptador

### 5.1. Mòdul

```text
llengua_mcp/
  adapters/
    esadir.py
    optimot.py
    ctilc.py
  parsers/
    esadir_search.py
    esadir_entry.py
  models.py
  cache.py
```

Si es manté el servidor `ctilc` actual, es pot afegir un adaptador `esadir` dins del mateix procés i exposar eines amb prefix `esadir_*`. Si es prefereix separar responsabilitats, un servidor `llengua` pot agrupar CTILC + Optimot + ésAdir.

### 5.2. Model de dades

```json
{
  "source": "esadir",
  "authority": "CCMA",
  "kind": "entry",
  "title": "a gust",
  "section": "Lèxic",
  "url": "https://www.esadir.cat/entrades/fitxa/node/a_gust",
  "labels": ["ús general", "recollit al DIEC"],
  "pronunciation": [],
  "definitions": ["Còmodament, amb satisfacció."],
  "examples": ["El porter alemany diu que vol renovar el contracte perquè se sent a gust al club"],
  "related": [],
  "audio_urls": [],
  "retrieved_at": "2026-11-18T…",
  "caveats": []
}
```

Per a resultats de cerca:

```json
{
  "title": "en / al [+ infinitiu]",
  "section": "Sintaxi",
  "snippet": "…",
  "url": "https://www.esadir.cat/entrades/fitxa/…",
  "match": "title",
  "score": 0.92
}
```

### 5.3. Eines MCP

| Eina | Entrada | Sortida |
|---|---|---|
| `esadir_consulta` | `termes`, `seccio?`, `condicio?`, `limit?` | Resultats amb títol, apartat, fragment, URL i tipus |
| `esadir_fitxa` | `url` o `slug` o `id` | Fitxa estructurada |
| `esadir_novetats` | `limit?` | Entrades del feed Atom |
| `esadir_suggeriments` | `prefix` | Suggeriments de l’autocomplete, marcats com a tals |

Opcionalment, una eina orquestradora:

| Eina | Funció |
|---|---|
| `consulta_llengua` | Consulta Optimot + ésAdir + CTILC segons la intenció i retorna fonts, conflictes i cauteles |
| `confronta_norma_us` | Compara la recomanació d’Optimot/ésAdir amb l’ús atestat al CTILC |

### 5.4. Resolució de termes

Ordre de resolució:

1. **URL directa** si l’usuari la proporciona.
2. **Cerca exacta** amb `condiciocerca=0`; si retorna una fitxa o redirecció, usar-la.
3. **Cerca per contingut** amb `condiciocerca=3`, filtrant per secció; agafar els primers resultats i quedar-se amb els que tinguin URL de fitxa.
4. **Cerca aproximada** amb `condiciocerca=1` només com a fallback.
5. **Autocomplete** només per suggerir formes, no per resoldre fitxes.
6. Si no hi ha resultat, retornar `no_result` i suggerir Optimot o la cerca avançada; **no** concloure que la forma no existeix.

Guardar la resolució `term → URL` en cache amb TTL, i invalidar-la si el feed de canvis mostra una entrada actualitzada.

### 5.5. Parsing de resultats

- Recórrer els blocs de resultats; identificar el tipus de coincidència (títol, cos, resta del llibre d’estil).
- Extreure `h1`/títol, apartat i enllaç.
- Deduplicar per URL canònica.
- Prioritzar resultats de la secció demanada; després, els de títol; després, els de cos.
- No sumar recomptes de blocs diferents com si fossin la mateixa cosa.

### 5.6. Parsing de fitxes

- `main h1` → títol.
- `#etiquetes` → etiquetes d’ús i DIEC.
- `#pronuncia` → AFI i variants.
- Paràgrafs de `main` → definició/exemples.
- Enllaços a `/entrades/`, `/toponims/`, `/nomspropis/`, `/filmoteca/` → relacionats.
- Enllaços `javascript:reprodueixSo(...)` → extreure la URL, però **no fetch**.
- Netejar `\xa0`, `\u200b`, espais dobles i entitats HTML.

---

## 6. Integració amb la resta de l’MCP

### 6.1. Jerarquia de fonts

1. **Optimot** per a norma, lèxic, terminologia, castellà-català i verbs.
2. **ésAdir** per a estil de mitjans, pronunciació, topònims i noms propis.
3. **CTILC** per a atestació i ús.
4. **Motor local** per a detecció ortogràfica i gramatical.

Si les fonts discrepen, retornar `conflicts`:

```json
{
  "question": "al ulls / als ulls",
  "answers": [
    {"source": "optimot", "position": "als ulls", "url": "…"},
    {"source": "esadir", "position": "als ulls", "url": "…"},
    {"source": "ctilc", "note": "atestació de la seqüència…", "url": "…"}
  ],
  "resolution": "La norma i l’estil coincideixen; el corpus només mostra ús.",
  "caveats": []
}
```

### 6.2. Flux d’usuari

- **“Com s’escriu ‘a gust’?”** → `esadir_fitxa` o `esadir_consulta`; retorna definició, etiquetes i exemples.
- **“Com es pronuncia ‘hidrosisme’?”** → `esadir_fitxa`; retorna AFI i enllaç d’àudio (sense descarregar-lo).
- **“És correcte ‘al ulls’?”** → motor local detecta `al` + plural; `consulta_llengua` busca Optimot/ésAdir; CTILC dona contextos si cal.
- **“És normatiu ‘X’?”** → Optimot primer; ésAdir com a complement; si ésAdir diu “no recollit al DIEC”, no ho converteixis automàticament en “incorrecte”.
- **“Què en diu la CCMA?”** → ésAdir; cita la font i la data.

---

## 7. Cortesia, límits i aspectes legals

- `robots.txt` d’ésAdir permet la cerca i les fitxes, però **bloqueja `/back/`**. No descarreguis àudio.
- No facis crawling massiu de les 50.000 fitxes. Fes servir la cerca i la cache.
- Rate limit global: 1 req/s o menys; jitter; cache de resultats i fitxes.
- User-Agent identificable i contacte.
- Cita sempre ésAdir/CCMA i la URL; no presentis el resultat com a norma de l’IEC.
- No reprodueixis fitxes senceres en productes públics; fragments curts i enllaç.
- El text de l’usuari no s’ha d’enviar sencer a ésAdir; fes consultes puntuals.
- Respecta `no-store`: la cache és local, amb TTL i invalidació pel feed.

---

## 8. Proves i fixtures

Crear fixtures amb aquests casos:

| Fixture | Comportament esperat |
|---|---|
| `foc_exact` | 56 elements; majoritàriament Filmoteca; no és una fitxa lèxica |
| `al_gram` | 242 elements; paginació; resultats de Gramàtica |
| `barcelona_top` | 351 elements; topònims |
| `grammy_np` | Redirecció a la fitxa `Grammy` |
| `agust_entry` | Fitxa directa `a gust`; definició i etiquetes |
| `hidro_entry` | Fitxa directa `hidrosisme`; AFI i àudio (no fetch) |
| `marxa_entry` | Fitxa directa `marxa a vista` |
| `agust_search` | 6 elements; no retorna la fitxa; cal resolució directa |
| `hidro_search` | 0 elements; la fitxa existeix |
| `marxa_search` | 0 elements; la fitxa existeix |
| `autocomplete_foc` | Noms de topònims, no fitxes |
| `feed` | Atom amb títol, data i URL |
| `robots` | Bloqueig de `/back/` |

Proves unitàries:

- Construcció d’URL de cerca amb `condiciocerca` i `lstTipusElement`.
- Parseig de resultats i deduplicació.
- Parseig de fitxa: títol, etiquetes, AFI, definició, exemples.
- Resolució `term → URL` i cache.
- No fetch d’URLs `/back/`.
- Gestió de redirecció a fitxa.
- Gestió de zero resultats sense convertir-ho en “no existeix”.

Proves en viu: opcionals, amb 1 req/s, i amb data; no a CI.

---

## 9. Fases d’implementació

1. **Fase A — lector de fitxes:** `esadir_fitxa` per URL/slug/id; parser i fixtures. És la part més estable.
2. **Fase B — cerca:** `esadir_consulta` amb seccions i paginació; resolució de termes; cache.
3. **Fase C — novetats:** `esadir_novetats` amb el feed Atom; invalidació de cache.
4. **Fase D — orquestració:** `consulta_llengua` i `confronta_norma_us` amb Optimot i CTILC.
5. **Fase E — correcció:** el motor local detecta dubtes i consulta ésAdir/Optimot només per als casos dubtosos.

No començaria per la correcció. Primer cal demostrar que la consulta i la citació són fiables.

---

## 10. Riscos i decisions obertes

- **Cerca inconsistent:** la cerca exacta falla en lemes multiParaula; cal combinació de cerca + fitxa directa + cache.
- **Filtres fràgils:** `lstTipusElement` no és una API estable; cal provar i versionar.
- **Sessions:** la paginació pot dependre de `PHPSESSID`; no es pot assumir stateless.
- **Contingut no exhaustiu:** ésAdir no és un diccionari complet; una absència no és una incorrecció.
- **Autoritat:** ésAdir és estil de la CCMA, no norma de l’IEC; cal mostrar-ho.
- **Àudio bloquejat:** no descarregar `/back/`; enllaçar.
- **Canvis de HTML:** fixturitzar i detectar drift.
- **Privacitat:** no enviar textos sencers; consultes puntuals.
- **Legal:** contactar la CCMA/ésAdir abans d’un servei públic; citar i no redistribuir.

---

## 11. Exemple de resposta final

> **a gust**  
> ésAdir, Lèxic: “ús general; recollit al DIEC (DIEC2 - novembre 2024)”.  
> Definició: “Còmodament, amb satisfacció.”  
> Exemple: “El porter alemany diu que vol renovar el contracte perquè se sent a gust al club.”  
> Font: https://www.esadir.cat/entrades/fitxa/node/a_gust (consulta 18/11/2026).  
> Nota: ésAdir és una font d’estil de la CCMA; per a la norma, contrasta-ho amb Optimot/IEC.

> **hidrosisme**  
> ésAdir, Lèxic: “ús general; no recollit al DIEC”.  
> AFI: [or.] iðɾusízmə; [occ.] iðɾosízme.  
> Definició: “Fenomen sísmic produït per un augment sobtat de la quantitat d’aigua en el subsol…”  
> Àudio: disponible a la fitxa (no descarregat per respecte a `robots.txt`).  
> Font: https://www.esadir.cat/entrades/fitxa/node/hidrosisme

---

## 12. Decisió recomanada

Incorporar ésAdir com a **adaptador de consulta** dins del futur servidor `llengua`, amb `esadir_fitxa` i `esadir_consulta`, i reservar la correcció per a una fase posterior amb motor local. La combinació natural serà:

- **Optimot** → norma i lèxic general.
- **ésAdir** → estil, pronunciació, topònims i noms propis.
- **CTILC** → ús i atestació.
- **Motor local** → detecció i suggeriments.

Aquesta separació és la que permetrà que l’MCP sigui útil sense convertir-se en un oracle que confon “no ho he trobat” amb “no és correcte”.
