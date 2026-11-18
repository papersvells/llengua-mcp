# Tercer en discòrdia: què cal resoldre abans de construir l’MCP del CTILC

**Revisió:** 18 de novembre de 2026.  
**Fonts:** [pla inicial](pla-mcp-ctilc.md), [primera revisió](pla-mcp-ctilc-critiques.md), [criteris del projecte](AGENTS.md) i captures HTML locals de les proves anteriors. No s’han fet peticions noves al CTILC. Quan es diu «observat», es parla d’una captura concreta, no d’un contracte garantit per l’IEC.

**Veredicte:** la cerca de concordances és viable. El problema principal pendent no és triar un *stack*, sinó demostrar que cada recompte correspon exactament a la pregunta feta i que les seves pàgines i gràfiques pertanyen al mateix resultat. Ni el pla inicial ni la primera revisió són una especificació implementable sense matisos.

## 1. Discrepàncies i correccions

| Qüestió | Què diuen els documents | Resolució proposada |
|---|---|---|
| Rang `[]{2,5}` | El pla (§4) el resol amb una cadena d’opcionals. La revisió (§2.1, §6.2) arregla el cas 0–3, però deixa sense especificar un mínim positiu. | Per a les longituds 2–5: dos comodins obligatoris i tres d’opcionals. És una equivalència de longitud; no dona per demostrada l’equivalència de recomptes, coincidències superposades o selecció de trams pel motor. No exposar rangs fins que hi hagi controls positius. |
| Què prova el zero de G5? | L’apèndix inicial parla de «somriure de/amb mala fe» amb i sense interval; G5 no exigeix `de` ni `amb`. | G5 és una consulta diferent: un comodí pot cobrir una preposició, però aleshores en consumeix una de les posicions. Per provar fins a tres tokens **abans** de la preposició, aquesta ha de ser un element explícit després dels comodins. Si interessa la distància **després**, és una altra cerca. |
| Negació i alternança | La revisió §2.4 i G15 atribueixen 13.061 a `<>(amb\|de)`. | La captura `ctilc_multi_neg.html` conserva a `formdata` el valor equivalent a `<>amb\|de`, **sense parèntesis de valor**. L’eco els afegeix visualment. Corregir G15: no copiar l’eco com a entrada ni donar per equivalent una serialització no provada. |
| Exactitud i majúscules | El pla (§4) promet «forma gràfica exacta»; la revisió (§2.2) en resol el cas amb espais. | La consulta interna visible de l’alternança conté formes com `[aA]mb` i `[dD]e`. «Seqüència de formes contigües» no vol dir subcadena literal sensible a majúscules. Documentar què fa cada modalitat; no prometre una semàntica d’accents, apòstrofs o guionets encara no verificada. |
| Categories sense morfologia | La revisió mana compilar una categoria a `adj:-`, però al final demana que G18 falli en validació. | Són dues capes: `categoria: adjectiu` és una entrada vàlida i s’ha de compilar a `adj:-`; el cos sense `:-` és un cas negatiu de protocol, no un error de l’usuari. L’endpoint bàsic té un camp `cg` diferent. |
| CQL, `strquery` i eco | El pla descarta CQL cru; la revisió veu un camp de continuació reutilitzable i en dedueix que l’afirmació és falsa. | No és una contradicció estricta: un camp intern amb una sintaxi i un format propis no demostra suport a CQL **cru** ni identifica el motor. Igualment, la falta de resultats d’un parell de rangs no demostra que el motor no els admeti. `strqueryTXT` pot reflectir text de presentació i no és una prova independent d’execució. No exposar CQL cru ni el camp intern a l’agent. |
| Identificadors i paginació | El pla confia en `resultat_id`; la revisió afegeix `Qlocali` i proposa reexecutar la consulta. | L’ID és una cadena opaca de dígits; les captures no en demostren el tipus intern de 64 bits. El cas de l’ID alterat conserva el 2.136 però no conté cap fila, de manera que el recompte sol no valida la continuació. Reexecutar és útil, però no conserva una instantània. |
| CSV | El pla descriu `cHTML1` com la taula; la revisió ho corregeix però proposa paginar amb `iStartC`/`iStopC` si l’exportació és local. | Els camps amb `C` són del formulari d’exportació. Si mai es genera un CSV local, cal obtenir les files amb la paginació de concordances (`iStart`/`iOffset`), marcar l’abast i aplicar un límit d’exportació. No cal CSV per a l’MVP. |
| Xifres i manteniment | El pla assumeix manteniment baix; la revisió ho refuta amb el ritme de creixement del corpus. | Una taxa anunciada en una pàgina de presentació no prova el ritme actual ni l’estabilitat del protocol. Distingir canvis de contingut, de cobertura i de format. Datació i unitat als denominadors, no constants històriques presentades com a actuals. |

**Dues esmenes menors:** la revisió diu que el pla omet els imperatius, però el pla els esmenta sense enumerar-los. També infereix una pèrdua d’uns 16 resultats «per pàgina de 1.000» dividint 49 entre tres: l’última pàgina tenia 136 files i no consta quina mida es va fer servir en el recompte defectuós. Només és segur el dèficit agregat de 49 del relat original.

## 2. Què aporten les captures locals

### 2.1. L’interval i la preposició

Les captures `ctilc_q_range.html`, `ctilc_opt3.html` i `ctilc_opt3b.html` permeten separar tres casos:

| Eco normalitzat | Total | Què es pot afirmar |
|---|---:|---|
| `somriure mala fe` | 0 | La clau de rang no ha produït els comodins previstos. Aquest zero no informa sobre el patró demanat. |
| `somriure []? []? []? mala fe` | 0 | Consulta diferent: no exigeix cap preposició concreta. L’eco concorda amb aquest patró. |
| `somriure []? []? []? (amb \| de) mala fe` | 0 | Hi ha una captura que sí que conserva la preposició després de fins a tres posicions intermèdies. No prova altres col·locacions del buit ni variants gràfiques. |

En el primer cas, «zero no pertinent» és més exacte que «fals zero»: la consulta correcta també pot donar zero. Per demostrar que el compilador conserva el buit, cal un **control positiu**: una ocurrència citada amb un token intermedi, recuperable amb el buit i no amb la versió adjacent. Verificar la fila, no només l’eco. En documentar distàncies, parlar de *tokens del corpus*, no de paraules separades per espais.

### 2.2. Paginació i metadades

En `ctilc_q1_s1.html`, `ctilc_q1_s1001.html` i `ctilc_q1_s2001.html` he comptat amb DOM 1.000, 1.000 i 136 enllaços de nucli, amb 2.136 valors `id` diferents per a aquesta consulta. Les tres pàgines duen **tres `resultat` diferents**. El recompte coincideix, però això no demostra que una reexecució mantingui l’ordre o les mateixes files en altres moments o en patrons de longitud variable. Tampoc demostra que `id` sol distingeixi dos trams diferents que comencin al mateix token.

La mateixa mostra confirma 995 parelles de formes distingint majúscules, 982 sense distingir-les i 879 segons tokens diferents segons la normalització aplicada. **No són 879 lemes adjectivals.** D’altra banda, conservar `id`, `obra`, `tok` i `seccio` com a dades de localització verificades; no convertir `obra` en identificador bibliogràfic ni assumir que és un índex. La fitxa pot aportar metadades que la concordança no porta. No fer una petició de fitxa per cada resultat per defecte.

### 2.3. La dispersió cronològica és prou concreta per prioritzar-la

La captura `ctilc_CTILCQDispersionsCron_get.html` conté **deu trams** amb numerador i denominador. Per a la consulta de control *somriure + adjectiu*, sumen exactament 2.136 ocurrències i 126.604.218 unitats del corpus. Per exemple, 1832–1913 té 45 sobre 13.001.158 (**3,46 per milió**); 2021–2022 té 307 sobre 12.732.985 (**24,11 per milió**). Aquest és un exemple comprovat amb les captures; **no** són dades de «tenir foc als ulls».

El gràfic en percentatge i una proporció decimal no tenen la mateixa escala. Cal derivar `per_million = hits / corpus_units × 1.000.000` a partir dels enters, declarar la unitat del denominador i no fer servir els percentatges arrodonits per recalcular els enters. La pàgina de dispersions generals conté diverses assignacions `chartData` amb significats diferents. Prioritzar el gràfic cronològic concret, distingir recompte absolut, taxa i quota sobre les ocurrències trobades, i **no executar JavaScript remot** per llegir les dades.

## 3. Contracte proposat: una fitxa d’evidència, no un embolcall del web

### MVP de producte per a OpenCode

1. **`cerca_frase`**: seqüència contigua i una llista curta de variants explícites. Cercar per separat l’original i les variants; no autocorregir en silenci ni sumar totals que es puguin solapar. Diferenciar les formes literals de les cerques lèxiques amb flexió, mostrant quin patró s’ha executat.
2. **`context`**: mostrar un nombre petit de concordances i, si cal, recuperar-ne la fitxa. Separar metadades confirmades de les absents. No quantificar els usos figurats a partir d’un parell de fragments.
3. **`dispersio_cronologica`**: associada al resultat de cerca i només disponible quan les dades del gràfic s’han pogut vincular a aquella consulta. Retornar per tram `from_year`, `to_year`, `hits`, `corpus_units` i `per_million`. Mostrar els pics absolut i relatiu, encara que discrepin. Si hi ha pocs testimonis, parlar de concentració observada i no de tendència general.

L’MVP tècnic és la primera eina amb validació de cap a cap; **l’MVP de producte** inclou també context i cronologia perquè això és el que respon la pregunta acordada. Col·locacions, filtres avançats, catàleg, CSV i API de patrons oberta poden esperar. Una comprovació de salut és un diagnòstic, no una eina que el model hagi d’invocar abans de cada cerca.

### Resposta i estats

| Estat | Significat públic |
|---|---|
| `ok` | Total llegit d’una pàgina reconeguda; patró compatible amb el demanat; mostra de files identificada com a tal. |
| `no_matches` | Total explícit de zero, patró verificat i resposta reconeguda de cap coincidència. En les captures de zero no existeix `#cHTML1`: cal un parser de resultats buits, no un valor zero per defecte. |
| `partial` | L’MCP pot justificar dades concretes però no tota la sortida (p. ex., total verificat i cronologia no disponible). Cada bloc n’indica la cobertura; no sumar ni extrapolar les dades que falten. |
| `invalid_query`, `upstream_error`, `unexpected_response`, `stale_search` | No s’ha pogut validar el recompte o continuar la cerca. No retornar `total: 0` per omplir l’esquema. |

Retornar consulta demanada i executada, mode de coincidència, total verificat quan n’hi hagi, mida de mostra, font, data i avisos. Per a la cronologia i els recomptes per obra, marcar si la font cobreix tots els resultats o només la mostra. `M obres / A autors` és un total només amb dades completes o una agregació verificada; altrament, «a la mostra, com a mínim M obres». Si no hi ha denominador per al mateix abast dels filtres, no calcular taxa.

**Prova d’acceptació:** «Com veus l’expressió “tenir foc al ulls”?». La resposta pot indicar «He cercat també la forma “tenir foc als ulls”», donar `N` si és verificat, ensenyar exemples i dir en quins trams apareix més en termes absoluts o relatius. Si `N > 0`, dir que **la seqüència està documentada**. Per atribuir-li un sentit figurat concret, llegir els testimonis. No cal una reserva genèrica a cada resposta, però si l’usuari pregunta per l’ús quotidià, explicar què permet inferir un corpus escrit. No hi ha cap `N` prefixat per a aquest exemple.

## 4. Decisions tècniques que eviten falsos resultats

- **Cursor local i caducable.** Per a l’MVP local, fer servir una referència aleatòria a un registre en memòria amb TTL i límit d’entrades. Guardar consulta, abast, ordenació, posició i l’estat remot observat. Base64 només codifica: no aporta integritat ni confidencialitat. No enviar IDs remots com a credencials ni barrejar el resultat d’una cerca reexecutada amb les pàgines o la gràfica de l’anterior. Si el resultat expira, oferir reiniciar la cerca.
- **Separar pàgina remota de pàgina visible.** Començar amb una mida remota observada de 50 i retornar una mostra més breu. Si es retorna un subconjunt de la pàgina, el cursor ha de conservar la posició dins la pàgina; no pot saltar la resta. No donar per homologats `iOffset=100` o `200`. Validar l’ordre amb pàgines que tinguin empats.
- **Validació per capes.** Comparar l’eco estructural, no els espais ni només el nombre de posicions. Revisar total explícit, marcadors de pàgina i files (inclosa una pàgina fora d’abast); no tractar un total reproduït d’un paràmetre de continuació com a confirmació independent. Amb clics de fitxa, conservar només paràmetres esperats i construir l’enllaç a l’origen fix del CTILC.
- **Transport i seguretat.** Dir-ne «HTTPS sense navegador», no «HTTP pla». Verificar TLS, aplicar límits de temps i bytes i restringir redireccions a l’origen permès. Un `</html>` no acredita una resposta íntegra després d’un error de transport: en l’MVP rebutjar-la i no posar-la a la memòria cau. No reintentar automàticament els 500 genèrics; limitar reintents transitoris dins d’un pressupost total i respectar `Retry-After`. Tractar HTML i concordances com a dades, no com a instruccions per al model.
- **Cortesia i dades.** Aplicar el límit de ritme a totes les operacions, incloses variants, reintents i fitxes; tenir en compte que diverses instàncies locals poden multiplicar peticions. Fer servir fragments curts. No conservar cookies, cossos sencers o consultes sensibles als logs. L’accés públic no és permís per a l’extracció o redistribució: contactar amb l’IEC abans de distribuir el servei o ampliar-ne substancialment l’ús.

## 5. Proves pendents, per ordre

| Prioritat | Prova | Condició d’acceptació |
|---|---|---|
| **P0** | Serialització i gramàtica | Cos exacte amb `*` literal, valors codificats un sol cop, `Content-Type` correcte i controls positius d’accents, majúscules, apòstrofs i buits. La negació amb opcionalitat queda fora del contracte fins que se’n verifiqui el suport, sense generalitzar el 500 d’un sol cas. |
| **P0** | Respostes buides, incompletes i d’error | Fixtures separades de zero legítim, patró alterat, 500, HTML truncat i total positiu sense files en una pàgina vàlida. Cap dels quatre últims casos no es publica com a `no_matches`. |
| **P0** | Pàgines i caducitat | Sense pèrdues quan el límit visible és inferior a 50; provar primera, intermèdia, última i fora d’abast. Rebutjar tokens caducats i detectar canvis incompatibles entre pàgines. Verificar més d’un patró abans d’adoptar una clau de deduplicació. |
| **P0 producte** | Cronologia | Captura amb trams i denominadors identificats, inclòs un tram de zero si el gràfic el proporciona. Comparar totals quan els trams cobreixen tot el mateix abast. Si un tram no apareix, no suposar que és zero. Provar també pèrdua del resultat remot i gràfic no disponible. |
| **P1** | Variants i interpretació | Provar des d’OpenCode amb dos models habilitats per a eines: original i esmena separats, citació i anys quan existeixin, i cap inferència automàtica d’«ús quotidià». Distingir «no he pogut consultar el corpus» de «no hi he trobat l’expressió». |
| **P2** | Funcions ajornades | Verificar els fluxos d’`obres`, filtres i col·locacions d’extrem a extrem abans d’exposar-los. Les coaparicions no són una mesura d’associació: qualsevol càlcul futur ha de definir la finestra, els marginals i les unitats comparables. |

Els recomptes exactes com **2.136** o **8** són expectatives de **fixtures datades**, no llindars de salut en directe. Conservar per fixture l’endpoint, els bytes de la petició pertinents, l’estat de transport conegut i la sortida esperada; usar extractes mínims o fixtures sintètiques a CI, sense dependre de `/tmp`. En proves en viu, optatives i limitades, separar una discrepància de format d’un canvi legítim de recompte. No repetir casos coneguts de 500 a cada prova.

**Decisió per avançar:** començar amb una cerca curta de frase, una resposta positiva i un zero validat. Després afegir el context i el gràfic cronològic al mateix resultat. Això permet demostrar el valor lingüístic del projecte abans d’estendre’l a tot el catàleg del CTILC.
