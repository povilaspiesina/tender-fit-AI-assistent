# Trys X ir y poros

Pilni struktūruoti įrašai yra [cases.json](cases.json). `X` sudaro dokumento tekstas (nurodytame `.txt` faile) ir konkretaus sintetinio kliento profilis (`cases.json` laukelyje `client_profile`). `y` yra rankiniu būdu numatytas atsakymas, su kuriuo Colab palygina faktinę modelio išvestį.

| Atvejis | X: dokumentas ir kliento profilis | y: laukiama ištrauka ir išvada |
| --- | --- | --- |
| 1. Reagentai | [Sintetinis pirkimas](synthetic_molecular_procurement.txt); kataloge PGR mišinys, DNR išskyrimo rinkinys, vanduo be nukleazių. | 1 dalis, 3 objektai; `aktualu` tolesnei peržiūrai; padengiama 1 dalis. |
| 2. LSMU | [Tikros techninės specifikacijos ištrauka](lsmu_spec_excerpt.txt); kataloge trietanolaminas, o ankstesniame tiekime buvo vazelinas. | 4 dalys, 11 objektų; `reikia_perziureti`, nes dabartinė pilnos dalies pasiūla nepatvirtinta. |
| 3. Šilutė | [Tikro skelbimo ištrauka](notice_10041864_excerpt.txt); kataloge tik molekulinės biologijos reagentai. | 1 dalis, 1 bendras stogo ir terasos **nuomos** objektas; `neaktualu`. |

Modelio atsakymo formuluotė gali skirtis nuo `y.reason`; automatinis palyginimas tikrina dalių ir objektų skaičių, sprendimo žymą bei padengiamų dalių sąrašą. Priežastį ir citatas reikia perskaityti rankiniu būdu.
