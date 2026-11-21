# AGENTS.md — MCP de consultes de llengua catalana

## 1. Què és aquest projecte

`llengua` serà un **servidor MCP d’assessorament sobre la llengua catalana**. Des d’OpenCode, l’usuari podrà plantejar un dubte sobre una paraula, una expressió o una frase. L’agent triarà les eines adequades, contrastarà les fonts quan calgui i donarà una resposta pràctica i documentada. Detectar barbarismes, comparar formulacions i trobar sinònims són tres casos d’ús inicials. La revisió automàtica de documents sencers queda fora d’abast.

**El repertori d’eines és obert.** Optimot, DIEC, ésAdir, CTILC i el diccionari de sinònims de Softcatalà són les primeres fonts previstes. S’hi podran incorporar altres recursos fiables segons les necessitats de consulta: per exemple, un conjugador per resoldre un dubte de flexió o un diccionari terminològic per trobar el terme precís d’un àmbit especialitzat.

Un dels adaptadors consulta el **CTILC** (Corpus Textual Informatitzat de la Llengua Catalana, de l’Institut d’Estudis Catalans). Les seves eines han de permetre:

- cercar lemes, formes i combinacions;
- obtenir contextos i fitxes de localització;
- consultar col·locacions, dispersions i xifres del corpus;
- diferenciar una **absència real** d’una **consulta mal formada**;
- citar i interpretar les dades amb les cauteles correctes.

El CTILC no té una API JSON moderna: és un lloc ASP amb formularis HTML i un motor de consultes intern. La feina principal és **traduir una intenció lingüística a una consulta vàlida** i tornar resultats estructurats, no HTML cru.

## 2. Estat actual

- Fase: **MVP complet; en ampliació**. El paquet `llengua_mcp` i els tests existeixen, i les 30 eines estan disponibles per a OpenCode amb `opencode.jsonc`.
- Implementat i provat en directe el 18/11/2026:
  - CTILC: `cerca`, `cerca_frase`, `cerca_forma`, `cerca_lema`, `cerca_patro`, `continuar_cerca`, `context`, `dispersio_cronologica`, `dispersio_dialectal`, `dispersio_general`, `collocacions`, `collocacions_forma`, `filtres_disponibles`, `obres`, `xifres`, `etiquetes`, `salut`.
  - Optimot: `optimot_cerca`, `optimot_fitxa`.
  - Corpus de consultes de l'IEC: `consultes_iec` (1.176 respostes curades; nonce + AJAX de wpDataTables, `table_id=7`).
  - DIEC: `diec_consulta`.
  - ésAdir: `esadir_consulta`, `esadir_fitxa`.
  - BDLex: `bdlex_consulta` (entrada, definició, exemple i text lliure; DCVB inclòs).
  - OIEC: `oiec_cerca`, `oiec_text` (ortografia normativa, via `api-oiec.iec.cat`).
  - Gramàtiques: `gramatica_cerca`, `gramatica_text` (GBU, GEIEC i GIEC, amb APIs JSON equivalents).
  - Softcatalà: `cerca_sinonims` amb dades locals versionades.
  - Jané: `jane_cerca` (implementat el 20/11/2026; nonce + AJAX de wpDataTables,
    taules 1, 4 i 5 per a lema, general i funció sintàctica).
- **Corpus de consultes lingüístiques de l’IEC: implementat el 18/11/2026.**
  La pàgina `/cerca-general/` porta un nonce (`wdtNonceFrontendServerSide_7`)
  que cal enviar a `admin-ajax.php?action=get_wdtable&table_id=7`. Amb el nonce
  i els paràmetres DataTables complets, l’AJAX retorna les 1.176 consultes;
  sense nonce o amb `table_id=1` (portada) retorna zero o el «Dubte del dia».
  Els temes són Fonètica, Lèxic, Morfologia, Onomàstica, Ortografia, Sintaxi i
  Altres. El filtre de pregunta és `columns[4][search][value]`.
- **Critèria: descartat (issue #7 tancada el 20/11/2026).** Per decisió de
  producte no s'integra. Consta la verificació del 20/11/2026: l'API REST sí que
  publica el contingut (455 posts, sense nonce), però la cerca de text és feble
  (només títols) i molt contingut viu en PDFs enllaçats. Per a ortografia i
  gramàtica ja hi ha l'OIEC i les gramàtiques de l'IEC.
- Els modes 4–6 de les cerques bàsiques del CTILC es van verificar el
  21/11/2026 amb `cg=I` i s'exposen amb `cg` obligatori. La cerca de noms propis es va descartar
  (issue #5, tancada el 20/11/2026). L'exportació CSV i les obres descarregables queden
  fora d'abast: l'MCP no fa extracció massiva ni descarrega textos sencers.
- Documents de referència:
  - `pla-mcp-ctilc.md` — pla inicial. És útil com a mapa del protocol, però **conté errors** i no s’ha d’implementar literalment.
  - `pla-mcp-ctilc-critiques.md` — revisió crítica amb verificació en directe, errors, correccions, golden tests i propostes. **És la font de veritat** quan els dos documents discrepin.
- Data de les comprovacions inicials: **18/11/2026**. Els recomptes del corpus poden canviar.
- Per a l’abast i les proves de cada adaptador, vegeu també `pla-mcp-ctilc-tercer-en-discordia.md`, `pla-incorporacio-optimot-mcp.md` i `pla-incorporacio-esadir-mcp.md`.

**Comprovacions en directe del 18/11/2026** (expectatives datades, no llindars eterns):

- `00*lema=somriure&01*cg=adj:-` → **2.136** (control de `salut`).
- `00*lema=somriure@subst&01*cg=adj:-` → **1.829**.
- `00*forma=somriure&01*forma=maliciós` → **32**; `00*lema=somriure&01*forma=amb|de&02*forma=mala&03*forma=fe` → **0**, amb eco verificat.
- `00*lema=somriure&01*forma=<>amb` → **13.727**; `00*formalema=somriure:V¬somriure:IF|somreia:3II` → **3.489**; amb un `[]?` opcional abans de *mala fe* → **0** amb eco verificat.
- `tenir foc al ulls` i `tenir foc als ulls` → **0** cadascun, amb eco verificat; és una absència en aquest corpus, no una prova que l’expressió no existeixi.
- Optimot, mode `frase_exacta` per «tenir que» → fitxa **6754/4**, versió **05.04.2023**, que qualifica *tenir que + infinitiu* com a no acceptable i dona *heu d’estudiar* com a forma correcta.
- Corpus de consultes de l’IEC: «tenir» → **257** (1.176 en total); tema **Sintaxi** → **347**; «tenir» a la pregunta → **12**.
- DIEC, «maliciós» → 3 accepcions; la tercera inclou l’exemple «Un somriure maliciós».
- ésAdir, «a gust» → fitxa amb definició i exemples; «hidrosisme» → AFI `[or.] iðɾusízmə` i `[occ.] iðɾosízme`.

## 3. Objectius

1. **Consultes fiables:** cada adaptador retorna evidència adequada a la font: article i accepció, fitxa i criteri, o bé patró, total i concordances per al CTILC.
2. **Zero falsos zeros:** si l’echo no coincideix amb la consulta enviada, no presentar el resultat com una absència lingüística.
3. **Interfície senzilla per a qualsevol model:** eines d’alt nivell que amaguin `NN*clau`, codis morfològics i detalls d’encoding.
4. **Reproducibilitat:** golden tests amb data, consulta exacta i resultat esperat; fixtures per a CI.
5. **Cortesia i legalitat:** rate limit, cache, User-Agent identificable, citació i contacte amb l’IEC abans de publicar.
6. **Compatibilitat amb OpenCode:** servidor MCP local per stdio, eines clares, configurable amb `mcp.servers`.

## 4. Fora d’abast (non-goals)

- No fer descàrregues massives ni mirall del corpus.
- No saltar captchas, límits o proteccions.
- No fer servir un navegador si n’hi ha prou amb HTTP.
- No afirmar que el CTILC representa la llengua oral o l’“ús quotidià”.
- No publicar extracts extensos ni redistribuir obres protegides.
- No presentar el projecte com un producte oficial de l’IEC.
- No exposar CQL cru com a API estable sense validació i advertències.

## 5. Principis de producte

**Resposta a l’usuari:** el model ha de consultar l’MCP, donar primer la correcció o la tria recomanada, explicar-ne breument el motiu i citar la font que ha llegit. Cal preservar el sentit i el to de la frase. Si l’original ja és correcte, es pot suggerir una alternativa més natural, marcada com a **opció d’estil**. Si una font no respon o no tracta el cas, cal dir-ho sense atribuir-li cap criteri.

| Font | Quan i com s’ha d’utilitzar |
|---|---|
| [Optimot](https://aplicacions.llengua.gencat.cat/llc/AppJava/index.html) | Per a dubtes gramaticals, de construcció o de registre. Si la consulta és una expressió concreta (p. ex. «tenir que»), provar `frase_exacta`; si és un fenomen, cercar amb `fitxes` les paraules clau. Obrir la fitxa pertinent i citar-ne la font original i la versió quan consti. |
| [Corpus de consultes de l’IEC](https://consultes-linguistiques.iec.cat/) | Per trobar una pregunta semblant i veure com l’ha resolta l’IEC, amb l’enllaç a la gramàtica o al diccionari. Citar la consulta; no substitueix l’Optimot ni la norma. |
| [DIEC](https://dlc.iec.cat/) | Per validar el lèxic: comprovar l’entrada i **l’accepció aplicable**. Una locució pot figurar dins l’article d’un dels seus mots. «No l’he trobada al DIEC» no justifica qualificar-la de barbarisme. |
| [ésAdir](https://www.esadir.cat/) | Per a criteris d’estil de la CCMA, pronunciació i noms propis. Atribuir el criteri editorial a ésAdir; una cerca sense resultats no prova que la forma sigui incorrecta. Si `esadir_consulta` dona `no_entry_results`, obrir `suggested_fitxa` amb `esadir_fitxa`. |
| CTILC | Per comprovar l’ús escrit: comparar patrons equivalents i llegir exemples en context. Admet filtres per autor, títol, any, tipus, gènere, tema (`classtem`), varietat i traducció. La freqüència, tota sola, no estableix la correcció ni el matís d’una expressió. |
| [BDLex](https://bdlex.iec.cat/) | Per consultar diccionaris històrics i dialectals (DCVB, DIEC, Fabra, obres dels segles XIX i XX). Pot cercar per entrada, definició, exemple o text lliure. És descriptiu i històric: una forma hi pot constar i no ser adequada avui; una absència no la fa incorrecta. Cal citar el diccionari concret. |
| [OIEC](https://oiec.iec.cat/) | Per regles d’ortografia (apòstrofs, guionets, accents, dièresis) que afecten molts mots. Citar el codi i el títol de l’apartat. |
| [GBU](https://gbu.iec.cat/inici), [GEIEC](https://geiec.iec.cat/inici) i [GIEC](https://giec.iec.cat/) | Per explicar una regla gramatical. La GBU és la consulta d’ús; la GEIEC, la versió en línia; la GIEC, la descripció especialitzada. |
| [Diccionari de sinònims de Softcatalà](https://www.softcatala.org/diccionari-de-sinonims/) | Per trobar alternatives. Cercar primer la paraula o locució sencera; si no hi ha entrada per a *de mala fe*, no donar sinònims de *fe* com si fossin de la locució. Prioritzar una còpia local versionada de les dades amb [atribució i llicència CC BY 4.0](https://www.softcatala.org/diccionari-de-sinonims/credits/). |
| [Diccionari de sinònims d'Albert Jané](https://sinonims.iec.cat/) | Per triar entre sentits: les accepcions numerades (`1.`, `2.`) separen significats i ajuden quan Softcatalà no desambigua. `mode="general"` cerca dins les llistes de sinònims; `mode="funcio"`, per funció sintàctica. Llicència CC BY-NC-ND 3.0: ús no comercial, entrades sense transformar i atribució a Albert Jané i a l'IEC; no barrejar amb les dades de Softcatalà. |

**Fonts addicionals previstes:** cap ara mateix. Les decisions obertes es
segueixen al repositori (issues).

**Criteris específics del corpus:**

- **Primer l’evidència, després la conclusió.** L’MCP dona dades; el model no ha de convertir `N > 0` en “és molt habitual”.
- **Atestació ≠ freqüència ≠ quotidianitat.**
  - `N > 0`: la seqüència està atestada en el corpus.
  - `N = 0`: no apareix en aquest corpus, no “no existeix”.
  - “Quotidià”: requereix corpus oral, registres i comparació; el CTILC tot sol no ho pot respondre.
- **El context mana.** Una ocurrència pot ser literal, figurada, una traducció, un error o una repetició dins d’una mateixa obra.
- **La dispersió és part del resultat.** No n’hi ha prou amb el total: calen obres, autors, anys, gèneres i varietats.
- **La normalització és obligatòria.** Per comparar èpoques, usar freqüència per milió o proporcions, no només recomptes absoluts.

## 6. Arquitectura tècnica prevista

- **Llenguatge:** Python 3.11+.
- **MCP:** SDK oficial `mcp` 2.x, classe `MCPServer` (l’antiga `FastMCP`), transport **stdio** per a OpenCode.
- **HTTP:** `httpx.AsyncClient` (no `requests` síncron dins d’una tool async).
- **Parsing:** `selectolax` o `lxml`/`BeautifulSoup`; **DOM, no només regex**.
- **Models:** `pydantic`.
- **Tests:** `pytest`, fixtures locals, VCR/cassettes; tests live opcionals.
- **Estructura prevista:**

```text
llengua_mcp/
  __init__.py
  server.py          # eines MCP
  app.py             # composició d'adaptadors
  config.py          # variables d'entorn
  http.py            # httpx, rate limit per host, cache
  cache.py           # cache TTL en memòria
  cursors.py         # cursors locals amb caducitat
  compiler.py        # QuerySpec -> NN*clau
  models.py
  tagset.py
  text.py            # normalització d'HTML i text
  sinonims.py        # índex local de Softcatalà
  fetch_sinonims.py  # baixada versionada de les dades
  adapters/
    ctilc.py
    optimot.py
    consultes.py
    diec.py
    esadir.py
    softcatala.py
  parsers/
    ctilc.py
    filtres.py
    fitxa.py
    dades.py
    optimot.py
    consultes.py
    diec.py
    esadir.py
tests/
  fixtures/
```

No cal un únic fitxer. La separació per parsers i client és important perquè cada pàgina del CTILC té una estructura diferent.

## 7. Regles crítiques del protocol CTILC

Aquestes regles estan verificades i no s’han de “simplificar” sense tornar-les a provar:

1. **`POST` a `CTILCQConc_Coocur2.asp`** amb `seccio=CTILC1` i elements `NN*clau=valor`. `GET` retorna 500.
2. **El `*` de la clau ha de quedar literal.** `requests`/`httpx` amb un `dict` l’envien com `%2A` i el servidor retorna 500. Construir el cos manualment o amb un encoder que respecti `*`.
3. **`cg` necessita morfologia.** `cg=adj` sol retorna 500; `cg=adj:-` funciona. Si no hi ha morfologia, generar `-`.
4. **`lema@CG` funciona; `lema:CG` no.** `formalema` té una gramàtica pròpia: `lema:cg¬forma:cg|forma:cg`.
5. **Els rangs no existeixen com a clau.** `01-03*cg=...` s’ignora i produeix un fals zero. Expandir a `01*cg`, `02*cg`, `03*cg`.
6. **`<>` i `()` no es poden combinar.** `(<>amb)` retorna 500. Validar `negat && opcional` com a error.
7. **`forma` és una sola forma.** Els espais es converteixen en `_`; per a frases cal un element per paraula. `cerca_forma("somriure mofeta")` no és el mateix que `cerca_patro` amb dos elements.
8. **`iStart` és 1-based.** `iStart=0` no és equivalent; validar `>= 1`. Paginar amb `iStart=1,1001,2001` i `iOffset=1000` funciona.
9. **L’ID `resultat` és un enter de 64 bits.** Ha de ser `string` a l’esquema, al JSON i al cursor. Un ID arrodonit pot retornar el total correcte i **0 files**.
10. **`resultat_id` no és un cursor.** Cal un cursor amb la consulta original, `Qlocali`, el patró i el proper offset; recompilar i re-POSTejar és més robust que dependre del cache del servidor.
11. **Les eines bàsiques i les combinacions tenen parsers diferents.** `Coocur2` fa servir `Patró seleccionat`; `Formes2`/`FormesLema2` fan servir `Forma`/`Lemes`.
12. **Els nuclis poden contenir etiquetes i espais d’amplada zero.** Netejar `<...>`, `&nbsp;`, `\u200b`, `\xa0` i col·lapsar espais.
13. **Col·locacions:** els resultats són a `CTILCQCol_LemesAgrup2.asp` / `FormesAgrup2.asp`, no a `Agrup1`. Calen `radiE`, `radiD` i `freqMin`; el resultat s’agrupa per categoria gramatical.
14. **Fitxa de localització:** `CTILCQFitxaLocalitzacio.asp` és una fitxa d’una ocurrència, no d’una obra. El paràmetre `obra` de la URL **no** és l’ID canònic; cal llegir `Id. obra` de la pàgina.
15. **CSV:** `Qjson_concordancesCSV.asp` no està verificat; a les proves va retornar 500. Descartat: l'exportació massiva queda fora d'abast.
16. **Un zero només és una absència verificada** si la pàgina dona un comptador explícit `0` i el missatge reconegut de cap coincidència. Un missatge de zero sense comptador, o un total il·legible, és `unexpected_response`, no `no_matches`.
17. **L'eco visible també es valida.** Els camps ocults `formdata` han de coincidir amb la consulta enviada i el patró visible ha de ser equivalent; si no, el resultat no es presenta com una absència.
18. **La continuació no barreja cerques.** Si el total o el patró canvien respecte del cursor, `continuar_cerca` retorna `stale_search` i descarta les files noves.
19. **`strquery` és un canal CQL intern**, però no una API general. Permet reexecutar el CQL compilat; els rangs i el CQL simplificat no funcionen. No exposar-lo sense validació i advertències.
20. **Els filtres canvien el total i l’eco.** Amb filtres, `Freqüència total` continua sent el total sense filtrar, i la xifra vàlida és `Quantitat filtrada`. Els camps `*Selec` (`autSelec`, `anySelec`, `varSelec`…) s’han de comparar amb els enviats. Si el resultat filtrat no té files, el portal pot retornar `1` com a valor de control: és `unexpected_response`, no una absència. Dues excepcions verificades el 20/11/2026: si l’autor s’ha validat abans contra `CTILCCorpus_Aut1.asp`, el total de control es converteix en `no_matches` amb `filtered_empty_verified`; i `classtem` només accepta un subtema a la vegada (els grups sencers van a `classtemGSelec`).
21. **Les obres tenen pàgines pròpies.** `CTILCCorpus_Aut1.asp` llista autors (`select#autorL`), `Aut2.asp` retorna les obres d’un autor i `Obr2.asp` cerca per títol. La taula no es pagina i una cerca massa àmplia pot superar el límit de 4 MB: cal retornar `too_many_results` amb una pista accionable, no un error genèric.
22. **La dispersió dialectal té tres gràfics.** `CTILCQDispersionsDial.asp` retorna la distribució del corpus, la proporció de la cerca per varietat i el repartiment de la cerca. Cal llegir el gràfic `Proporció`, que porta al tooltip el numerador i el denominador; no comparar recomptes absoluts entre varietats de mides diferents, sinó `per_million`. Un zero pot ser una mancança del corpus.
23. **Les cerques bàsiques tenen pàgines pròpies.** `Formes2.asp` i `FormesLema2.asp` no tenen «Patró seleccionat»: l’encapçalament és `Forma : …` / `Lemes : …` (plural) i `Freqüència total`. El panell `formesSelec` dona `form|lema CG|CM` a `Formes2` i `lema CG|form|CM` a `FormesLema2`: l’ordre canvia. La paginació és `iStart`/`iOffset` i no necessita el `resultat`. Els modes negatius 4–6 es verifiquen amb l’eco visible i els camps ocults de `fConc`; cal `cg` per evitar el fals zero de la cerca sense categoria. `iOffset` no limita el desglossament.
24. **La dispersió general creua sis atributs.** `CTILCQDispersions.asp` retorna tres gràfics per atribut (`Proporció`, `Repartiment`, `Total`/`Totals`). Cal aparellar `Repartiment` (ocurrències de la cerca) amb `Total`/`Totals` (corpus); `genere` suma només les obres literàries i `classificacio` les no literàries, així que no han de sumar el total general.

## 8. Eines MCP

Eines de consulta disponibles (30):

- `optimot_cerca` i `optimot_fitxa` — primera prioritat per verificar correccions; distingir candidats de fitxes llegides. Els resultats s’ordenen per coincidència amb la consulta; si el mode és poc precís, `suggested_mode` proposa una cerca alternativa.
- `consultes_iec` — respostes curades del Corpus de consultes de l'IEC. Serveix per trobar una pregunta semblant i veure com l'ha resolta l'IEC; retorna la pregunta, la resposta neta, el tema i els enllaços a la font. Cal citar la consulta i enllaçar la font; no substitueix la norma.
- `diec_consulta` — recuperar l’article i identificar l’accepció que justifica la resposta. Els articles llargs es retallen a `max_senses`; si `senses_truncated` és cert, apuja’l per veure les locucions del final.
- `esadir_consulta` i `esadir_fitxa` — descobrir i llegir entrades d’estil. Si `esadir_consulta` retorna `no_entry_results`, cal obrir `suggested_fitxa` amb `esadir_fitxa` abans de concloure que no hi ha entrada.
- `bdlex_consulta` — diccionaris històrics i dialectals, amb cerca per entrada, definició, exemple o text lliure. Usa el motor intern de BDLex, que no és una API pública documentada; si canvia, caldrà actualitzar el parser. El DDLC té un portal propi i no forma part del catàleg de BDLex.
- `oiec_cerca` i `oiec_text` — ortografia normativa: cerca per paraula i lectura d'apartats pel codi. L'API (`api-oiec.iec.cat`) és JSON net i sense autenticació.
- `gramatica_cerca` i `gramatica_text` — regles gramaticals a la GBU, la GEIEC i la GIEC. La GIEC fa servir el patró de l'OIEC (`cercadic/{mode}` amb la paraula codificada dues vegades); la GBU i la GEIEC, `search_text`/`text_by_cody`.
- `cerca_sinonims` — trobar alternatives a un mot o una expressió. Si l’usuari dona context, les agrupacions que hi coincideixen (etiqueta de sentit o formes) es retornen primer; el model selecciona dues o tres opcions pertinents, quan n’hi hagi, i explica el matís de cadascuna. Pot comprovar-ne el sentit al DIEC i la combinació al CTILC.
- `jane_cerca` — diccionari de sinònims d'Albert Jané (IEC), amb accepcions numerades. `mode="lema"` cerca pel començament del lema; `mode="general"`, el mot també dins les llistes de sinònims; `mode="funcio"`, per funció sintàctica (cal `funcio`). Retorna femenins, notes d'ús i enllaços a DIEC, DDLC, CTILC, BDLex, DCVB, CiT i TERMCAT. Complementa Softcatalà; les dades no s'han de fusionar.

Prioritat dins l’adaptador CTILC:

- `cerca_frase(frase, variants?, limit?)` — tokenitza, prova variants (`al`/`als`, accents, etc.), compila el patró i retorna una fitxa d’evidència.
- `cerca(lema?, forma?, categoria?, limit?)` — cerca simple per a la majoria de preguntes.
- `cerca_forma(forma, mode?, cg?, limit?, offset?)` — concordança bàsica amb el desglossament de formes i morfologia (modes 0–6; `cg` obligatori per als negatius).
- `cerca_lema(lema, mode?, cg?, limit?, offset?)` — concordança bàsica d’un lema amb les seves formes; útil per construir un `formalema`. Admet els mateixos modes, aplicats al lema.
- `continuar_cerca(cursor, limit?)` — reprèn una pàgina amb el cursor local.
- `cerca_patro(elements, limit?)` — patró avançat amb elements tipats.
- `context(occurrence_id)` — context ±50 i paràgraf, amb metadades de l’obra.
- `dispersio_cronologica(cursor)` — distribució per trams. Accepta el `search_cursor` de qualsevol cerca vàlida (o el `next_cursor`); si el patró o els totals no quadren, `data_valid` és fals, `periods` queda buit i les dades crues van a `unvalidated`.
- `dispersio_dialectal(cursor)` — distribució per varietat, amb `query_hits`, `corpus_hits`, `per_million` i `share_of_query`. Valida el patró i els totals; si no quadren, `data_valid` és fals i `varieties` queda buit.
- `dispersio_general(cursor)` — distribució per any, varietat, traducció, tipus, gènere i classificació temàtica. Cada atribut té el seu total: `genere` només cobreix les obres literàries i `classificacio` les no literàries.
- `collocacions(lema, radi?, freq_min?, limit?)` — coaparicions dins d'una finestra de ±radi mots (0-5), agrupades per categoria gramatical. Els resultats són a `CTILCQCol_LemesAgrup2.asp` (POST amb `cadlema`, `radiE`/`radiD`, `freqMin`); la pàgina conté totes les files. Les de puntuació de l'apartat ALTRES es descarten (`excluded_rows`) i els noms propis es retornen a part, a `altres`. Cal validar `lema_echo_verified` abans de fer servir les dades.
- `collocacions_forma(forma, radi?, freq_min?, limit?)` — el mateix per a una forma concreta (`CTILCQCol_FormesAgrup2.asp`, `cadforma`), útil per separar lectures que el lema barreja (`somriures` nom vs. `somriure` verb). Afegeix `info_mutua`, `freq`, `distancia`, `varianca` i `freq_lema`; cal validar `forma_echo_verified`. Sense resultats, el portal només dona un missatge sense comptador: `unexpected_response` amb `zero_without_counter`, no una absència verificada.
- `filtres_disponibles(cursor, tipus?, limit?, offset?)` — autors, títols o temes (`classtem`) d’un resultat concret, amb recompte. Serveix per triar valors vàlids abans de filtrar.
- `obres(autor?, titol?, autor_id?, limit?, offset?)` — metadades de les obres per autor o per títol (any, tipus, gènere, classificació, traducció i varietat). Si un cognom dona diversos autors, retorna `ambiguous_author` i cal continuar amb `autor_id`.
- `xifres()` — mida i cobertura del corpus.
- `etiquetes()` — categories i codis morfològics llegibles.
- `salut()` — comprova que el lloc respon i que l’echo de control és correcte. No crea ni esborra cursors.

`cerca`, `cerca_frase` i `cerca_patro` accepten `filtres` (`autor`, `titol`,
`any_min`/`any_max`, `tipus`, `genere`, `classtem`, `varietat`, `traduccio`).
Amb filtres, `total` és la «Quantitat filtrada» i `total_unfiltered` la
freqüència sense filtres; `filters_verified` ha de ser cert. Si no hi ha files,
el portal pot retornar un total de control (1): és `unexpected_response` amb
`filtered_empty_unverified`, no una absència. Si l'autor s'ha validat contra el
catàleg global i els filtres quadren, és `no_matches` amb
`filtered_empty_verified`. `classtem` és la classificació temàtica de les obres
no literàries: un grup sencer (`3`) o un sol subtema (`3.2`); no es combina amb
`genere` ni amb `tipus=LIT`. Els valors per a `tipus`/`genere`/`varietat` són
LIT/NLIT, A/N/P/T i les cinc varietats.

Posteriors:

- Cap eina d'exportació ni de descàrrega: l'exportació CSV i les obres
  descarregables queden fora d'abast.

### Esquema de sortida mínim

Una cerca de concordances del CTILC amb recompte verificat ha de retornar:

```json
{
  "query": {},
  "pattern_echo": "…",
  "total": 0,
  "returned": 0,
  "has_more": false,
  "search_cursor": "…",
  "next_cursor": null,
  "occurrences": [],
  "warnings": [],
  "source": "https://ctilc.iec.cat/…",
  "retrieved_at": "…",
  "citation": "CTILC (IEC), consulta feta el …"
}
```

`warnings` ha de cobrir, com a mínim: `zero_results`, `pattern_echo_unexpected`, `transport_eof`, `result_cache_miss`, `parse_partial`, `corpus_updated`.

## 9. Interpretació de dades: coses a anar amb compte

- **Mida del corpus:** 126.604.218 paraules; **102.493.057 analitzades** morfosintàcticament. La resta són noms propis, no analitzables o altres. Un zero en una cerca per lema/categoria pot ser una manca d’anotació.
- **Període:** dades des de 1832 fins a 2022; la prosa del lloc de vegades diu 1833. No és un corpus oral.
- **Creixement:** uns 5 milions de paraules l’any. Els recomptes i golden tests es mouen; registrar sempre la data i el total.
- **Dispersió:** un total alt pot concentrar-se en un autor, una obra, un gènere o una dècada. Cal mirar obres/autors únics i proporcions.
- **Col·locacions:** les xifres de la tool de col·locacions (±3) no són les mateixes que les d’adjacència. No barrejar mètriques.
- **Literal vs figuratiu:** el model ha de llegir contextos; l’MCP no ho classifica automàticament.
- **“Quotidià”:** no es pot concloure del CTILC. Caldria corpus oral i dades sociolingüístiques.

## 10. Legal, ètica i privacitat

- Ús personal/de recerca: possible, però **no hi ha una autorització explícita** a les pàgines del CTILC.
- `robots.txt` i `sitemap.xml` retornen 404; **l’absència no és permís**.
- No fer descàrregues massives; limitar el ritme (~1 req/s o menys) i cachejar.
- Contactar **`dcc@iec.cat`** abans de publicar o integrar l’MCP en un producte.
- Citar sempre el CTILC i l’IEC; no usar el logo de l’IEC ni presentar-se com a oficial.
- No redistribuir extracts extensos ni obres protegides.
- El `resultat` cachejat al servidor pot quedar accessible per ID; no hi posar consultes sensibles.
- No loguejar textos sencers de les consultes; minimitzar dades.

## 11. Qualitat i tests

- **Unitaris:** encoder (`*` literal), compilador, `01-03` expandit, `negat+opcional` rebutjat, cursor, IDs com a `string`, eco visible, zero explícit, continuació stale, antònims de sinònims, XML inesperat i `no-store`.
- **Fixtures:** 50 files, 1.000 files, 0 files, fila mal formada, `<i>`, `&#8203;`, `Forma`, `Lemes`, col·locació, dispersió, fitxa.
- **Contracte:** VCR/cassettes; CI sense xarxa.
- **Live:** opcional (`LLENGUA_LIVE=1`), amb rate limit i data; s'executen al workflow `live.yml`, no a `ci.yml`.
- **CI:** `.github/workflows/ci.yml` (ruff i `pytest` sense xarxa, Python 3.11–3.13) i `.github/workflows/live.yml` (proves en directe, dilluns).
- **Drift:** `salut` comprova una consulta de control (`00*lema=somriure&01*cg=adj:-` → 2.136 el 18/11/2026) i l’echo.
- **Golden tests:** els de `pla-mcp-ctilc-critiques.md`, no els del pla original sense corregir.

## 12. Convencions de codi i repositori

- Codis i noms tècnics en anglès; **descripcions d’eines, errors i documentació d’usuari en català**.
- Type hints i models Pydantic; evitar `Any` innecessari.
- `ruff format` / `ruff check`; `pytest`.
- No secrets al repositori; fer servir variables d’entorn (`CTILC_USER_AGENT`, `CTILC_CONTACT`, `CTILC_RATE`, `CTILC_CACHE_DIR`).
- Missatges d’error accionables: dir què ha fallat i com corregir-ho.
- No reescriure els documents de planificació sense petició explícita; les decisions noves van a la documentació del codi o a un nou document.
- Si es descobreix un canvi de protocol, actualitzar el test i el document de crítiques; no “arreglar” el test perquè passi.

## 13. Integració amb OpenCode

Configuració local prevista:

El repositori ja inclou `opencode.jsonc` amb aquesta configuració:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "servers": {
      "llengua": {
        "type": "local",
        "command": [
          "/ruta/al/projecte/.venv/bin/python",
          "-m",
          "llengua_mcp.server"
        ],
        "cwd": ".",
        "environment": {
          "LLENGUA_USER_AGENT": "llengua-mcp/0.1 (recerca; contacte)",
          "LLENGUA_DATA_DIR": "/ruta/al/projecte/data"
        },
        "timeout": { "execution": 60000 },
        "codemode": false
      }
    }
  }
}
```

Instal·lació i dades:

```sh
uv venv .venv
uv pip install --python .venv/bin/python -e .
LLENGUA_DATA_DIR=./data .venv/bin/python -m llengua_mcp.fetch_sinonims
```

- `codemode: false` exposa les eines directament i és més compatible amb models petits; Code Mode es pot activar després.
- Les eines apareixeran com `llengua_<tool>` (o `tools.llengua.<tool>` amb Code Mode).
- Instruccions d’agent recomanades:
  - consultar el CTILC per a afirmacions empíriques sobre el català;
  - dir la data, la mida del corpus i les variants provades;
  - distingir zero real de consulta invàlida;
  - no concloure “ús quotidià” a partir del CTILC;
  - citar el CTILC i l’IEC.

## 14. Definició de fet (MVP)

Proves d’acceptació del producte des d’OpenCode:

1. **Correcció:** davant «Què et sembla “Tinc que anar a casa”?», l’agent cerca a l’Optimot una fitxa sobre l’obligació, la llegeix i proposa **«He d’anar a casa»**. Explica *haver de + infinitiu* i cita la fitxa consultada.
2. **Comparació:** davant «Què et sona millor: “somriure maliciós” o “somriure de mala fe”?», consulta Optimot, ésAdir i CTILC. Al corpus cerca *somriure* com a nom en totes dues formulacions i examina els contextos. Si cal, precisa el sentit al DIEC. Recomana una formulació segons el matís, distingint la tria del model dels criteris publicats, sense donar per fet cap recompte.
3. **Alternatives:** davant «Què puc posar en lloc de “maliciós” a “un somriure maliciós”?», consulta Softcatalà i explica quines opcions conserven el sentit i quines el canvien. Cita l’entrada i presenta les alternatives com a suggeriments.

**Estat de la definició de fet:** els tres casos d’acceptació i les eines del
CTILC ja estan implementats i provats en directe (18–19/11/2026), amb 234 tests
sense xarxa i dinou proves en directe optatives (`LLENGUA_LIVE=1`). Hi ha 30
eines, incloent-hi el Corpus de consultes de l’IEC, els filtres, les obres, les
dispersions i les cerques bàsiques del CTILC. El DDLC no s’integra a través de
BDLex; l'exportació CSV i les obres descarregables queden fora
d'abast. Critèria i la cerca de noms propis del CTILC es van descartar
el 20/11/2026.

La part del CTILC es considera llesta quan:

1. `cerca_frase`, `context`, `xifres`, `etiquetes` i `salut` funcionen amb OpenCode.
2. Una consulta vàlida no retorna 500 ni un fals zero; l’echo es valida.
3. Els IDs de 64 bits es conserven com a `string`.
4. Hi ha fixtures i tests que cobreixen `*`, paginació, accents, `<>`, `()`, `formalema` i errors.
5. Hi ha README, avís legal i citació.
6. El rate limit i la cache funcionen.
7. S’ha revisat el cas “tenir foc als ulls” com a test d’acceptació: la resposta ha de ser una fitxa d’evidència, no un “N → és quotidià”.
8. Els filtres per autor, any, gènere i varietat validen l’eco i no converteixen el total de control (1) en una absència.

## 15. Enllaços

- CTILC: <https://ctilc.iec.cat/>
- BDLex: <https://bdlex.iec.cat/>
- Contacte IEC: `dcc@iec.cat`
- Pla inicial: `pla-mcp-ctilc.md`
- Revisió i correccions: `pla-mcp-ctilc-critiques.md`
