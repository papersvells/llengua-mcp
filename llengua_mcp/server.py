"""Servidor MCP `llengua` (stdio)."""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.server.mcpserver import MCPServer

from llengua_mcp.app import App
from llengua_mcp.config import Settings
from llengua_mcp.errors import (
    LlenguaError,
    UnexpectedResponseError,
    error_payload,
)
from llengua_mcp.models import PatternElement

INSTRUCTIONS = """\
Ets un servidor de consultes sobre la llengua catalana. Combina fonts amb
autoritat diferent i no les confonguis mai:

- Optimot: dubtes gramaticals, de construcció o de registre. Cal obrir la fitxa
  amb `optimot_fitxa` abans de citar-ne el criteri. Si l'usuari dona una
  expressió concreta, prova primer el mode `frase_exacta`; si pregunta per un
  fenomen, cerca amb `fitxes` les paraules clau (p. ex. «perífrasi d'obligació»).
  Si l'usuari pregunta per un mot antic o dialectal que no surt al DIEC, prova
  `bdlex_consulta` abans de qualificar-lo: potser el recull el DCVB.
- DIEC: lèxic normatiu. Cita l'entrada i l'accepció; una locució pot ser dins
  de l'article d'un dels mots. No trobar-hi una forma no la fa incorrecta.
- BDLex: diccionaris històrics i dialectals (DCVB, DIEC, Fabra, obres dels
  segles XIX i XX). Per documentar mots antics o propis d'un parlar i per
  cercar per definició o exemple. És descriptiu: una forma hi pot constar i
  no ser adequada avui. Cita sempre el diccionari concret.
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
  observada, no de tendència. Les col·locacions indiquen quines paraules hi
  coapareixen dins d'una finestra de mots; les seves xifres no es poden
  comparar amb els recomptes de seqüència exacta.
- Softcatalà: sinònims. Són propostes de significat; tria les que encaixen en
  la frase i explica'n el matís.

Per a una correcció, dona primer la frase o la forma corregida, després una
explicació breu i finalment la font consultada. Si l'original ja és correcte i
suggereixes una alternativa, marca-la com a opció d'estil. Si una font no
respon o no tracta el cas, digues-ho: no li atribueixis cap criteri.

No revisis paràgrafs sencers per iniciativa pròpia: l'usuari fa consultes
puntuals sobre una paraula, una expressió o una frase.
"""

mcp = MCPServer("llengua", instructions=INSTRUCTIONS, version="0.1.0")

_app: App | None = None
_app_lock = asyncio.Lock()


async def get_app() -> App:
    global _app
    if _app is None:
        async with _app_lock:
            if _app is None:
                _app = App(Settings.from_env())
    return _app


async def _call(source: str, awaitable) -> dict[str, Any]:
    try:
        return await awaitable
    except LlenguaError as exc:
        return error_payload(exc, source=source or exc.source)
    except Exception as exc:  # noqa: BLE001 - l'agent ha de rebre un error útil
        return error_payload(
            UnexpectedResponseError(
                "Error inesperat en consultar la font.",
                hint=f"{type(exc).__name__}: {exc}",
                source=source,
            ),
            source=source,
        )


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
    resultats no és una freqüència d'ús. Per a una expressió concreta (per
    exemple «tenir que»), prova el mode `frase_exacta`; per a un fenomen, cerca
    amb `fitxes` paraules com «perífrasi d'obligació» o «haver de».
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
async def diec_consulta(paraula: str, limit: int = 3) -> dict[str, Any]:
    """Consulta el DIEC i retorna les accepcions de l'entrada.

    Serveix per validar el lèxic i, sobretot, per identificar l'accepció
    aplicable. Una locució pot figurar dins de l'article d'un dels mots. Si no
    hi ha entrada, això no converteix la forma en incorrecta.
    """
    app = await get_app()
    return await _call("https://dlc.iec.cat/Results", app.diec.consulta(paraula, limit=limit))


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

    La cerca exacta pot fallar en entrades multiparaula. Si coneixes la forma,
    obre-la directament amb `esadir_fitxa`. ésAdir és estil de la CCMA, no la
    norma de l'IEC.
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


def _sync_call(source: str, function, *args, **kwargs) -> dict[str, Any]:
    try:
        return function(*args, **kwargs)
    except LlenguaError as exc:
        return error_payload(exc, source=source or exc.source)
    except Exception as exc:  # noqa: BLE001
        return error_payload(
            UnexpectedResponseError(
                "Error inesperat en consultar la font.",
                hint=f"{type(exc).__name__}: {exc}",
                source=source,
            ),
            source=source,
        )


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
    `DCVB` i `DIEe`; indica `dicts` per afegir-ne d'altres (p. ex. `DGLC`, `DIE2`).
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

    Cerca la paraula o la locució sencera. Si no hi ha entrada per a una
    expressió, no en busca els components per separat, perquè els sinònims
    d'una part no equivalen als de l'expressió. Si dones un `context`, el model
    ha de triar les opcions que hi encaixen i explicar-ne el matís.
    """
    app = await get_app()
    return _sync_call(
        "https://www.softcatala.org/diccionari-de-sinonims/",
        app.softcatala.cerca,
        paraula,
        context=context,
        limit=limit,
    )


@mcp.tool()
async def cerca_frase(
    frase: str,
    variants: list[str] | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Cerca una seqüència contigua de formes al CTILC.

    Cada paraula és un token. No incloguis puntuació externa: el corpus
    tokenitza per formes. Les variants són frases completes alternatives
    (per exemple, «tenir foc al ulls» i «tenir foc als ulls»); es consulten per
    separat i els totals no se sumen. Retorna contextos, total verificat, eco
    del patró i un cursor per continuar. Un zero només és una absència en aquest
    corpus, no una prova que la forma no existeixi.
    """
    app = await get_app()
    return await _call(
        "https://ctilc.iec.cat/scripts/CTILCQConc_Coocur2.asp",
        app.ctilc.search_phrase(frase, variants=variants, limit=limit),
    )


@mcp.tool()
async def cerca(
    lema: str | None = None,
    forma: str | None = None,
    categoria: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Cerca simple al CTILC per lema o per forma.

    `lema` cerca totes les formes del lema i admet una `categoria` (`subst`,
    `V`, `adj`...). `forma` cerca una sola forma gràfica. No es poden combinar
    totes dues. Retorna els mateixos contextos verificats que `cerca_frase`,
    amb `pattern_echo`, total i cursor.
    """
    app = await get_app()
    return await _call(
        "https://ctilc.iec.cat/scripts/CTILCQConc_Coocur2.asp",
        app.ctilc.cerca(lema=lema, forma=forma, categoria=categoria, limit=limit),
    )


@mcp.tool()
async def cerca_patro(
    elements: list[PatternElement],
    limit: int = 10,
) -> dict[str, Any]:
    """Cerca un patró avançat al CTILC (combinacions).

    Cada element pot ser `lema` (amb `category` opcional), `forma` (una sola
    paraula), `formalema`, `cg` (categoria i morfologia) o `qualsevol`. Es pot
    marcar `optional` o `negated`, però no tots dos alhora. Per a un nom amb
    adjectiu: lema «somriure» amb categoria «subst» + cg «adj».

    Retorna el patró executat, el total verificat i contextos. `optional` en
    diversos elements seguits emula un interval, però no s'ha de presentar com
    una equivalència de rangs sense controls positius.
    """
    app = await get_app()
    return await _call(
        "https://ctilc.iec.cat/scripts/CTILCQConc_Coocur2.asp",
        app.ctilc.search_pattern(elements, limit=limit),
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

    Passa el `next_cursor` d'una cerca concreta: la distribució només és
    vàlida vinculada a aquella consulta. Retorna per tram `from_year`,
    `to_year`, `hits`, `corpus_units` i `per_million` (ocurrències per milió
    de paraules, derivades dels enters), i destaca els pics absolut i relatiu.

    Les dades es validen: si el patró de la pàgina no és el de la cerca o la
    suma dels trams no coincideix amb el total, l'eina ho indica i no presenta
    la gràfica com a vàlida. Amb pocs testimonis, parla de concentració
    observada, no de tendència.
    """
    app = await get_app()
    return await _call(
        "https://ctilc.iec.cat/scripts/CTILCQDispersionsCron.asp",
        app.ctilc.dispersio_cronologica(cursor),
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
    return app.ctilc.etiquetes()


@mcp.tool()
async def salut() -> dict[str, Any]:
    """Comprova que el CTILC respon i que l'eco de control és correcte.

    Fa una consulta coneguda (`somriure` + adjectiu) i compara el total amb el
    de referència del 18/11/2026. Una diferència de total pot ser un canvi
    legítim del corpus; un eco incorrecte o un error de transport sí que és
    un problema de protocol. No cal invocar-ho abans de cada cerca.
    """
    app = await get_app()
    return await _call("https://ctilc.iec.cat/scripts/CTILCQConc_Coocur2.asp", app.ctilc.salut())


def main() -> None:
    """Punt d'entrada per a `python -m llengua_mcp.server` i l'executable."""

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
