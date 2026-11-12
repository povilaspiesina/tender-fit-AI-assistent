"""Build the 1.3 notebooks: tender-lot relevance with Keras and TF Decision Forests.

Both notebooks share the same data-loading, feature and split code, so the two
models are trained and tested on identical rows. The private label table and
catalog vocabulary are read at run time and never embedded here.
"""

from __future__ import annotations

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "notebooks"


def new() -> dict:
    return {"nbformat": 4, "nbformat_minor": 5,
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                         "language_info": {"name": "python"}},
            "cells": []}


def md(nb, s):
    nb["cells"].append({"cell_type": "markdown", "metadata": {}, "source": s.strip() + "\n"})


def code(nb, s):
    nb["cells"].append({"cell_type": "code", "metadata": {}, "source": s.strip() + "\n",
                        "execution_count": None, "outputs": []})


def save(nb, name):
    (OUT / name).write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


DATA_MD = """
## Duomenys: kas yra `X` ir `y`

**Viena eilutė = viena viešojo pirkimo dalis.** Šaltinis: Europos Sąjungos oficialus [TED API](https://docs.ted.europa.eu/api/latest/index.html) (Lietuvos perkančiųjų organizacijų skelbimai apie pirkimą, eForms XML). Kiekvienai daliai išsaugoti pirkimo ID, dalies numeris, TED nuoroda ir atsisiuntimo laikas — faile `private/1_3_zymos.csv`.

- **`y`** — ar dalį verta perduoti molekulinės biologijos reagentų ir laboratorinių reikmenų tiekėjo peržiūrai (`1`) ar ne (`0`).
  **Svarbu:** šias žymas uždėjo **AI agentas** pagal privačius kliento katalogus ir rašytines taisykles (`labeler = claude_agentas`), o 42 iš pradžių neaiškios dalys priskirtos pagal spėjimą. Tai **ne žmogaus patvirtintas aukso standartas**. Todėl žemiau esantys rezultatai rodo, kaip gerai modeliai atkartoja šias žymas, o ne tikrą kliento sprendimą.
- **`X`** — tik tai, kas žinoma iš skelbimo prieš sprendimą:
  1. tekstas: dalies pavadinimas, perkamų objektų aprašymas ir pirkimo pavadinimas;
  2. BVPŽ (CPV) kodų požymiai;
  3. požymiai, apskaičiuoti lyginant su **dabartiniu kliento katalogu**: kiek dalies žodžių yra katalogo produktų pavadinimų žodyne (`private/1_3_katalogo_zodynas.json`, sudarytas tik iš pavadinimų, be kainų) ir kiek pataikoma į katalogo kategorijų raktinius žodžius.

**Nenaudojama kaip `X`:** agento užuominų stulpeliai, žymos priežastis, atrankos grupė (ji rodo, kaip pirkimas buvo surinktas, todėl nutekintų atsakymą) ir perkančioji organizacija.

**Ribos:** TED turi tik viršslenkstinius pirkimus; techninės specifikacijos dažnai yra CVP prieduose, todėl dalies aprašymas gali būti trumpas. Lentelėje nėra katalogo eilučių ar kainų.
"""

SETUP = r'''
import os, json, re, hashlib, random
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

SEED = 42
random.seed(SEED); np.random.seed(SEED)

PROJECT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
PRIVATE = Path(os.getenv("TENDER_FIT_PRIVATE_DIR", PROJECT / "private"))
LABELS_CSV = PRIVATE / "1_3_zymos.csv"
VOCAB_JSON = PRIVATE / "1_3_katalogo_zodynas.json"
assert LABELS_CSV.exists(), f"Nerastas {LABELS_CSV}. Nurodykite TENDER_FIT_PRIVATE_DIR."
assert VOCAB_JSON.exists(), f"Nerastas {VOCAB_JSON}. Paleiskite scripts/build_catalog_vocab.py."
'''

LOAD = r'''
raw = pd.read_csv(LABELS_CSV, dtype=str, encoding="utf-8-sig").fillna("")
raw = raw[raw["label"].isin(["0", "1"])].copy()
raw["y"] = raw["label"].astype(int)
raw["text"] = (raw["lot_title"] + " . " + raw["items_text"] + " . " + raw["procurement_title"]).str.lower()
print("Dalių:", len(raw), "| pirkimų:", raw.procurement_id.nunique())
print("Žymos:", raw.y.value_counts().to_dict())
print("Pirkimų su bent viena aktualia dalimi:", raw.loc[raw.y == 1, "procurement_id"].nunique())
print("Žymėtojai:", raw.labeler.value_counts().to_dict())
'''

FEATURES = r'''
catalog_vocab = set(json.loads(VOCAB_JSON.read_text(encoding="utf-8"))["token_doc_freq"])
TOKEN = re.compile(r"[a-ząčęėįšųūž][a-ząčęėįšųūž0-9\-]{2,}")

# Katalogo kategorijų raktiniai žodžiai (LT kamienai + EN). Sudaryti pagal katalogų kategorijas,
# ne pagal konkrečius pirkimus.
POSITIVE_GROUPS = {
    "kw_antikunai": ["antikūn", "antibod", "imunoglobulin"],
    "kw_elisa": ["elisa", "imunofermentin", "imunoanaliz"],
    "kw_pcr": ["pcr", "pgr", "polimeraz", "polymeras", "amplifik", "taq", "master mix", "atvirkštin"],
    "kw_fermentai": ["ferment", "enzym", "restrikc", "ligaz", "nukleaz"],
    "kw_nukleino": ["oligonukleot", "pradmen", "primer", "zond", "sirna", "sgrna", "dnr", "rnr", "nukleotid", "dntp", "dna", "rna"],
    "kw_sekoskaita": ["sekoskait", "sequenc", "bibliotek", "ngs"],
    "kw_baltymai": ["rekombinant", "baltym", "citokin", "protein", "peptid", "ląstelių linij"],
    "kw_terpes": ["terp", "medium", "agar", "mielių", "bakterijų augin"],
    "kw_plastikas": ["mėgintuvėl", "plokštel", "antgal", "pipeči", "pipet", "juostel", "krioviel"],
    "kw_reagentai": ["reagent", "molekulin", "genetin", "genomin"],
}
NEGATIVE_GROUPS = {
    "kw_klinika": ["analizator", "klinikin", "šlapim", "kraujo", "hematolog", "koaguliac", "diagnostin"],
    "kw_vaistai": ["vaist", "tablet", "injekc", "infuz", "vakcin"],
    "kw_med_priemones": ["švirkšt", "adat", "pirštin", "tvarst", "chirurg", "kateter", "kaukė"],
    "kw_chemija": ["rūgšt", "tirpikl", "etanol", "acetonitril", "druska", "chemin"],
    "kw_paslaugos": ["paslaug", "aptarnav", "remont", "priežiūr", "nuom"],
    "kw_iranga": ["įrang", "prietais", "aparat", "centrifug", "mikroskop", "spektrofotometr"],
}
CPV_PREFIXES = {"cpv_336965": "336965", "cpv_33696": "33696", "cpv_38437": "38437", "cpv_33793": "33793",
                "cpv_3314": "3314", "cpv_336": "336", "cpv_24": "24", "cpv_38": "38", "cpv_331": "331"}


def build_features(df):
    out = pd.DataFrame(index=df.index)
    tokens = df["text"].apply(lambda t: TOKEN.findall(t))
    out["n_tokens"] = tokens.apply(len)
    out["catalog_vocab_hits"] = tokens.apply(lambda ts: sum(t in catalog_vocab for t in ts))
    out["catalog_vocab_share"] = out.catalog_vocab_hits / out.n_tokens.clip(lower=1)
    for name, words in {**POSITIVE_GROUPS, **NEGATIVE_GROUPS}.items():
        out[name] = df["text"].apply(lambda t: sum(t.count(w) for w in words))
    out["kw_positive_total"] = out[list(POSITIVE_GROUPS)].sum(axis=1)
    out["kw_negative_total"] = out[list(NEGATIVE_GROUPS)].sum(axis=1)
    out["kw_positive_groups"] = (out[list(POSITIVE_GROUPS)] > 0).sum(axis=1)
    cpvs = df["cpv_codes"].str.split()
    out["n_cpv"] = cpvs.apply(len)
    for name, prefix in CPV_PREFIXES.items():
        out[name] = cpvs.apply(lambda codes: sum(c.startswith(prefix) for c in codes))
    out["n_lots_in_procurement"] = pd.to_numeric(df["daliu_is_viso"], errors="coerce").fillna(1)
    return out.astype("float32")


engineered = build_features(raw)
print("Inžinerinių požymių:", engineered.shape[1])
engineered.describe().T[["mean", "max"]].head(12)
'''

SPLIT = r'''
from sklearn.model_selection import StratifiedGroupKFold

# Padalijimas pagal pirkimo ID: visos vieno pirkimo dalys patenka į tą pačią aibę.
groups = raw["procurement_id"].values
outer = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=SEED)
rest_idx, test_idx = next(outer.split(raw, raw.y, groups))
inner = StratifiedGroupKFold(n_splits=4, shuffle=True, random_state=SEED)
tr, va = next(inner.split(raw.iloc[rest_idx], raw.y.iloc[rest_idx], groups[rest_idx]))
train_idx, val_idx = rest_idx[tr], rest_idx[va]

split = pd.Series("train", index=raw.index)
split.iloc[val_idx] = "val"; split.iloc[test_idx] = "test"
raw["split"] = split.values
summary = raw.groupby("split").agg(dalys=("y", "size"), aktualios=("y", "sum"),
                                   pirkimai=("procurement_id", "nunique"))
print(summary)
for a, b in [("train", "val"), ("train", "test"), ("val", "test")]:
    shared = set(raw.loc[raw.split == a, "procurement_id"]) & set(raw.loc[raw.split == b, "procurement_id"])
    assert not shared, f"Pirkimas patenka į {a} ir {b}"
SPLIT_FINGERPRINT = hashlib.sha1(",".join(raw.loc[raw.split == "test", "procurement_id"].sort_values()).encode()).hexdigest()[:10]
print("Testo aibės kontrolinė suma (turi sutapti abiejuose užrašiniuose):", SPLIT_FINGERPRINT)
'''

TFIDF = r'''
from sklearn.feature_extraction.text import TfidfVectorizer

# Simbolių n-gramos tinka lietuvių kalbos galūnėms. Žodynas mokomas TIK iš mokymo aibės.
tfidf = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=3, max_features=400, sublinear_tf=True)
tfidf.fit(raw.loc[raw.split == "train", "text"])
text_matrix = pd.DataFrame(tfidf.transform(raw["text"]).toarray().astype("float32"), index=raw.index,
                           columns=[f"tfidf_{i:03d}" for i in range(len(tfidf.vocabulary_))])
X_all = pd.concat([engineered, text_matrix], axis=1)
y_all = raw["y"].values
masks = {s: (raw.split == s).values for s in ["train", "val", "test"]}
X = {s: X_all[m] for s, m in masks.items()}
y = {s: y_all[m] for s, m in masks.items()}
print("Požymių iš viso:", X_all.shape[1], "=", engineered.shape[1], "inžinerinių +", text_matrix.shape[1], "teksto")
'''

BASELINE = r'''
from sklearn.metrics import (classification_report, confusion_matrix, precision_recall_fscore_support,
                             average_precision_score, accuracy_score)

def report(name, y_true, y_pred, y_score=None):
    p, r, f, _ = precision_recall_fscore_support(y_true, y_pred, average="binary", zero_division=0)
    row = {"modelis": name, "accuracy": accuracy_score(y_true, y_pred), "precision_1": p, "recall_1": r, "f1_1": f,
           "praleista_aktualiu": int(((y_true == 1) & (y_pred == 0)).sum()),
           "klaidingai_aktualiu": int(((y_true == 0) & (y_pred == 1)).sum())}
    if y_score is not None:
        row["PR_AUC"] = average_precision_score(y_true, y_score)
    return row

# Paprasta bazinė taisyklė: daugiau katalogo kategorijų raktinių žodžių nei neigiamų.
def rule(features):
    return ((features.kw_positive_total > features.kw_negative_total) |
            ((features.cpv_336965 > 0) & (features.kw_negative_total == 0))).astype(int).values

baseline_row = report("Bazinė raktinių žodžių taisyklė", y["test"], rule(X["test"]))
majority_row = report("Visada 0 (dauguma)", y["test"], np.zeros_like(y["test"]))
pd.DataFrame([majority_row, baseline_row]).round(3)
'''

ERRORS = r'''
def show_errors(pred, title):
    test = raw[masks["test"]].assign(pred=pred)
    missed = test[(test.y == 1) & (test.pred == 0)]
    false_pos = test[(test.y == 0) & (test.pred == 1)]
    print(f"{title}: praleistos aktualios dalys ({len(missed)})")
    for _, r in missed.iterrows():
        print(" -", r.lot_title[:90], "|", r.source_url)
    print(f"\n{title}: klaidingai aktualiomis pažymėtos dalys ({len(false_pos)}, rodomos iki 8)")
    for _, r in false_pos.head(8).iterrows():
        print(" -", r.lot_title[:90])
'''

# ---------------------------------------------------------------- Keras notebook
nn = new()
md(nb := nn, """
# 1.3 — Pirkimo dalies aktualumas: „TensorFlow / Keras“ neuroninis tinklas

**Pritaikyta iš kurso užrašinio** [AdventureWorks DW using TensorFlow](https://colab.research.google.com/drive/1LLFM2Ba5jAZSna8JnS44frwSLW9mx5As?usp=sharing).

**Ką daro originalas.** „AdventureWorks“ klientų lentelėje `BikeBuyer` yra `y` (ar klientas pirko dviratį), o kiti stulpeliai — `X`. Kodas pašalina identifikatorius, padalija duomenis į mokymo / validavimo / testavimo dalis, normalizuoja skaitinius ir užkoduoja kategorinius požymius, sujungia juos ir moko kelis `Dense` sluoksnius dvejetainei klasifikacijai, tada vertina, išsaugo ir iš naujo įkelia modelį.

**Kas pakeista.** Vietoje kliento pirkėjo — **viešojo pirkimo dalis**, o `y` — ar ją verta perduoti kliento peržiūrai. Dvejetainė klasifikacija ir `Dense` tinklas išlieka. Pridėta: padalijimas **pagal pirkimo ID** (kad to paties pirkimo dalys nepatektų į mokymą ir testą), klasių svoriai (aktualių dalių mažuma), paprasta bazinė taisyklė palyginimui ir praleistų aktualių dalių analizė.

Šis modelis yra **laboratorinis klasifikatorius**, ne viso produkto tinkamumo įrodymas. Lygiai tie patys duomenys ir padalijimas naudojami sprendimų miško užrašinyje.
""")
md(nn, DATA_MD)
md(nn, "## 1. Aplinka ir privatūs failai\n\nUžrašinis vykdomas lokaliai (arba „Colab“ su įkeltu `private/` aplanku). Privatūs failai į viešą saugyklą nekeliami.")
code(nn, SETUP + "\nimport tensorflow as tf\ntf.keras.utils.set_random_seed(SEED)\nprint('TensorFlow', tf.__version__)")
md(nn, "## 2. Įkelti pažymėtas dalis")
code(nn, LOAD)
md(nn, "## 3. Požymiai `X`\n\n`build_features` kiekvienai daliai suskaičiuoja: kiek žodžių yra kliento katalogo žodyne, kiek pataikoma į teigiamų (katalogo kategorijų) ir neigiamų (klinika, vaistai, medicinos priemonės, chemija, įranga) raktinių žodžių grupes, ir BVPŽ kodų prefiksus. Tai tie patys požymiai abiem modeliams.")
code(nn, FEATURES)
md(nn, "## 4. Mokymo / validavimo / testavimo padalijimas pagal pirkimą\n\n`StratifiedGroupKFold` sudaro grupes pagal `procurement_id` ir stengiasi išlaikyti panašią aktualių dalių proporciją. Testo aibė naudojama **tik galutiniam įvertinimui**. Kontrolinė suma leidžia patikrinti, kad miško užrašinyje testo aibė ta pati.")
code(nn, SPLIT)
md(nn, "## 5. Teksto požymiai\n\nTF-IDF simbolių n-gramos paverčia tekstą skaičiais. Žodynas sudaromas **tik iš mokymo** dalių, kad testo tekstas nepaveiktų požymių.")
code(nn, TFIDF)
md(nn, "## 6. Bazinė taisyklė\n\nPrieš mokant modelį verta žinoti, ką pasiekia paprasta taisyklė. Jei modelis jos neaplenkia, sudėtingumas nepasiteisina. Kadangi neaktualių dalių dauguma, `accuracy` gali būti aukštas net modeliui, kuris visada sako `0` — todėl svarbiausi yra aktualios klasės `recall` ir praleistų aktualių dalių skaičius.")
code(nn, BASELINE)
md(nn, """
## 7. Neuroninis tinklas

- `Normalization` sluoksnis išmoksta kiekvieno požymio vidurkį ir dispersiją **iš mokymo aibės** (atitinka originalo skaitinių požymių normalizavimą).
- `Dense(32, relu)` jungia požymius, `Dropout(0.3)` mažina įsiminimą, `Dense(1, sigmoid)` grąžina tikimybę, kad dalis aktuali.
- `class_weight` suteikia didesnį svorį retesnei aktualiai klasei.
- `EarlyStopping` stebi validavimo nuostolį ir grąžina geriausius svorius.
""")
code(nn, r'''
from tensorflow.keras import layers
from sklearn.utils.class_weight import compute_class_weight

normalizer = layers.Normalization()
normalizer.adapt(X["train"].values)

def build_model():
    inputs = tf.keras.Input(shape=(X_all.shape[1],), name="pozymiai")
    x = normalizer(inputs)
    x = layers.Dense(32, activation="relu")(x)
    x = layers.Dropout(0.3)(x)
    outputs = layers.Dense(1, activation="sigmoid", name="aktualumas")(x)
    model = tf.keras.Model(inputs, outputs, name="pirkimo_dalies_nn")
    model.compile(optimizer=tf.keras.optimizers.Adam(1e-3), loss="binary_crossentropy",
                  metrics=[tf.keras.metrics.AUC(curve="PR", name="pr_auc"), tf.keras.metrics.Recall(name="recall")])
    return model

model = build_model()
model.summary()
weights = compute_class_weight("balanced", classes=np.array([0, 1]), y=y["train"])
class_weight = {0: float(weights[0]), 1: float(weights[1])}
print("Klasių svoriai:", class_weight)
''')
code(nn, r'''
history = model.fit(X["train"].values, y["train"], validation_data=(X["val"].values, y["val"]),
                    epochs=200, batch_size=32, class_weight=class_weight, verbose=0,
                    callbacks=[tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=15,
                                                                restore_best_weights=True)])
print("Epochų:", len(history.history["loss"]))
pd.DataFrame(history.history)[["loss", "val_loss"]].plot(title="Nuostolis pagal epochą"); plt.show()
''')
md(nn, "## 8. Slenksčio pasirinkimas validavimo aibėje\n\nNumatytasis slenkstis 0,5 nebūtinai tinka. Kadangi svarbiausia nepraleisti aktualių dalių, validavimo aibėje parenkamas **aukščiausias slenkstis, kuriam recall ≥ 0,9**. Testo aibė šiam pasirinkimui nenaudojama. Validavimo aibėje aktualių dalių nedaug, todėl slenkstis yra apytikslis.")
code(nn, r'''
val_score = model.predict(X["val"].values, verbose=0).ravel()
candidates = np.round(np.arange(0.05, 0.96, 0.05), 2)
val_recall = [((val_score >= t) & (y["val"] == 1)).sum() / max(1, (y["val"] == 1).sum()) for t in candidates]
ok = [t for t, r in zip(candidates, val_recall) if r >= 0.9]
THRESHOLD = float(max(ok)) if ok else 0.5
print("Pasirinktas slenkstis:", THRESHOLD)
''')
md(nn, "## 9. Galutinis įvertinimas testo aibėje")
code(nn, r'''
test_score = model.predict(X["test"].values, verbose=0).ravel()
rows = [majority_row, baseline_row,
        report("Keras NN (slenkstis 0,5)", y["test"], (test_score >= 0.5).astype(int), test_score),
        report(f"Keras NN (slenkstis {THRESHOLD})", y["test"], (test_score >= THRESHOLD).astype(int), test_score)]
results = pd.DataFrame(rows).round(3)
display(results)
nn_pred = (test_score >= THRESHOLD).astype(int)
print(classification_report(y["test"], nn_pred, target_names=["neaktualu", "aktualu"], zero_division=0))
cm = confusion_matrix(y["test"], nn_pred)
print("Painiavos matrica (eilutės = tikra, stulpeliai = prognozė):\n", cm)
PRIVATE.joinpath("rezultatai").mkdir(exist_ok=True)
results.assign(test_fingerprint=SPLIT_FINGERPRINT).to_csv(PRIVATE / "rezultatai" / "1_3_nn.csv", index=False)
''')
md(nn, "## 10. Klaidos: kurias aktualias dalis modelis praleido?\n\nSvarbiausia rizika — klaidingai atmestas aktualus pirkimas. Šias dalis žmogus turėtų patikrinti pagal TED nuorodą.")
code(nn, ERRORS + "\nshow_errors(nn_pred, 'Keras NN')")
md(nn, "## 11. Išsaugoti ir iš naujo įkelti modelį\n\nKaip originale: išsaugotas modelis turi duoti tas pačias prognozes. Modelis saugomas `private/` aplanke, nes išmoktas iš privačių žymų.")
code(nn, r'''
path = PRIVATE / "modeliai" / "1_3_pirkimo_dalies_nn.keras"
path.parent.mkdir(exist_ok=True)
model.save(path)
reloaded = tf.keras.models.load_model(path)
same = np.allclose(reloaded.predict(X["test"].values, verbose=0).ravel(), test_score, atol=1e-6)
print("Įkeltas modelis duoda tas pačias prognozes:", same)
example = raw[masks["test"]].iloc[0]
print("Pavyzdys:", example.lot_title[:80], "→ tikimybė", round(float(test_score[0]), 3), "| žyma", example.y)
''')
md(nn, "## 12. Išvados\n\nSkaičiai aukščiau yra šio paleidimo rezultatai. Jų interpretacija pateikta pristatymo gide (`docs/1_3_1_5_pristatymo_gidas.md`). Pagrindinės ribos: mažai skirtingų aktualių pirkimų, agento (ne žmogaus) žymos ir trumpi TED aprašymai.")
save(nn, "1_3_pirkimo_daliu_neuroninis_tinklas.ipynb")

# ---------------------------------------------------------------- TF-DF notebook
df_nb = new()
md(df_nb, """
# 1.3 — Pirkimo dalies aktualumas: „TensorFlow Decision Forests“

**Pritaikyta iš kurso užrašinio** [AdventureWorks DW using TensorFlow Decision Forests](https://colab.research.google.com/drive/1zE7b6UlSOreWsgD7lGQOVfEki_xTRDAX).

**Ką daro originalas.** Tą pačią „AdventureWorks“ `BikeBuyer` užduotį sprendžia `tensorflow_decision_forests`: lentelę paverčia TF-DF duomenų rinkiniu, moko `RandomForestModel`, vertina tikslumą, rodo mokymo žurnalą, požymių svarbą, vieną medį ir vieno pavyzdžio prognozę.

**Kas pakeista.** Naudojami **lygiai tie patys** duomenys, požymiai ir mokymo / validavimo / testavimo padalijimas kaip neuroniniame tinkle (patikrinama kontroline suma). Miškui nereikia normalizavimo. Pridėta bazinė taisyklė, slenksčio pasirinkimas validavimo aibėje ir praleistų aktualių dalių analizė.
""")
md(df_nb, DATA_MD)
md(df_nb, "## 1. Aplinka ir privatūs failai\n\nTF-DF turi griežtą suderinamumą su „TensorFlow“ versija; žr. [žinomas problemas](https://www.tensorflow.org/decision_forests/known_issues).")
code(df_nb, SETUP + "\nimport tensorflow as tf\nimport tensorflow_decision_forests as tfdf\nprint('TensorFlow', tf.__version__, '| TF-DF', tfdf.__version__)")
md(df_nb, "## 2. Įkelti pažymėtas dalis")
code(df_nb, LOAD)
md(df_nb, "## 3. Tie patys požymiai `X`")
code(df_nb, FEATURES)
md(df_nb, "## 4. Tas pats padalijimas pagal pirkimą")
code(df_nb, SPLIT)
md(df_nb, "## 5. Tie patys teksto požymiai")
code(df_nb, TFIDF)
md(df_nb, "## 6. Bazinė taisyklė")
code(df_nb, BASELINE)
md(df_nb, """
## 7. Atsitiktinis miškas

`pd_dataframe_to_tf_dataset` paverčia lentelę TF-DF formatu. `RandomForestModel` moko 300 sprendimų medžių; kiekvienas mato atsitiktinę eilučių ir požymių imtį, o galutinė prognozė — medžių balsų vidurkis. Klasių disbalansą kompensuojame pavyzdžių svoriais (tie patys kaip neuroniniame tinkle). Validavimo aibė naudojama slenksčiui parinkti.
""")
code(df_nb, r'''
from sklearn.utils.class_weight import compute_class_weight

weights = compute_class_weight("balanced", classes=np.array([0, 1]), y=y["train"])
def to_tf(split_name, with_weight=False):
    frame = X[split_name].copy()
    frame.columns = [c.replace("-", "_") for c in frame.columns]
    frame["y"] = y[split_name]
    if with_weight:
        frame["w"] = np.where(frame.y == 1, weights[1], weights[0]).astype("float32")
        return tfdf.keras.pd_dataframe_to_tf_dataset(frame, label="y", weight="w")
    return tfdf.keras.pd_dataframe_to_tf_dataset(frame, label="y")

train_tf, val_tf, test_tf = to_tf("train", True), to_tf("val"), to_tf("test")
forest = tfdf.keras.RandomForestModel(num_trees=300, random_seed=SEED, verbose=0)
forest.fit(train_tf, verbose=0)
print("Miškas išmokytas, medžių:", forest.make_inspector().num_trees())
''')
md(df_nb, "## 8. Mokymo žurnalas ir požymių svarba\n\nOut-of-bag (OOB) įvertinimas naudoja mokymo eilutes, kurių konkretus medis nematė. Požymių svarba parodo, į kuriuos požymius miškas dažniausiai remiasi; tai nėra priežastinis įrodymas.")
code(df_nb, r'''
inspector = forest.make_inspector()
logs = inspector.training_logs()
plt.plot([l.num_trees for l in logs], [l.evaluation.accuracy for l in logs])
plt.xlabel("Medžių skaičius"); plt.ylabel("OOB accuracy"); plt.title("Mokymo žurnalas"); plt.show()
importance = inspector.variable_importances()["NUM_AS_ROOT"]
ngram = {c: repr(n) for c, n in zip(text_matrix.columns, tfidf.get_feature_names_out())}  # tarpas = žodžio riba
top = pd.DataFrame([(v[0].name, ngram.get(v[0].name, ""), v[1]) for v in importance[:15]],
                   columns=["požymis", "TF-IDF n-grama", "kiek kartų šaknyje"])
top
''')
md(df_nb, "## 9. Vieno medžio fragmentas\n\nMiškas susideda iš 300 medžių; vienas medis rodomas tik iliustracijai.")
code(df_nb, r'''
tree_text = inspector.extract_tree(tree_idx=0)
print(str(tree_text)[:1500])
''')
md(df_nb, "## 10. Slenksčio pasirinkimas validavimo aibėje (taip pat kaip NN)")
code(df_nb, r'''
val_score = forest.predict(val_tf, verbose=0).ravel()
candidates = np.round(np.arange(0.05, 0.96, 0.05), 2)
val_recall = [((val_score >= t) & (y["val"] == 1)).sum() / max(1, (y["val"] == 1).sum()) for t in candidates]
ok = [t for t, r in zip(candidates, val_recall) if r >= 0.9]
THRESHOLD = float(max(ok)) if ok else 0.5
print("Pasirinktas slenkstis:", THRESHOLD)
''')
md(df_nb, "## 11. Galutinis įvertinimas ir palyginimas su neuroniniu tinklu")
code(df_nb, r'''
test_score = forest.predict(test_tf, verbose=0).ravel()
rows = [majority_row, baseline_row,
        report("TF-DF miškas (slenkstis 0,5)", y["test"], (test_score >= 0.5).astype(int), test_score),
        report(f"TF-DF miškas (slenkstis {THRESHOLD})", y["test"], (test_score >= THRESHOLD).astype(int), test_score)]
df_pred = (test_score >= THRESHOLD).astype(int)
print(classification_report(y["test"], df_pred, target_names=["neaktualu", "aktualu"], zero_division=0))
print("Painiavos matrica (eilutės = tikra, stulpeliai = prognozė):\n", confusion_matrix(y["test"], df_pred))
results = pd.DataFrame(rows).round(3)
PRIVATE.joinpath("rezultatai").mkdir(exist_ok=True)
results.assign(test_fingerprint=SPLIT_FINGERPRINT).to_csv(PRIVATE / "rezultatai" / "1_3_tfdf.csv", index=False)
nn_file = PRIVATE / "rezultatai" / "1_3_nn.csv"
if nn_file.exists():
    nn_results = pd.read_csv(nn_file)
    assert (nn_results.test_fingerprint.astype(str) == SPLIT_FINGERPRINT).all(), "Testo aibės nesutampa!"
    results = pd.concat([results, nn_results[nn_results.modelis.str.startswith("Keras")].drop(columns="test_fingerprint")])
results.reset_index(drop=True)
''')
md(df_nb, "## 12. Praleistos aktualios dalys")
code(df_nb, ERRORS + "\nshow_errors(df_pred, 'TF-DF miškas')")
md(df_nb, "## 13. Išsaugoti, įkelti ir prognozuoti vieną pavyzdį")
code(df_nb, r'''
path = PRIVATE / "modeliai" / "1_3_pirkimo_dalies_tfdf"
path.parent.mkdir(exist_ok=True)
forest.save(path)
import tf_keras  # TF-DF modeliai yra Keras 2 (tf_keras) modeliai
reloaded = tf_keras.models.load_model(path)
same = np.allclose(reloaded.predict(test_tf, verbose=0).ravel(), test_score, atol=1e-5)
print("Įkeltas modelis duoda tas pačias prognozes:", same)
example = raw[masks["test"]].iloc[0]
print("Pavyzdys:", example.lot_title[:80], "→ tikimybė", round(float(test_score[0]), 3), "| žyma", example.y)
''')
md(df_nb, "## 14. Išvados\n\nAbu modeliai mokyti ir testuoti su ta pačia testo aibe. Interpretacija — pristatymo gide (`docs/1_3_1_5_pristatymo_gidas.md`).")
save(df_nb, "1_3_pirkimo_daliu_sprendimu_miskas.ipynb")
print("Parašyti du 1.3 užrašiniai")
