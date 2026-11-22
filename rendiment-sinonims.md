# Construcció de l'índex de sinònims

Mesura local del 22/11/2026, amb Python de `.venv`, les dades de Softcatalà
`0922f7d6409914cdc4c311f9be3b98282964938f` (1.046.954 bytes) i 12.597
grups. L'abans és `llengua_mcp/sinonims.py` de `HEAD`; el després incorpora
la cau LRU local de 8.192 entrades i evita normalitzar notes buides.

En cinc càrregues de cada versió, alternades, amb instàncies noves i
`perf_counter()`, les medianes van ser **2,076 s abans** i **1,821 s després**
(aproximadament un 12 % menys). Les mesures són locals i sensibles a la
càrrega de la màquina; no mesuren l'arrencada completa per stdio.

En una càrrega separada de cada versió, `tracemalloc` va registrar un pic de
**37,57 MiB abans** i **38,43 MiB després**; la memòria retinguda en acabar
era de **34,75 MiB** en tots dos casos. Són assignacions Python, no el consum
total del procés. La cau és acotada i no queda associada a l'índex un cop
acaba la càrrega.

Les proves comparen grups, índexs i consultes amb i sense memoització, incloent
ordre, accents, notes i antònims; també comproven que la cau no es reté.
