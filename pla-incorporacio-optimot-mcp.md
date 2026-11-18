# Pla d’incorporació de l’Optimot al futur MCP de llengua

**Proves:** 18 de novembre de 2026 · **Font:** [Optimot, consultes lingüístiques](https://aplicacions.llengua.gencat.cat/llc/AppJava/index.html)  
**Documents relacionats:** [pla d’ésAdir](pla-incorporacio-esadir-mcp.md) i [revisió del CTILC](pla-mcp-ctilc-tercer-en-discordia.md).

## 1. Objectiu i abast

Incorporar l’Optimot com a **cercador de referències lingüístiques**: trobar una fitxa pertinent, llegir-la i citar-la. El portal és del Departament de Política Lingüística i integra diverses fonts, entre elles les fitxes pròpies, el DIEC i diccionaris terminològics del TERMCAT. **Optimot és el portal; l’autoritat i l’abast de cada resultat depenen de la font concreta.**

No substitueix el CTILC: el nombre de documents que retorna el cercador **no és un recompte d’ocurrències** i no informa de freqüència, època ni quotidianitat. Tampoc és un corrector de text complet. El primer lliurable serà de consulta i lectura, sense enviar textos sencers ni automatitzar el servei d’atenció personalitzada.

## 2. Cerques de prova en directe

Peticions GET puntuals, separades com a mínim per aproximadament un segon. A totes les cerques de la taula el servidor ha respost HTTP 200. Els totals són els **mostrats pel portal** en aquesta sessió, no valors fixos de regressió.

| Consulta | Mode | Resultat observat | Implicació |
|---|---|---|---|
| `tenir foc als ulls` | Frase exacta | «No hi ha resultats» | No s’ha trobat una entrada amb aquest mode; no implica que l’expressió no existeixi o sigui incorrecta. |
| `tenir foc als ulls` | Bàsica | 16.681 resultats; entre els primers, *foc* (DIEC), una fitxa d’*alto el foc* i *tenir* (DIEC) | El total inclou coincidències parcials; no s’ha d’oferir com a evidència sobre la frase. |
| `tindre o tenir` | Fitxes de l’Optimot | 1.966 resultats; la primera és *tindre o tenir?* | Prioritzar el títol pertinent i obrir la fitxa abans d’atribuir-li una recomanació. |
| `conèixer` | Verbs conjugats | 1 resultat: *conèixer*, font «Verbs conjugats». No s’ha detectat un enllaç ordinari `method=detall` | No reutilitzar el flux de fitxes sense verificar abans com s’obté la conjugació. |
| `acera` | Castellà-català | 28 resultats; primer, *acera (castellà)* del Diccionari castellà-català; també hi ha entrades del TERMCAT | El mode no exclou altres fonts; conservar la procedència de cada candidat. |

### 2.1. Fitxa de detall: correcció d’una hipòtesi anterior

Seguint l’enllaç de la primera fitxa de `tindre o tenir` s’ha obtingut HTTP 200. La pàgina mostra **fitxa 6442/3**, **darrera versió 17.06.2022** i una resposta que admet els dos infinitius i indica que *tenir* és la forma més general en registres formals.

El mateix enllaç, conservant la consulta i traient només `;jsessionid=…` del camí, també ha retornat la fitxa correcta, **tant amb la sessió de cerca com amb un client nou sense cookies prèvies**. Per tant, el 500 d’una prova anterior amb una URL de detall reconstruïda amb menys camps **no demostra que l’Optimot necessiti sessió per obrir qualsevol fitxa**. Tampoc sabem quins camps són mínims per a totes les fonts.

`idFont=15260` i `idHit=15260` són identificadors del resultat web en aquest cas; **no són el número editorial 6442/3**. No generalitzar el comportament dels enllaços a DIEC, TERMCAT, traduccions, conjugacions o paginació sense proves addicionals.

## 3. Integració tècnica

### 3.1. Cerca

L’entrada pública observada és un formulari GET que torna **HTML**, no una API documentada. Exemple de cerca:

```text
https://aplicacions.llengua.gencat.cat/llc/AppJava/index.html?action=Principal&method=cerca_generica&input_cercar=tindre+o+tenir&tipusCerca=cerca.fitxes
```

| Mode públic de l’eina | Valor del formulari | Prioritat |
|---|---|---|
| `fitxes` | `cerca.fitxes` | Primer per a dubtes de construcció, gramàtica o registre |
| `basica` | `cerca.tot` | Cerca lèxica i descoberta entre fonts |
| `frase_exacta` | `cerca.queSignifica` | Cerca exacta al portal, **no** al corpus |
| `castella_catala` | `cerca.traduir` | Opcional, després de verificar el detall |
| `verbs` | `cerca.verbs` | Ajornat fins a verificar l’extracció de formes conjugades |

Codificar els paràmetres amb el client HTTP (accents, apòstrofs, espais) i limitar les consultes a termes o fragments curts. No seguir automàticament totes les pàgines ni obrir totes les entrades. Per a un dubte gramatical, cercar per les paraules clau del fenomen; obrir només els candidats pertinents. El filtratge per font i la paginació remota poden esperar.

### 3.2. Cerca i detall són parsers diferents

- **Cerca:** extreure files només del bloc de resultats. Retornar títol, font original, àrea temàtica si hi és, fragment breu i referència de detall si és disponible. Ignorar filtres laterals, menú i números globals. No inventar un fragment ni un enllaç quan no hi són.
- **Detall:** obtenir el bloc de resposta de la fitxa, no la previsualització de la columna de resultats. Preservar número editorial, data de versió si consta, títol i font; distingir aquests camps de la data de consulta de l’MCP.
- **Enllaços:** resoldre rutes relatives; només fer peticions a l’origen HTTPS previst i a camins i accions de consulta coneguts. No seguir enllaços arbitraris ni publicar IDs de sessió en citacions o registres. Per a l’MVP, usar una referència local temporal per obrir un candidat; publicar un enllaç de detall sense sessió només si se n’ha comprovat la validesa. Si no, retornar la referència editorial i l’enllaç al cercador, indicant que no és un enllaç directe.
- **Estats:** `ok`, `no_results`, `partial`, `upstream_error` i `unexpected_response`. Només `no_results` quan la pàgina és reconeguda i conté el missatge explícit de cap resultat. Un 500, una pàgina d’error amb HTTP 200 o un canvi d’HTML no són un zero.

## 4. Eines del futur MCP

Afegir un adaptador `optimot` i parsers separats al mateix servidor de llengua que els adaptadors CTILC i ésAdir. No cal un segon servidor ni canviar la configuració d’OpenCode per cada font.

| Eina | Entrada | Sortida |
|---|---|---|
| `optimot_cerca` | `consulta`, `mode`, `limit` | Candidats amb títol, font original, fragment, referència temporal i avisos. Per defecte, fins a cinc candidats; indicar si són una mostra. |
| `optimot_fitxa` | Referència retornada per `optimot_cerca` | Títol, número i versió quan constin, fragment pertinent, font, URL verificat si és possible i data de consulta. |

El model ha de poder distingir «he trobat un candidat» de «he llegit la resposta». Si la primera pàgina és sorollosa, reformular una vegada o indicar que no s’ha trobat una referència pertinent; no citar una fitxa només perquè surt primera.

### Exemple d’ús

> **«Puc escriure “tindre” en un text formal?»**  
> La fitxa 6442/3 de l’Optimot admet *tenir* i *tindre* i indica que, en registres formals, *tenir* és la forma més general. Per tant, si busques aquesta forma més general, tria *tenir*; això no converteix *tindre* en una incorrecció. Font: Fitxes de l’Optimot, versió del 17.06.2022.

**Amb la resta de fonts:** si et pregunten si una expressió està documentada, consulta el CTILC. Si et pregunten quin criteri aplica 3Cat, consulta ésAdir. Si et pregunten per la norma o pel registre, busca una referència pertinent a l’Optimot i identifica si és una fitxa, el DIEC o una altra font. Una recomanació editorial, una admissió normativa i una atestació poden coexistir sense contradir-se.

## 5. Proves d’acceptació i límits

1. **Sense xarxa a CI:** mostres petites o sintètiques de cerca amb fonts mixtes, fitxa positiva amb número i data, zero explícit, error HTTP i pàgina inesperada. Comprovar que el títol de la fitxa no es confon amb la previsualització i que els enllaços de sessió no surten al resultat.
2. **En directe, optatiu:** comprovar el control *tindre o tenir?* i el cas de frase exacta. Registrar data i mode, i validar estructura, font i contingut pertinent, no els totals històrics. Tornar a provar el detall sense cookies amb més d’una classe de font abans d’ampliar el contracte.
3. **A OpenCode:** l’agent ha de citar la fitxa que ha obert, no penalitzar *tindre* com a error general i no confondre els resultats amplis de «tenir foc als ulls» amb testimonis del CTILC. Si la font no respon, ho ha de dir explícitament.

**Ús responsable:** pressupost baix de peticions per consulta, límit compartit per host (p. ex. una petició per segon), identificació del client amb contacte, respecte pels senyals de limitació i cap reintent automàtic de 500. No enviar documents sencers o dades personals. Consultar l’[avís legal de la Generalitat](https://web.gencat.cat/ca/menu-ajuda/ajuda/avis_legal/) i les condicions de les fonts integrades abans de distribuir el servei o conservar contingut. No donar per fet que totes tenen la mateixa llicència. Respectar les directives HTTP de memòria cau i no persistir HTML, cookies o cossos de fitxes per defecte.

**Ordre recomanat:** lliurar primer `optimot_cerca` en mode fitxes i bàsic més `optimot_fitxa`, amb citacions verificables. Després afegir traducció, conjugació i consultes creuades si els seus fluxos queden validats. La correcció automàtica continua sent una capa separada.
