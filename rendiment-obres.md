# Paginació local de les obres del CTILC

Mesura local del 22/11/2026 amb `.venv`: a partir de
`tests/fixtures/obres_resultats.html`, s'han repetit les tres files 500
vegades i s'ha ajustat el comptador a 1.500 obres (334.987 bytes). Les
respostes són sintètiques, no mesures del servei CTILC.

Amb `HttpClient._one_request` substituït i deu pàgines de 20 obres
(`offset` de 0 a 180), la mediana de cinc execucions és **1.286,6 ms abans**
i **127,9 ms després**. Cada execució fa un enviament simulat i té nou
encerts de cau HTTP. L'abans fa servir el mateix codi però executa
`parse_works` a cada pàgina; el després reutilitza l'anàlisi de la resposta
cachejada. Els temps depenen de la màquina i no són un llindar de CI.

La cau derivada guarda com a màxim quatre anàlisis i només les reutilitza si
el token de la resposta cachejada coincideix. Una resposta renovada o
`no-store` invalida l'anàlisi anterior. Les proves cobreixen la paginació
completa i parcial, l'eco, els avisos, les renovacions i `no-store`.
