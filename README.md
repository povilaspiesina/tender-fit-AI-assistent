# Viešųjų pirkimų aktualumo asistentas

[Atidaryti prototipą Google Colab](https://colab.research.google.com/github/povilaspiesina/tender-fit-AI-assistent/blob/main/notebooks/pirkimu_aktualumo_prototipas.ipynb)

VILNIUS TECH kurso „Gilusis mokymas naudojant TensorFlow“ 1 darbo 1.1–1.2.2 dalių prototipas. Sistema iš pirkimo skelbimo ir jo priedų ištraukia perkamus objektus, palygina juos su tiekėjo (kliento) profiliu ir pateikia **preliminarų** aktualumo vertinimą su šaltinio nuorodomis. Sprendimas nereiškia, kad tiekėjas gali teikti pasiūlymą ar atitinka visas pirkimo sąlygas.

## Kas pateikta

| Kurso dalis | Rezultatas |
| --- | --- |
| 1.1 | [Sistemos aprašas](docs/projektas.md), [ChatGPT projektavimo užklausa](prompts/projektavimo_promptas.md), [PlantUML](diagrams/procesas.puml) ir [Mermaid](diagrams/procesas.mmd) diagramos. |
| 1.2.1 | [Trys aiškios X, y poros](data/xy_examples.md), [struktūruoti scenarijai](data/cases.json), jų šaltinio ištraukos ir [testavimo užklausos](prompts/testavimo_promptai.md). |
| 1.2.2 | [Google Colab užrašinė](notebooks/pirkimu_aktualumo_prototipas.ipynb): failų priėmimas, teksto ištraukimas, struktūruoti Gemini API atsakymai, šaltinio patikra, vertinimas ir rezultatų lentelės. |
| 1.3 | Ar pirkimo dalį verta perduoti tiekėjo peržiūrai: [Keras neuroninis tinklas](notebooks/1_3_pirkimo_daliu_neuroninis_tinklas.ipynb) ir [TF Decision Forests](notebooks/1_3_pirkimo_daliu_sprendimu_miskas.ipynb) su tais pačiais 380 TED pirkimų dalių duomenimis ir tuo pačiu padalijimu pagal pirkimą. |
| 1.4 | [CNN laboratorinių reikmenų nuotraukoms](notebooks/1_4_laboratoriniu_reikmenu_cnn.ipynb) (antgaliai, mikromėgintuvėliai, mikroplokštelės). |
| 1.5 | [Iš anksto išmokyti vaizdų modeliai](notebooks/1_5_reikmenu_isankstiniai_modeliai.ipynb) ir [perkeltinis mokymas](notebooks/1_5_reikmenu_perkeltinis_mokymas.ipynb) su tais pačiais 1.4 vaizdais. |

1.3–1.5 užrašiniai įvykdyti lokaliai. Jų įvestys (pažymėtos pirkimų dalys, privataus katalogo žodynas, nuotraukos) laikomos `private/` ir į saugyklą nekeliamos, todėl iš GitHub jų iš naujo paleisti negalima. **1.3 žymas uždėjo AI agentas, ne žmogus.** 1.4–1.5 nuotraukos yra viešos (Wikimedia Commons, Openverse), ne asmeniškai darytos; autoriai ir licencijos: [data/1_4_vaizdu_saltiniai.csv](data/1_4_vaizdu_saltiniai.csv). Užrašinius generuoja `scripts/build_1_3_tender_lot_notebooks.py` ir `scripts/build_1_4_1_5_labware_notebooks.py`.

## Paleidimas Google Colab

1. Atidarykite `notebooks/pirkimu_aktualumo_prototipas.ipynb` per Google Colab.
2. Google AI Studio sukurkite Gemini API raktą. Colab kairėje atverkite **Secrets**, pridėkite `GEMINI_API_KEY` ir suteikite užrašinei prieigą. **Rakto neįrašykite į kodą ar GitHub.**
3. Vykdykite langelius iš eilės iki demonstracinių scenarijų rezultatų lentelės. Bibliotekų diegimo langelį paleiskite pirmą, o po diegimo, jei Colab to prašo, iš naujo paleiskite aplinką. Demonstraciniai scenarijai įterpti į užrašinę, todėl galima paleisti be papildomų failų. Vienas pirkimas yra sintetinis; du kiti paremti pateiktais realiais dokumentais. Tiekėjų profiliai ir pirkimų istorija yra **sintetiniai**.
4. Norėdami tikrinti visą dokumentą, paskutinėje dalyje įkelkite PDF arba DOCX. Šilutės pirkimo skelbimas ir LSMU pirkimo sąlygos yra atskiri pirkimai; jų nejunkite į vieną užklausą. Jei norite vertinti visus konkretaus pirkimo priedus, įkelkite juos kartu.
5. Pakeiskite demonstracinį profilį tikru kliento katalogu, veiklos ribomis ir, jei turite, ankstesnių pirkimų istorija. Iki tol vertinimas **nėra pritaikytas realiam klientui**. Istorija yra papildomas signalas, bet neįrodo, kad prekė tebėra kataloge.

## Duomenų kilmė ir ribos

- Šilutės pirkimo [skelbimas](https://viesiejipirkimai.lt/epps/cft/prepareViewCfTWS.do?resourceId=10041864) ir [pridėtų dokumentų sąrašas](https://viesiejipirkimai.lt/epps/cft/listContractDocuments.do?resourceId=10041864). Pateiktame PDF yra aukšto lygio nuomos aprašymas, bet ne visi techniniai parametrai.
- Naudotojo pateiktame LSMU DOCX 1 priede yra 4 pirkimo dalys ir 11 prekių. Pasiūlymo formoje yra preliminarūs kiekiai. `data/lsmu_spec_excerpt.txt` yra ištrauka bandymams, o ne visas pirkimo dokumentas.
- `data/cases.json` esantys tiekėjų profiliai ir pirkimų istorija yra sugalvoti demonstracijai. `data/synthetic_molecular_procurement.txt` taip pat yra sintetinis. Laukiami atsakymai nurodo preliminarų tinkamumą **peržiūrai**, ne konkurso atitiktį.
- Modelis gali klysti, todėl išvestis tikrinama pagal originalius dokumentus. Nežinoma arba dokumentuose nepateikta informacija žymima kaip trūkstama; ji nėra spėjama.

## Techniniai sprendimai

Colab naudoja `google-genai` ir Pydantic struktūruotai JSON išvesčiai, `pypdf` PDF tekstui bei `python-docx` DOCX pastraipoms ir lentelėms. API naudojimas grindžiamas [oficialiu Gemini pradžios vadovu](https://ai.google.dev/gemini-api/docs/get-started) ir [API raktų rekomendacijomis](https://ai.google.dev/gemini-api/docs/api-key).
