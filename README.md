# llengua — MCP de consultes de llengua catalana

`llengua` és un servidor MCP local per a OpenCode. Permet plantejar un dubte
sobre una paraula, una expressió o una frase, consultar fonts amb autoritat
diferent i obtenir una resposta pràctica i documentada. No revisa documents
sencers ni substitueix un corrector.

## Fonts

| Font | Eina | Què aporta |
|---|---|---|
| [Optimot](https://aplicacions.llengua.gencat.cat/llc/AppJava/index.html) | `optimot_cerca`, `optimot_fitxa` | Criteris sobre gramàtica, construcció, registre i lèxic |
| [DIEC](https://dlc.iec.cat/) | `diec_consulta` | Lèxic normatiu i accepcions |
| [ésAdir](https://www.esadir.cat/) | `esadir_consulta`, `esadir_fitxa` | Estil de la CCMA, pronunciació i noms propis |
| [BDLex](https://bdlex.iec.cat/) | `bdlex_consulta` | Diccionaris històrics i dialectals (DCVB, DIEC, Fabra...) |
| [CTILC](https://ctilc.iec.cat/) | `cerca`, `cerca_frase`, `cerca_patro`, `continuar_cerca`, `context`, `dispersio_cronologica`, `xifres`, `etiquetes`, `salut` | Ús escrit i contextos |
| [Softcatalà](https://www.softcatala.org/diccionari-de-sinonims/) | `cerca_sinonims` | Alternatives lèxiques (dades locals, CC BY 4.0) |

## Instal·lació

Requereix Python 3.11 o posterior.

```sh
uv venv .venv
uv pip install --python .venv/bin/python -e .
```

Per baixar les dades de sinònims (un sol fitxer, 1 MB aproximadament):

```sh
.venv/bin/python -m llengua_mcp.fetch_sinonims
```

Les dades es desen a `LLENGUA_DATA_DIR` (per defecte, el directori de dades de
l'usuari). El descàrrec usa un commit fixat perquè la instal·lació sigui
reproduïble; per actualitzar-les, `--ref master --force`.

## Configuració d'OpenCode

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "servers": {
      "llengua": {
        "type": "local",
        "command": ["/ruta/al/projecte/.venv/bin/python", "-m", "llengua_mcp.server"],
        "environment": {
          "LLENGUA_USER_AGENT": "llengua-mcp/0.1 (recerca; contacte)",
          "LLENGUA_CONTACT": "la-teva-adreca@example.com"
        },
        "timeout": { "execution": 60000 },
        "codemode": false
      }
    }
  }
}
```

Variables d'entorn:

| Variable | Per defecte | Ús |
|---|---|---|
| `LLENGUA_USER_AGENT` | `llengua-mcp/0.1` | Identificació del client |
| `LLENGUA_CONTACT` | buit | Contacte afegit al `User-Agent` |
| `LLENGUA_RATE` | `1.0` | Peticions per segon i per host (màxim 1.0) |
| `LLENGUA_TIMEOUT` | `45` | Temps màxim per petició, en segons |
| `LLENGUA_MAX_BYTES` | `4000000` | Mida màxima d'una resposta |
| `LLENGUA_MAX_OCCURRENCES` | `50` | Files màximes per pàgina del CTILC |
| `LLENGUA_CACHE_TTL` | `3600` | Validesa de la cache i dels cursors |
| `LLENGUA_DATA_DIR` | dades d'usuari | Fitxers de sinònims |
| `LLENGUA_CACHE_DIR` | cache d'usuari | Reservat per a cache persistent |

## Exemples d'ús

- **Corregir una construcció**: `optimot_cerca("tenir que", mode="frase_exacta")`
  i `optimot_fitxa(ref)` per justificar *he d'anar* en lloc de *tinc que anar*.
  Si la cerca exacta no dona res, `optimot_cerca("perífrasi d'obligació")`.
- **Comparar dues formulacions**: `diec_consulta("maliciós")` per al sentit i
  `cerca_patro` amb `lema=somriure@subst` + `cg=adj` per als contextos reals.
- **Trobar alternatives**: `cerca_sinonims("maliciós", context="un somriure maliciós")`
  i triar les opcions que conserven el sentit.
- **Documentar una forma antiga o dialectal**: `bdlex_consulta("engrunar")`, o
  cercar per definició: `bdlex_consulta(definicio="esclafar")`.
- **Comprovar una expressió**: `cerca_frase("tenir foc al ulls", variants=["tenir foc als ulls"])`.
  Cada variant es retorna per separat; els totals no se sumen.
- **Veure en quines èpoques apareix**: cerca i, amb el `next_cursor`,
  `dispersio_cronologica(cursor)`.

## Com interpretar els resultats

- **`status`**: `ok`, `no_matches` / `no_results`, `partial`, `invalid_query`,
  `upstream_error`, `unexpected_response`, `stale_search` o `unavailable`.
  Un error no es converteix mai en `total: 0`.
- **CTILC**: `echo_verified` exigeix que coincideixin els camps enviats i el
  patró visible. Un zero només és `no_matches` si la pàgina en dona el comptador
  explícit i el missatge de cap coincidència; si no, és `unexpected_response`.
  Si és `false`, el resultat no es pot presentar com una absència lingüística.
- **`next_cursor`**: continua la mateixa cerca. És local i caduca; si el total o
  el patró canvien, l'eina retorna `stale_search` i no barreja pàgines.
- **Dispersió cronològica**: passa el cursor d'una cerca concreta. Retorna per
  tram `hits`, `corpus_units` i `per_million` (ocurrències per milió, derivades
  dels enters del gràfic, mai del percentatge arrodonit). Es validen el patró i
  la suma dels trams; si no coincideixen, la gràfica no es presenta com a
  vàlida. Amb pocs testimonis, parla de concentració observada.
- **Optimot**: el nombre de resultats és un recompte de documents del portal, no
  una freqüència d'ús. Cal obrir la fitxa abans de citar-ne el criteri.
- **DIEC**: cal citar l'entrada i l'accepció. No trobar-hi una forma no la fa
  incorrecta.
- **ésAdir**: és estil de la CCMA, no la norma de l'IEC. Una cerca sense resultats
  no demostra que una forma sigui incorrecta.
- **BDLex**: agrupa diccionaris de períodes i abasts diferents. Cal citar el
  diccionari concret de cada entrada (`dictionary` / `dictionary_label`) i no
  tractar una forma antiga o dialectal com a adequada per a un text formal
  actual. Una absència tampoc no la fa incorrecta.
- **Sinònims**: són propostes de significat. Cada grup indica `relation`
  (`synonym` o `antonym`); un antònim no es presenta mai com a sinònim. Cal
  triar les opcions segons la frase i explicar-ne el matís.

## Límits coneguts

- La revisió automàtica de paràgrafs sencers no forma part de l'abast.
- Les cerques bàsiques del CTILC (`Formes2`, `FormesLema2`) i les col·locacions
  encara no s'exposen: calen fixtures i proves pròpies.
- L'exportació CSV del CTILC no s'implementa: l'endpoint no s'ha pogut verificar.
- El Corpus de consultes lingüístiques de l'IEC, la GBU, l'OIEC i Critèria són
  fonts previstes, però la seva consulta fiable requereix un flux addicional
  que encara no s'ha validat.
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

## Citació

> Corpus Textual Informatitzat de la Llengua Catalana (CTILC), Institut
> d'Estudis Catalans, <https://ctilc.iec.cat/>, consulta feta el DD/MM/AAAA.

Cada resposta inclou `source`, `retrieved_at` i `citation` per a la font
consultada.

## Desenvolupament

```sh
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/ruff format .
.venv/bin/ruff check .
.venv/bin/pytest
```

Els tests no fan xarxa. Les proves en directe són optatives i no formen part de
la integració contínua:

```sh
LLENGUA_LIVE=1 .venv/bin/pytest tests/test_live.py
```
