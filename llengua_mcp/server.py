"""Servidor MCP `llengua` (stdio)."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.mcpserver import MCPServer

from llengua_mcp.app import App
from llengua_mcp.config import Settings
from llengua_mcp.errors import (
    LlenguaError,
    UnexpectedResponseError,
    error_payload,
)
from llengua_mcp.http import current_meter, reset_meter, start_meter
from llengua_mcp.models import CtilcFilters, PatternElement

INSTRUCTIONS = """\
Ets un servidor de consultes sobre la llengua catalana. Combina fonts amb
autoritat diferent i no les confonguis mai:

- Optimot: dubtes gramaticals, de construcció o de registre. Cal obrir la fitxa
  amb `optimot_fitxa` abans de citar-ne el criteri. Si l'usuari dona una
  expressió concreta, prova primer el mode `frase_exacta`; si pregunta per un
  fenomen, cerca amb `fitxes` les paraules clau (p. ex. «perífrasi d'obligació»).
  Si l'usuari pregunta per un mot antic o dialectal que no surt al DIEC, prova
  `bdlex_consulta` abans de qualificar-lo: potser el recull el DCVB.
- Corpus de consultes de l'IEC: respostes curades a dubtes reals. Serveix per
  veure com s'ha resolt una qüestió semblant i per enllaçar la font que cita
  (GIEC, DIEC, Optimot). Cita la consulta; no substitueix la norma.
- DIEC: lèxic normatiu. Cita l'entrada i l'accepció; una locució pot ser dins
  de l'article d'un dels mots. No trobar-hi una forma no la fa incorrecta.
- BDLex: diccionaris històrics i dialectals (DCVB, DIEC, Fabra, obres dels
  segles XIX i XX). Per documentar mots antics o propis d'un parlar i per
  cercar per definició o exemple. És descriptiu: una forma hi pot constar i
  no ser adequada avui. Cita sempre el diccionari concret. El DDLC té un
  portal propi; no es consulta per BDLex.
- PCCD: font descriptiva de parèmies catalanes. `pccd_cerca` permet cercar
  paremiotipus i, opcionalment, variants; `pccd_fitxa` mostra variants i fonts.
  La datació més antiga del recull no és necessàriament la primera documentació
  absoluta i els recomptes de fitxa no indiquen freqüència d'ús.
- Conjugador de Softcatalà: `conjugador_consulta` retorna les formes verbals i
  les marques territorials de la fitxa. Les cel·les buides no són necessàriament
  formes incorrectes o inexistents; conserva les notes i els límits de la font.
- ésAdir: estil de la CCMA, pronunciació i noms propis. No és la norma de l'IEC.
- OIEC: ortografia normativa (apòstrofs, guionets, accents, dièresi). Cita
  sempre el codi d'apartat i el títol de la secció.
- Gramàtiques: per explicar una regla gramatical, `gramatica_cerca` i
  `gramatica_text`. La GBU és la consulta d'ús; la GEIEC, la versió en línia;
  la GIEC, la descripció exhaustiva. Cita el codi i el títol.
- CTILC: ús escrit i contextos. Un total positiu només demostra atestació; un
  zero no demostra que una forma no existeixi. No en dedueixis «ús quotidià».
  La dispersió cronològica serveix per dir en quins trams apareix més, amb
  ocurrències i taxa per milió; amb pocs testimonis, parla de concentració
  observada, no de tendència. La dispersió dialectal dona la distribució per
  varietat: compara `per_million`, no els recomptes absoluts, perquè els
  subcorpus tenen mides molt diferents. La dispersió general creua any,
  varietat, traducció, tipus, gènere i tema; `genere` i `classificacio` tenen
  totals propis i no sumen el total general. Les col·locacions indiquen quines
  paraules hi coapareixen dins d'una finestra de mots; les seves xifres no es
  poden comparar amb els recomptes de seqüència exacta. Per a una forma o un
  lema, `cerca_forma` i `cerca_lema` donen el desglossament de formes i
  morfologia; `cerca` dona concordances amb filtres. Les metadades de les obres
  (any, gènere, varietat) es consulten amb `obres`; si un cognom dona diversos
  autors, cal triar-ne un amb `autor_id`.
- Softcatalà: sinònims. Són propostes de significat; tria les que encaixen en
  la frase i explica'n el matís.
- Jané (IEC): diccionari de sinònims amb accepcions numerades. Si una paraula
  té diversos sentits, tria el número que encaixa en la frase abans de
  substituir res; `mode="general"` cerca dins les llistes de sinònims i
  `mode="funcio"` per funció sintàctica. Complementa Softcatalà: no barregis
  les dades dels dos diccionaris en una sola llista.

Comença amb la resposta pràctica: la forma recomanada o la diferència de
matís. Després desplega l'evidència pertinent que ja has obtingut. Organitza-la
per fonts si n'hi ha més d'una i enllaça cada criteri o dada amb la font que
l'avala. Omet els apartats per als quals no hi hagi dades pertinents.

- Explica per què cada forma funciona o no en el context. Distingeix una forma
  no normativa d'una forma correcta amb un altre sentit o registre. Si una
  alternativa només millora l'estil, presenta-la com a opció d'estil.
- Dona les alternatives pertinents en la frase i explica quines conserven el
  sentit i quines el canvien. Inclou les notes d'ús que hi ajudin i mantén els
  antònims separats dels sinònims.
- Si la font ho documenta, explica l'etimologia, l'evolució o les variants
  històriques i dialectals; cita la font concreta. No confonguis el testimoni
  més antic obtingut al corpus amb la primera documentació d'una forma.
- Per al CTILC, mostra els recomptes verificats de cada variant comparable i
  explica què es veu a les concordances pertinents que has rebut. Acompanya
  les citacions breus d'autor, obra i any quan constin. Distingeix el total
  verificat de les concordances mostrades (p. ex. «5 concordances mostrades
  de 32 ocurrències»). Si ja tens dispersió validada, explica on es concentra
  l'ús i compara taxes per milió entre subcorpus. La freqüència al CTILC no
  estableix la correcció ni demostra l'ús oral o quotidià.
- Indica les discrepàncies, els resultats parcials i els errors que afectin
  la conclusió. Una absència verificada és una absència al corpus; un resultat
  no verificat no és un zero. Si una font no respon o no tracta el cas, no li
  atribueixis cap criteri. Separa l'evidència de la teva recomanació.

No facis consultes addicionals, no paginis i no augmentis els límits només
per omplir la resposta. No inventis detalls absents ni aboquis dades
irrellevants o repetides.

No revisis paràgrafs sencers per iniciativa pròpia: l'usuari fa consultes
puntuals sobre una paraula, una expressió o una frase.
"""

_app: App | None = None
_app_lock = asyncio.Lock()


async def get_app() -> App:
    global _app
    if _app is None:
        async with _app_lock:
            if _app is None:
                _app = App(Settings.from_env())
    return _app


async def _warm_indexes(app: App) -> None:
    """Carrega en segon pla els índexs locals que no depenen de la xarxa."""

    try:
        await app.softcatala.warm()
    except Exception:  # noqa: BLE001 - si falten dades, l'eina ho explica en consultar-se
        return


@asynccontextmanager
async def _lifespan(_server: MCPServer):
    global _app
    app = await get_app()
    warm = asyncio.create_task(_warm_indexes(app))
    try:
        yield {}
    finally:
        async with _app_lock:
            if _app is app:
                _app = None
        try:
            warm.cancel()
            await asyncio.gather(warm, return_exceptions=True)
        finally:
            await app.aclose()


async def _call(source: str, awaitable) -> dict[str, Any]:
    token = start_meter()
    try:
        try:
            payload = await awaitable
        except LlenguaError as exc:
            payload = error_payload(exc, source=source or exc.source)
        except Exception as exc:  # noqa: BLE001 - l'agent ha de rebre un error útil
            payload = error_payload(
                UnexpectedResponseError(
                    "Error inesperat en consultar la font.",
                    hint=f"{type(exc).__name__}: {exc}",
                    source=source,
                ),
                source=source,
            )
        meter = current_meter()
        if meter is not None:
            payload["timing"] = meter.payload()
        return payload
    finally:
        reset_meter(token)


mcp = MCPServer("llengua", instructions=INSTRUCTIONS, version="0.1.0", lifespan=_lifespan)


@mcp.tool()
async def optimot_cerca(
    consulta: str,
    mode: str = "fitxes",
    limit: int = 5,
) -> dict[str, Any]:
    """Cerca referències lingüístiques a l'Optimot.

    Args:
        consulta: Paraula, expressió o frase curta (per exemple «tindre o tenir»).
        mode: `fitxes` (dubtes de construcció, gramàtica o registre), `basica`
            (cerca lèxica àmplia), `frase_exacta`, `castella_catala` o `verbs`.
        limit: Nombre màxim de candidats (1-20).

    Retorna candidats amb títol, font original, fragment i `detail_ref`. Per
    llegir una fitxa, passa el `detail_ref` a `optimot_fitxa`. El recompte de
    resultats no és una freqüència d'ús. Els resultats s'ordenen per coincidència
    amb la consulta (`relevance`); si el mode és poc precís, la resposta inclou
    `suggested_mode` amb una cerca alternativa. Per a una expressió concreta
    (per exemple «tenir que»), prova el mode `frase_exacta`; per a un fenomen,
    cerca amb `fitxes` paraules com «perífrasi d'obligació» o «haver de».
    """
    app = await get_app()
    return await _call(
        "https://aplicacions.llengua.gencat.cat/llc/AppJava/index.html",
        app.optimot.cerca(consulta, mode=mode, limit=max(1, min(limit, 20))),
    )


@mcp.tool()
async def optimot_fitxa(ref: str) -> dict[str, Any]:
    """Obre una fitxa de l'Optimot a partir d'un `detail_ref`.

    Retorna títol, número de fitxa, data de versió, seccions de resposta i
    relacionades. Cal citar la font original i la versió quan constin.
    """
    app = await get_app()
    return await _call(
        "https://aplicacions.llengua.gencat.cat/llc/AppJava/index.html",
        app.optimot.fitxa(ref),
    )


@mcp.tool()
async def consultes_iec(
    cerca: str | None = None,
    tema: str | None = None,
    camp: str = "tot",
    limit: int = 5,
    offset: int = 0,
) -> dict[str, Any]:
    """Cerca al Corpus de consultes lingüístiques de l'IEC.

    Són respostes curades a dubtes reals, amb el tema i els enllaços a la font
    que citen (GIEC, DIEC, Optimot...). Serveix per veure com s'ha resolt una
    qüestió semblant; no substitueix la norma ni la fitxa d'una altra font.

    Args:
        cerca: Text lliure (per exemple «tenir que»).
        tema: Filtra per tema: Fonètica, Lèxic, Morfologia, Onomàstica,
            Ortografia, Sintaxi o Altres.
        camp: `tot` (pregunta i resposta) o `pregunta` (només la pregunta).
        limit: Nombre màxim de consultes (1-20).
        offset: Posició inicial per paginar; usa `next_offset`.

    Cal indicar `cerca` o `tema`. Cita la consulta i enllaça la font.
    """
    app = await get_app()
    return await _call(
        "https://consultes-linguistiques.iec.cat/cerca-general/",
        app.consultes.cerca(
            cerca,
            tema=tema,
            camp=camp,
            limit=limit,
            offset=offset,
        ),
    )


@mcp.tool()
async def diec_consulta(paraula: str, limit: int = 3, max_senses: int = 20) -> dict[str, Any]:
    """Consulta el DIEC i retorna les accepcions de l'entrada.

    Serveix per validar el lèxic i, sobretot, per identificar l'accepció
    aplicable. Una locució pot figurar dins de l'article d'un dels mots. Si no
    hi ha entrada, això no converteix la forma en incorrecta.

    Args:
        paraula: Mot o locució curta.
        limit: Nombre màxim d'entrades (1-5).
        max_senses: Nombre màxim d'accepcions per entrada (1-50). Si l'article
            és llarg, `senses_truncated` indica que cal apujar-lo.
    """
    app = await get_app()
    return await _call(
        "https://dlc.iec.cat/Results",
        app.diec.consulta(paraula, limit=limit, max_senses=max_senses),
    )


@mcp.tool()
async def conjugador_consulta(
    verb: str,
    mode: str | None = None,
    temps: str | None = None,
    persona: str | None = None,
) -> dict[str, Any]:
    """Consulta la conjugació d'un verb al conjugador de Softcatalà.

    Args:
        verb: Infinitiu, també pronominal (p. ex. `abstenir-se`).
        mode: Opcional: `indicatiu`, `subjuntiu`, `imperatiu` o `formes no personals`.
        temps: Opcional: nom del temps tal com apareix a la fitxa (p. ex. `Present`).
        persona: Opcional: `jo`, `tu`, `ell`, `ella`, `vostè`, `nosaltres`,
            `vosaltres`, `vós`, `ells`, `elles` o `vostès`. També admet `1sg`–`3pl`.

    Les marques de varietat es retornen amb cada forma. Els buits de la taula
    es distingeixen de les formes no aplicables; no són un judici de correcció.
    """
    app = await get_app()
    return await _call(
        "https://www.softcatala.org/conjugador-de-verbs/",
        app.conjugador.consulta(verb, mode=mode, temps=temps, persona=persona),
    )


@mcp.tool()
async def pccd_cerca(
    consulta: str,
    inclou_variants: bool = False,
    condicio: str = "conté",
    limit: int = 10,
) -> dict[str, Any]:
    """Cerca parèmies a la PCCD.

    Args:
        consulta: Paremiotipus o fragment de la parèmia.
        inclou_variants: Amplia la cerca a les variants formals.
        condicio: `conté` (per defecte) o `coincident`.
        limit: Màxim de resultats retornats (1-50).
    """
    app = await get_app()
    return await _call(
        "https://pccd.dites.cat/",
        app.pccd.cerca(consulta, inclou_variants=inclou_variants, condicio=condicio, limit=limit),
    )


@mcp.tool()
async def pccd_fitxa(entrada: str, limit: int = 20) -> dict[str, Any]:
    """Obre una fitxa de la PCCD per títol o URL retornat per `pccd_cerca`.

    Retorna els recomptes de la fitxa, les variants disponibles, la datació
    més antiga del recull i les citacions de les fonts. Per controlar la mida
    de la resposta, `limit` restringeix les variants retornades (1-50), amb
    fins a cinc citacions per variant.
    """
    app = await get_app()
    return await _call(
        "https://pccd.dites.cat/",
        app.pccd.fitxa(entrada, limit=limit),
    )


@mcp.tool()
async def esadir_consulta(
    termes: str,
    seccio: str | None = None,
    condicio: str = "coincident",
    limit: int = 5,
) -> dict[str, Any]:
    """Cerca entrades i criteris d'estil a ésAdir (CCMA).

    Args:
        termes: Mot, expressió, topònim o nom propi.
        seccio: Opcional: `lexic`, `gramatica`, `toponim`, `nompropi`,
            `convencions`, `traduccio`, `altresllengues` o `enllac`.
        condicio: `coincident`, `aproximat`, `comença per`, `conté` o `acaba en`.
        limit: Nombre màxim de resultats.

    La cerca exacta pot fallar en entrades multiparaula i retornar títols de
    filmoteca. Si apareix `no_entry_results`, prova `esadir_fitxa` amb el
    `suggested_fitxa` abans de concloure que no hi ha entrada. ésAdir és estil
    de la CCMA, no la norma de l'IEC.
    """
    app = await get_app()
    return await _call(
        "https://www.esadir.cat/cerca/resavancada",
        app.esadir.consulta(termes, seccio=seccio, condicio=condicio, limit=limit),
    )


@mcp.tool()
async def esadir_fitxa(entrada: str) -> dict[str, Any]:
    """Obre una fitxa d'ésAdir per URL, slug o títol.

    Retorna etiquetes d'ús, pronunciació AFI, definicions, exemples, enllaços
    relacionats i URL d'àudio. L'àudio no es descarrega perquè `/back/` està
    bloquejat a robots.txt.
    """
    app = await get_app()
    return await _call("https://www.esadir.cat", app.esadir.fitxa(entrada))


@mcp.tool()
async def bdlex_consulta(
    paraula: str | None = None,
    definicio: str | None = None,
    exemple: str | None = None,
    text_lliure: str | None = None,
    dicts: list[str] | None = None,
    coincidencia: str = "exact",
    limit: int = 5,
    max_senses: int = 6,
) -> dict[str, Any]:
    """Consulta BDLex (IEC), la plataforma de diccionaris històrics i dialectals.

    Inclou el DCVB, el DIEC actual i diverses obres dels segles XIX i XX.
    Es pot cercar per entrada (`paraula`), per paraules de la definició
    (`definicio`), per un exemple (`exemple`) o per text lliure
    (`text_lliure`). Retorna entrades estructurades amb definicions, exemples,
    variants, etimologia, fonètica i etiquetes d'àrea. Per defecte consulta
    `DCVB` i `DIEe`. `dicts` substitueix aquesta selecció: els codis admesos
    són `DCVB`, `DIEe` (DIEC2 en línia), `DIE2` (DIEC2 de 2007), `DIEC`
    (DIEC1 de 1995), `DGLC`, `DGFP`, `DPCV`, `DGMG`, `DMCT`, `NDMA`,
    `DVCE`, `DMCF`, `DLCL`, `DEBJ` i `DMFC`. El DDLC no forma part de BDLex:
    té un portal propi (https://dcc.iec.cat/ddlcI/scripts/index.html).
    `max_senses` limita les accepcions per entrada (màxim 15).

    És una font descriptiva i històrica: una forma pot constar-hi i no ser
    adequada avui, i una absència no la converteix en incorrecta. Cita sempre
    el diccionari concret.
    """
    app = await get_app()
    return await _call(
        "https://bdlex.iec.cat/",
        app.bdlex.consulta(
            paraula,
            definicio=definicio,
            exemple=exemple,
            text_lliure=text_lliure,
            dicts=dicts,
            coincidencia=coincidencia,
            limit=limit,
            max_senses=max_senses,
        ),
    )


@mcp.tool()
async def oiec_cerca(
    paraula: str,
    coincidencia: str = "contains",
) -> dict[str, Any]:
    """Cerca a l'Ortografia catalana (OIEC) de l'IEC.

    Serveix per explicar regles d'ortografia que afecten molts mots: apòstrofs,
    guionets, accents, dièresi, majúscules, pronoms febles... Retorna fins a
    cinc apartats amb el codi (`codi_text`), el títol, un fragment que conté la
    paraula i l'enllaç. Per llegir un apartat sencer, passa el codi a
    `oiec_text`. L'OIEC és la referència normativa de l'ortografia: cita
    sempre el codi i el títol de la secció.
    """
    app = await get_app()
    return await _call(
        "https://api-oiec.iec.cat",
        app.oiec.cerca(paraula, coincidencia=coincidencia),
    )


@mcp.tool()
async def oiec_text(codi: str) -> dict[str, Any]:
    """Llegeix un apartat de l'Ortografia catalana (OIEC) pel seu codi.

    Usa el `codi_text` retornat per `oiec_cerca` (per exemple `4.1.2b`).
    Retorna el text complet de l'apartat, net d'etiquetes, amb els codis
    d'apartat anterior i següent per navegar-hi.
    """
    app = await get_app()
    return await _call("https://api-oiec.iec.cat", app.oiec.text(codi))


@mcp.tool()
async def gramatica_cerca(
    paraula: str,
    font: str = "gbu",
    coincidencia: str = "contains",
) -> dict[str, Any]:
    """Cerca a les gramàtiques de l'IEC: GBU, GEIEC o GIEC.

    Serveix per explicar una regla gramatical: perífrasis, pronoms febles,
    concordança, subordinades... Retorna fins a cinc apartats amb el codi
    (`codi_text`), el títol, un fragment que conté la paraula i l'enllaç. Si
    hi ha nodes sense text llegible, l'estat és `partial`, no `no_results`.

    Args:
        paraula: Paraula o fenomen gramatical (per exemple «perífrasi verbal»).
        font: `gbu` (gramàtica bàsica i d'ús, la consulta adequada per a dubtes
            d'ús), `geiec` (versió en línia) o `giec` (descripció exhaustiva).
        coincidencia: `contains` (En qualsevol posició) o `exact` (Coincident).

    Per llegir un apartat sencer, passa el codi a `gramatica_text`.
    """
    app = await get_app()
    return await _call(
        "https://api-gbu.iec.cat/api",
        app.gramatiques.cerca(paraula, font=font, coincidencia=coincidencia),
    )


@mcp.tool()
async def gramatica_text(codi: str, font: str = "gbu") -> dict[str, Any]:
    """Llegeix un apartat d'una gramàtica de l'IEC pel seu codi.

    Usa el `codi_text` retornat per `gramatica_cerca` (per exemple `28.1`).
    Retorna el text complet de l'apartat, net d'etiquetes, amb l'enllaç a la
    secció al portal corresponent. Es valida que el codi retornat coincideixi
    amb el sol·licitat; els codis que només són títols donen error.
    """
    app = await get_app()
    return await _call(
        "https://api-gbu.iec.cat/api",
        app.gramatiques.text(codi, font=font),
    )


@mcp.tool()
async def cerca_sinonims(
    paraula: str,
    context: str | None = None,
    limit: int = 15,
) -> dict[str, Any]:
    """Cerca sinònims al diccionari de Softcatalà (dades locals, CC BY 4.0).

    Cerca la paraula o la locució sencera. Distingeix els accents: si la forma
    exacta no hi és i només es troba una coincidència sense accents, ho indica
    amb `match: "accent_insensitive"` i l'avís `accent_insensitive_match`, i no
    barreja els grups de dues formes que només difereixen en el diacrític. Si no
    hi ha entrada per a una expressió, no en busca els components per separat,
    perquè els sinònims d'una part no equivalen als de l'expressió. Si dones un
    `context`, les agrupacions que hi coincideixen (etiqueta de sentit o formes
    que hi surten) es retornen primer; el diccionari no porta definicions, així
    que el model ha de triar les opcions que hi encaixen i explicar-ne el matís.
    """
    app = await get_app()
    return await _call(
        "https://www.softcatala.org/diccionari-de-sinonims/",
        app.softcatala.cerca_async(
            paraula,
            context=context,
            limit=limit,
        ),
    )


@mcp.tool()
async def jane_cerca(
    paraula: str,
    mode: str = "lema",
    funcio: str | None = None,
    limit: int = 5,
    offset: int = 0,
) -> dict[str, Any]:
    """Cerca al diccionari de sinònims d'Albert Jané (IEC).

    Torna les entrades amb les accepcions numerades (`1.`, `2.`), cosa que
    permet triar el sentit que encaixa en la frase. `mode` pot ser `lema`
    (començament del lema), `general` (el mot també dins les llistes de
    sinònims) o `funcio` (per funció sintàctica; llavors cal `funcio`, per
    exemple «nominal» o «adjectiva»). Cada resultat porta també els femenins,
    les notes d'ús i els enllaços al DIEC, DDLC, CTILC, BDLex, DCVB, CiT i
    TERMCAT. Els sinònims són propostes de significat, no equivalents exactes.
    """
    app = await get_app()
    return await _call(
        "https://sinonims.iec.cat/",
        app.jane.cerca(
            paraula,
            mode=mode,
            funcio=funcio,
            limit=limit,
            offset=offset,
        ),
    )


@mcp.tool()
async def cerca_frase(
    frase: str,
    variants: list[str] | None = None,
    limit: int = 10,
    filtres: CtilcFilters | None = None,
) -> dict[str, Any]:
    """Cerca una seqüència contigua de formes al CTILC.

    Cada paraula és un token. No incloguis puntuació externa: el corpus
    tokenitza per formes. Les variants són frases completes alternatives
    (per exemple, «tenir foc al ulls» i «tenir foc als ulls»); es consulten per
    separat i els totals no se sumen. Retorna contextos, total verificat, eco
    del patró, `search_cursor` (per a eines com la dispersió) i `next_cursor`
    per continuar. Un zero només és una absència en aquest corpus, no una prova
    que la forma no existeixi.

    `filtres` permet restringir per autor, títol, anys, tipus (LIT/NLIT),
    gènere (A/N/P/T), varietat i traducció. Amb filtres, un resultat sense
    files no es presenta com una absència: el portal pot retornar un total de
    control.
    """
    app = await get_app()
    return await _call(
        "https://ctilc.iec.cat/scripts/CTILCQConc_Coocur2.asp",
        app.ctilc.search_phrase(frase, variants=variants, limit=limit, filters=filtres),
    )


@mcp.tool()
async def cerca(
    lema: str | None = None,
    forma: str | None = None,
    categoria: str | None = None,
    limit: int = 10,
    filtres: CtilcFilters | None = None,
) -> dict[str, Any]:
    """Cerca simple al CTILC per lema o per forma.

    `lema` cerca totes les formes del lema i admet una `categoria` (`subst`,
    `V`, `adj`...). `forma` cerca una sola forma gràfica. No es poden combinar
    totes dues. Retorna els mateixos contextos verificats que `cerca_frase`,
    amb `pattern_echo`, total, `search_cursor` i `next_cursor`. `filtres`
    funciona com a `cerca_frase`.
    """
    app = await get_app()
    return await _call(
        "https://ctilc.iec.cat/scripts/CTILCQConc_Coocur2.asp",
        app.ctilc.cerca(
            lema=lema,
            forma=forma,
            categoria=categoria,
            limit=limit,
            filters=filtres,
        ),
    )


@mcp.tool()
async def cerca_forma(
    forma: str,
    mode: str = "coincident",
    cg: str | None = None,
    limit: int = 10,
    offset: int = 0,
) -> dict[str, Any]:
    """Concordança bàsica d'una forma al CTILC (`Formes2`).

    A diferència de `cerca`, aquesta eina dona el desglossament de les formes
    trobades amb la categoria i la morfologia, a més d'una pàgina
    d'ocurrències. `mode` pot ser `coincident`, `comença per`, `acaba en`,
    `conté`, `no comença per`, `no acaba en` o `no conté`. Els modes negatius
    requereixen `cg` (p. ex. `I` per a interjeccions); tria una categoria
    concreta perquè el portal retorna tot el desglossament, encara que `limit`
    sigui baix. `cg` restringeix per categoria o codi morfològic.
    Per continuar, passa `offset`.
    """
    app = await get_app()
    return await _call(
        "https://ctilc.iec.cat/scripts/CTILCQConc_Formes2.asp",
        app.ctilc.cerca_forma(
            forma,
            mode=mode,
            cg=cg,
            limit=limit,
            offset=offset,
        ),
    )


@mcp.tool()
async def cerca_lema(
    lema: str,
    mode: str = "coincident",
    cg: str | None = None,
    limit: int = 10,
    offset: int = 0,
) -> dict[str, Any]:
    """Concordança bàsica d'un lema al CTILC (`FormesLema2`).

    Retorna la freqüència total, les formes del lema amb categoria i morfologia
    (útil per construir un `formalema`) i una pàgina d'ocurrències. `mode` pot
    ser `coincident`, `comença per`, `acaba en`, `conté`, `no comença per`,
    `no acaba en` o `no conté`. Els modes negatius requereixen `cg` (p. ex. `I`
    per a interjeccions) i s'apliquen al lema, no a les seves formes. Tria una
    categoria concreta: `limit` només redueix la pàgina d'ocurrències, no el
    desglossament. Per continuar, passa `offset`.
    """
    app = await get_app()
    return await _call(
        "https://ctilc.iec.cat/scripts/CTILCQConc_FormesLema2.asp",
        app.ctilc.cerca_lema(
            lema,
            mode=mode,
            cg=cg,
            limit=limit,
            offset=offset,
        ),
    )


@mcp.tool()
async def cerca_patro(
    elements: list[PatternElement],
    limit: int = 10,
    filtres: CtilcFilters | None = None,
) -> dict[str, Any]:
    """Cerca un patró avançat al CTILC (combinacions).

    Cada element pot ser `lema` (amb `category` opcional), `forma` (una sola
    paraula), `formalema`, `cg` (categoria i morfologia) o `qualsevol`. Es pot
    marcar `optional` o `negated`, però no tots dos alhora. Per a un nom amb
    adjectiu: lema «somriure» amb categoria «subst» + cg «adj».

    Retorna el patró executat, el total verificat i contextos. `optional` en
    diversos elements seguits emula un interval, però no s'ha de presentar com
    una equivalència de rangs sense controls positius. `filtres` funciona com a
    `cerca_frase`.
    """
    app = await get_app()
    return await _call(
        "https://ctilc.iec.cat/scripts/CTILCQConc_Coocur2.asp",
        app.ctilc.search_pattern(elements, limit=limit, filters=filtres),
    )


@mcp.tool()
async def continuar_cerca(cursor: str, limit: int | None = None) -> dict[str, Any]:
    """Continua una cerca del CTILC amb el `next_cursor` retornat.

    El cursor és local i caduca. Si el resultat remot ha canviat o ha caducat,
    retorna `stale_search`: torna a executar la cerca original en lloc de
    barrejar pàgines de resultats diferents.
    """
    app = await get_app()
    return await _call(
        "https://ctilc.iec.cat/scripts/CTILCQConc_Coocur2.asp",
        app.ctilc.continue_search(cursor, limit=limit),
    )


@mcp.tool()
async def dispersio_cronologica(cursor: str) -> dict[str, Any]:
    """Retorna la dispersió cronològica d'una cerca del CTILC.

    Passa el `search_cursor` d'una cerca concreta (o el `next_cursor`): la
    distribució només és vàlida vinculada a aquella consulta. Retorna per tram
    `from_year`, `to_year`, `hits`, `corpus_units` i `per_million` (ocurrències
    per milió de paraules, derivades dels enters), i destaca els pics absolut i
    relatiu.

    Les dades es validen: si el patró de la pàgina no és el de la cerca o la
    suma dels trams no coincideix amb el total, `data_valid` és fals, `periods`
    queda buit i les dades sense validar són a `unvalidated`; no s'han de
    presentar com a resultats. Amb pocs testimonis, parla de concentració
    observada, no de tendència.
    """
    app = await get_app()
    return await _call(
        "https://ctilc.iec.cat/scripts/CTILCQDispersionsCron.asp",
        app.ctilc.dispersio_cronologica(cursor),
    )


@mcp.tool()
async def dispersio_dialectal(cursor: str) -> dict[str, Any]:
    """Retorna la distribució dialectal d'una cerca del CTILC.

    Passa el `search_cursor` (o el `next_cursor`) d'una cerca concreta. Retorna
    per varietat les ocurrències de la cerca (`query_hits`), les del corpus
    (`corpus_hits`), la taxa per milió de paraules (`per_million`) i el
    percentatge sobre la cerca (`share_of_query`). La varietat és la de l'obra,
    no la del parlant: el corpus és escrit.

    Per comparar varietats de mides molt diferents, fes servir `per_million`,
    no els recomptes absoluts. Un zero pot ser una mancança del corpus. Si el
    patró o els totals no quadren, `data_valid` és fals, `varieties` queda buit
    i les dades sense validar són a `unvalidated`.
    """
    app = await get_app()
    return await _call(
        "https://ctilc.iec.cat/scripts/CTILCQDispersionsDial.asp",
        app.ctilc.dispersio_dialectal(cursor),
    )


@mcp.tool()
async def dispersio_general(cursor: str) -> dict[str, Any]:
    """Retorna la dispersió general d'una cerca del CTILC.

    Passa el `search_cursor` (o el `next_cursor`) d'una cerca concreta. Retorna
    la distribució per any, varietat, traducció, tipus, gènere literari i
    classificació temàtica, amb `query_hits`, `corpus_hits`, `per_million` i
    `share_of_query` per grup.

    Cada atribut té el seu propi total: `genere` cobreix només les obres
    literàries i `classificacio` les no literàries. Per comparar grups de mides
    diferents, fes servir `per_million`, no els recomptes absoluts. Si el patró
    o els totals no quadren, `data_valid` és fals, `attributes` queda buit i les
    dades sense validar són a `unvalidated`.
    """
    app = await get_app()
    return await _call(
        "https://ctilc.iec.cat/scripts/CTILCQDispersions.asp",
        app.ctilc.dispersio_general(cursor),
    )


@mcp.tool()
async def collocacions(
    lema: str,
    radi: int = 3,
    freq_min: int = 5,
    limit: int = 5,
) -> dict[str, Any]:
    """Col·locacions d'un lema al CTILC, agrupades per categoria gramatical.

    Serveix per saber quines paraules solen aparèixer a prop d'un lema: per a
    «somriure» retorna quins noms, adjectius o verbs hi coapareixen més.
    Retorna per categoria els lemes amb freqüència de coaparició; `rows` és el
    nombre de files disponibles abans de retallar-les a `limit` i `altres`
    recull els noms propis. Cal que `lema_echo_verified` sigui cert: si és
    fals, les dades no són del lema demanat.

    Args:
        lema: Un sol lema, sense espais (per exemple «somriure»).
        radi: Finestra de coaparició en mots a cada costat (0-5, per defecte 3).
        freq_min: Freqüència mínima de coaparició (per defecte 5).
        limit: Màxim de lemes per categoria (1-10).

    Important: les xifres són freqüències de **coaparició dins d'una finestra**,
    no d'adjacència. No es poden comparar directament amb els totals de
    `cerca_frase` o `cerca_patro`, que compten seqüències exactes.
    """
    app = await get_app()
    return await _call(
        "https://ctilc.iec.cat/scripts/CTILCQCol_LemesAgrup2.asp",
        app.ctilc.collocacions(
            lema,
            radi=radi,
            freq_min=freq_min,
            limit=limit,
        ),
    )


@mcp.tool()
async def collocacions_forma(
    forma: str,
    radi: int = 3,
    freq_min: int = 5,
    limit: int = 5,
) -> dict[str, Any]:
    """Col·locacions d'una forma concreta al CTILC, agrupades per categoria.

    Serveix per separar lectures que el lema barreja: el lema «somriure» ajunta
    el nom i el verb, mentre que amb «somriures» o «somrigué» s'aïlla una sola
    forma. Cada item porta, a més del lema, la `info_mutua` (informació mútua,
    el criteri d'ordenació del portal), el `freq` de coaparició, la `distancia`
    mitjana, la `varianca` i la `freq_lema`. Cal que `forma_echo_verified`
    sigui cert: si és fals, les dades no són de la forma demanada.

    Args:
        forma: Una sola forma, sense espais (per exemple «somriures»).
        radi: Finestra de coaparició en mots a cada costat (0-5, per defecte 3).
        freq_min: Freqüència mínima de coaparició (per defecte 5).
        limit: Màxim de lemes per categoria (1-10).

    Important: les xifres són coaparicions dins d'una finestra, no adjacència,
    i no es poden comparar amb els totals de `cerca_frase` o `cerca_patro`. La
    informació mútua amb freqüències baixes és inestable.
    """
    app = await get_app()
    return await _call(
        "https://ctilc.iec.cat/scripts/CTILCQCol_FormesAgrup2.asp",
        app.ctilc.collocacions_forma(
            forma,
            radi=radi,
            freq_min=freq_min,
            limit=limit,
        ),
    )


@mcp.tool()
async def filtres_disponibles(
    cursor: str,
    tipus: str = "autors",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    """Llista els valors disponibles d'un filtre del CTILC.

    Passa el `search_cursor` d'una cerca. Retorna els autors, els títols o els
    temes (`classtem`) que apareixen en aquell resultat, amb el recompte
    d'ocurrències de cadascun. Serveix per triar valors vàlids abans de
    filtrar; un valor inventat pot donar un resultat sense files que no és una
    absència verificable.

    Args:
        cursor: `search_cursor` d'una cerca.
        tipus: `autors`, `titols` o `temes`.
        limit: Nombre màxim de valors (1-100).
        offset: Posició inicial; usa `next_offset`.
    """
    app = await get_app()
    return await _call(
        "https://ctilc.iec.cat/scripts/CTILCQConcFiltObra_filtres.asp",
        app.ctilc.filtres_disponibles(
            cursor,
            tipus=tipus,
            limit=limit,
            offset=offset,
        ),
    )


@mcp.tool()
async def obres(
    autor: str | None = None,
    titol: str | None = None,
    autor_id: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Consulta les obres del CTILC per autor o per títol.

    Retorna les metadades de cada obra: autor, títol, any, tipus, gènere,
    classificació temàtica, traducció i varietat. Serveix per citar una obra
    amb propietat i per comprovar els valors dels filtres.

    Si la cerca per autor retorna més d'un candidat, la resposta té
    `status: "ambiguous_author"` i una llista `authors`; torna a cridar l'eina
    amb `autor_id` per triar-ne un. `autor` i `titol` no es poden combinar.

    Args:
        autor: Cognom o començament del cognom (per exemple «Sagarra»).
        titol: Títol sencer o un fragment (per exemple «vida»).
        autor_id: Identificador d'autor retornat per una resposta amb diversos
            candidats.
        limit: Nombre màxim d'obres (1-100).
        offset: Posició inicial; usa `next_offset`.
    """
    app = await get_app()
    return await _call(
        "https://ctilc.iec.cat/scripts/CTILCCorpus_Aut1.asp",
        app.ctilc.obres(
            autor=autor,
            titol=titol,
            autor_id=autor_id,
            limit=limit,
            offset=offset,
        ),
    )


@mcp.tool()
async def context(occurrence_id: str, obra: str | None = None) -> dict[str, Any]:
    """Obre la fitxa de localització d'una ocurrència del CTILC.

    Retorna metadades de l'obra (amb l'ID canònic `work.id`), la posició de
    l'ocurrència, el context de ±50 posicions i el paràgraf. El paràmetre `obra`
    de la URL no és l'ID bibliogràfic: l'ID canònic es llegeix de la fitxa.
    """
    app = await get_app()
    return await _call(
        "https://ctilc.iec.cat/scripts/CTILCQFitxaLocalitzacio.asp",
        app.ctilc.context(occurrence_id, obra=obra),
    )


@mcp.tool()
async def xifres() -> dict[str, Any]:
    """Retorna la mida i la cobertura del CTILC, amb períodes.

    El total inclou paraules analitzades, noms propis, no analitzables i altres.
    Serveix per contextualitzar un recompte i per calcular taxes per milió.
    """
    app = await get_app()
    return await _call("https://ctilc.iec.cat/scripts/CTILCQDadesNum.asp", app.ctilc.xifres())


@mcp.tool()
async def etiquetes() -> dict[str, Any]:
    """Retorna les categories i els codis morfològics llegibles del CTILC.

    És un subconjunt documentat; si una etiqueta no hi apareix, cal consultar
    el formulari del CTILC. No inventis el significat d'un codi desconegut.
    """
    app = await get_app()

    async def local() -> dict[str, Any]:
        return app.ctilc.etiquetes()

    return await _call("https://ctilc.iec.cat/", local())


@mcp.tool()
async def salut() -> dict[str, Any]:
    """Comprova que el CTILC respon i que l'eco de control és correcte.

    Fa una consulta coneguda (`somriure` + adjectiu) i compara el total amb el
    de referència del 18/11/2026. Una diferència de total pot ser un canvi
    legítim del corpus; un eco incorrecte o un error de transport sí que és
    un problema de protocol. No cal invocar-ho abans de cada cerca. No crea ni
    esborra cursors de l'usuari.
    """
    app = await get_app()
    return await _call("https://ctilc.iec.cat/scripts/CTILCQConc_Coocur2.asp", app.ctilc.salut())


def main() -> None:
    """Punt d'entrada per a `python -m llengua_mcp.server` i l'executable."""

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
