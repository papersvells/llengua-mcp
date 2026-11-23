<p align="center">
  <img src="llengua-mcp-logo.png" alt="Logo de Llengua MCP" width="300">
</p>

# Llengua-mcp: assessorament de llengua catalana amb fonts verificades per al teu assistent

[![CI](https://github.com/papersvells/llengua-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/papersvells/llengua-mcp/actions/workflows/ci.yml)

**Llengua** és un servidor local de [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)
que connecta assistents d'IA amb diccionaris, gramàtiques i corpus de català.
Pregunta-li per una paraula, una expressió o una frase i demana-li que consulti
les fonts abans de respondre.

Ajuda a resoldre dubtes, comparar formulacions, trobar sinònims i examinar
exemples d'ús escrit. No és un corrector de documents sencers ni un servei
oficial de l'IEC. Revisa sempre les fonts i els matisos de la resposta.

## Fonts

| Font | Què aporta |
|---|---|
| [Optimot](https://aplicacions.llengua.gencat.cat/llc/AppJava/index.html) | Criteris sobre gramàtica, construcció, registre i lèxic |
| [Corpus de consultes de l'IEC](https://consultes-linguistiques.iec.cat/) | Respostes curades a dubtes reals, amb enllaços a les fonts |
| [DIEC](https://dlc.iec.cat/) | Lèxic normatiu i accepcions |
| [ésAdir](https://www.esadir.cat/) | Estil de la CCMA, pronunciació i noms propis |
| [BDLex](https://bdlex.iec.cat/) | Diccionaris històrics i dialectals, inclòs el DCVB |
| [OIEC](https://oiec.iec.cat/) i gramàtiques de l'IEC | Ortografia, gramàtica bàsica i gramàtiques de referència |
| [CTILC](https://ctilc.iec.cat/) | Ús escrit, contextos, col·locacions i dispersió |
| [Softcatalà](https://www.softcatala.org/diccionari-de-sinonims/) i [Jané](https://sinonims.iec.cat/) | Sinònims; Jané separa accepcions numerades |
| [Diccionari anglès-català de Softcatalà](https://github.com/Softcatala/diccionari-angles-catala) | Equivalents per a mots i locucions anglesos, amb accepcions i marques d'ús |
| [Llista de Xavier Pàmies](https://diccxpamies.xarxa.cat/) | Solucions de traducció anglès-català i glossaris literaris |
| [DIRELEX](https://direlex.softcatala.org/) | Alternatives lèxiques contextualitzades, notes d'ús i fraseologia; dades CC BY-NC 4.0 |
| [DSFF](https://dsff.uab.cat/) | Frases fetes, conceptes i relacions de sentit; dades CC BY-NC-SA 4.0 |
| [PCCD](https://pccd.dites.cat/) | Paremiotipus, variants i fonts de dites i refranys; dades sota CC BY-NC-SA 4.0 |
| [Conjugador de Softcatalà](https://www.softcatala.org/conjugador-de-verbs/) | Formes verbals amb marques territorials |

## Instal·lació ràpida

Necessites [uv](https://docs.astral.sh/uv/getting-started/installation/) i Git.
La manera més simple és executar Llengua directament des de la branca `main`
del repositori de GitHub amb [`uvx`](https://docs.astral.sh/uv/guides/tools/).
No cal clonar manualment el repositori ni registrar-se a PyPI. El client ha de
poder trobar `uvx` al seu `PATH`.

Aquesta configuració segueix la branca `main`, de manera que pot rebre canvis.
Quan hi hagi versions etiquetades, pots fixar-ne una canviant
`git+https://github.com/papersvells/llengua-mcp.git` per
`git+https://github.com/papersvells/llengua-mcp.git@vX.Y.Z`.

### OpenCode

Afegeix aquesta configuració a `opencode.jsonc` del projecte o al fitxer global
de configuració. Si ja tens un fitxer, integra-hi només l'entrada `llengua`:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "servers": {
      "llengua": {
        "type": "local",
        "command": [
          "uvx",
          "--from",
          "git+https://github.com/papersvells/llengua-mcp.git",
          "llengua-mcp"
        ],
        "timeout": { "execution": 60000 },
        "codemode": false
      }
    }
  }
}
```

Comprova la connexió amb `opencode mcp list` o `/mcps`. Si OpenCode no troba
`uvx`, configura'n la ruta absoluta.

### Claude Code

```sh
claude mcp add --scope user --transport stdio llengua -- \
  uvx --from git+https://github.com/papersvells/llengua-mcp.git llengua-mcp
claude mcp get llengua
```

A Claude Code, comprova l'estat amb `/mcp`. Més informació a la
documentació de [Claude Code](https://code.claude.com/docs/en/mcp).

### Codex

```sh
codex mcp add llengua -- \
  uvx --from git+https://github.com/papersvells/llengua-mcp.git llengua-mcp
codex mcp list
```

Consulta la [documentació MCP de Codex](https://developers.openai.com/codex/mcp/)
per veure l'estat de la connexió.

### Antigravity

A l'Antigravity App, obre **Customizations → Installed → MCP Servers** i fes
servir **Copy Config File Path** per trobar `mcp_config.json`. Afegeix-hi
l'entrada següent dins de `mcpServers`, conservant la resta de configuració:

```json
{
  "mcpServers": {
    "llengua": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/papersvells/llengua-mcp.git",
        "llengua-mcp"
      ]
    }
  }
}
```

Comprova l'estat al gestor de servidors MCP. Consulta la documentació
[actual d'Antigravity](https://antigravity.google/docs/mcp); els noms de menús
poden variar entre l'App, l'IDE i la CLI.

### Pi i altres clients

Pi necessita una extensió compatible amb servidors MCP; la configuració depèn
de l'extensió. En qualsevol client MCP que admeti transport local `stdio`,
configura `uvx` com a comanda i aquests arguments:

```text
--from
git+https://github.com/papersvells/llengua-mcp.git
llengua-mcp
```

Consulta la documentació del client o de l'extensió per saber on introduir-los.

## Comprova que funciona

Quan el client indiqui que Llengua està connectat, pregunta:

> És correcte dir «tinc que anar a casa»? Consulta les fonts i explica'm
> l'alternativa.

Comprova que l'assistent ha fet servir les eines i cita les fonts, no només que
ha generat una resposta. La primera execució amb `uvx` pot trigar una mica
perquè descarrega el paquet i prepara l'entorn.

## Sinònims de Softcatalà (opcional)

Les eines de consulta funcionen sense baixar aquestes dades; només
`cerca_sinonims` necessita el fitxer local. Per instal·lar-lo al directori de
dades de l'usuari:

```sh
uvx --from git+https://github.com/papersvells/llengua-mcp.git llengua-mcp-fetch-sinonims
```

La baixada usa una revisió fixada de les dades de Softcatalà (llicència CC BY
4.0). Es desen al directori de dades de l'usuari. Per personalitzar-lo, defineix
`LLENGUA_DATA_DIR` tant al client MCP com a la comanda de baixada.

## Diccionari anglès-català de Softcatalà (opcional)

Instal·la les dades locals per activar `engcat_cerca`:

```sh
uvx --from git+https://github.com/papersvells/llengua-mcp.git@v0.4.0 llengua-mcp-fetch-engcat
```

La comanda crea un índex local a partir de l'XML d'una revisió fixada. Si fas
servir `LLENGUA_DATA_DIR`, configura el mateix directori al client MCP i a la
comanda d'instal·lació. Les cerques no fan peticions de xarxa.

Per exemple, pregunta «Com en dic, de *bank*, si parlo de la vora d'un riu?».
L'eina cerca el mot o la locució sencera; no tradueix frases ni documents.

## DIRELEX (opcional)

Per consultar el Diccionari de recursos lexicals, instal·la les dades locals:

```sh
uvx --from git+https://github.com/papersvells/llengua-mcp.git@v0.5.0 llengua-mcp-fetch-direlex
```

Les dades són de Carles Castellanos i Llorenç i Agustí Mayor i Lloret,
[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/deed.ca):
**només per a ús no comercial**. Es descarreguen separadament del paquet MIT,
en una revisió fixada. Configura el mateix `LLENGUA_DATA_DIR` a la comanda
i al client MCP. La consulta `direlex_cerca` no fa xarxa ni cerca al glossari.

## Consells i límits

- Dona la frase sencera i explica el registre o el matís que busques.
- Demana que l'assistent consulti i citi fonts; les respostes poden contenir
  errors o diferir segons el model.
- Distingeix norma, registre i recomanacions d'estil.
- El CTILC recull textos escrits: una ocurrència no demostra correcció ni ús
  quotidià, i un zero no demostra que una expressió no existeixi.
- Les consultes s'envien als portals externs. Evita incloure-hi informació
  sensible; el projecte limita el ritme i no fa descàrregues massives.

## Privacitat, fonts i llicència

El servidor s'executa a l'ordinador de l'usuari, però consulta fonts externes
per Internet. Les dades dels diccionaris de Softcatalà i del DIRELEX són locals
un cop baixades.
El codi es distribueix sota llicència MIT; les dades i els serveis consultats
poden tenir condicions diferents. Consulta [`NOTICE`](NOTICE) per les fonts,
llicències i atribucions. Llengua-mcp no és un producte oficial de l'IEC, la CCMA
ni Softcatalà.

## Desenvolupament

Per treballar des del codi font, clona el repositori i instal·la les
dependències de desenvolupament:

```sh
git clone https://github.com/papersvells/llengua-mcp.git
cd llengua-mcp
uv venv
uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/ruff format .
.venv/bin/ruff check .
.venv/bin/pytest
```

Les proves habituals no fan xarxa. Les proves en directe són opcionals:

```sh
LLENGUA_LIVE=1 .venv/bin/pytest tests/test_live.py
```

Per a la referència completa de les eines, les variables d'entorn, els formats
de resposta i les limitacions, consulta [`docs/referencia.md`](docs/referencia.md).
