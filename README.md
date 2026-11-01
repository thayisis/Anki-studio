# Anki Studio

Application Streamlit gratuite pour convertir des PDF balisés en notes Anki, avec comparaison au document original. Utilisation dans un navigateur, notamment Safari sur iPad ; aucune installation locale n’est nécessaire pour l’utilisateur de l’application hébergée.

## Workflow

1. Importer un PDF contenant des marqueurs textuels `CARTE`, `CARTE CLOZE` ou `CARTE OCCLUSION` sur des lignes distinctes.
2. Comparer chaque note au PDF : titre, phrases complètes, retraits, images et ordre. Une note peut couvrir plusieurs pages.
3. Corriger le titre et les sections parentes en texte simple. Le tableau du verso permet de corriger chaque ligne, sa puce et son retrait sans écrire de HTML. Les images restent en place. « Replacer aussi le titre source au début du verso » permet de récupérer un premier paragraphe pris pour titre.
4. Valider les notes individuellement. Toute correction annule leur validation et l’ancien téléchargement.
5. Exporter les notes **validées et compatibles**. Les autres sont listées avec leur motif d’exclusion. Les compteurs distinguent notes, cartes Anki générées et notes en attente.
6. Télécharger aussi le dossier source ZIP pour conserver le PDF original, toutes les notes (y compris exclues), les coordonnées, les images et les zones PDF.

### Basic et Cloze

Les Basic utilisent les champs natifs `Front` / `Back`. Un verso vide (ou ne contenant que des puces sans texte ni image) est explicitement exclu, même après validation. Corriger le titre et utiliser la récupération du titre source au verso avant de revalider ; cette récupération ne peut pas dupliquer le texte lors d’enregistrements successifs. Les titres distincts ne sont pas recopiés inutilement au verso. Pour une définition isolée, le mot-concept du recto peut aussi figurer dans la phrase complète au verso afin de préserver son libellé original.

Les Cloze utilisent un modèle natif Anki de type Cloze (`Text` / `Extra`, filtre `{{cloze:Text}}`). Le marqueur `CARTE CLOZE` ne précise pas les mots à masquer. Les quatre passages des cours fournis ont maintenant des suppressions littérales proposées et modifiables (voir [CARD_CORRECTIONS.md](CARD_CORRECTIONS.md)). Pour les autres passages, l’utilisateur peut saisir `{{c1::texte}}`, `{{c2::autre texte::indice}}`, etc. dans le titre ou une ligne. Les suppressions vides, incomplètes ou imbriquées sont refusées explicitement. Un même numéro produit une seule carte ; plusieurs numéros produisent plusieurs cartes.

L’export ne laisse jamais une Occlusion ou une Cloze incomplète bloquer les Basic validées. Chaque archive produite est contrôlée avant téléchargement : base SQLite, nombre de notes/cartes, types des modèles, noms des champs, rectos/versos, numéros de Cloze et contenu exact des médias.

### Occlusion d’image : limitation explicite

**L’application n’exporte pas encore les huit Occlusions du cours.** Une image statique n’est pas présentée comme une Occlusion native. Les cartes et leurs images sont détectées, montrées et préservées dans le dossier source, même sans texte.

Le [modèle officiel Anki](https://github.com/ankitects/anki/blob/main/rslib/src/image_occlusion/notetype.rs) utilise un type Cloze spécialisé, l’identification `OriginalStockKind::ImageOcclusion`, des champs Occlusions/Image/Header/BackExtra/Comments, et `anki.imageOcclusion.setup()` pour interpréter des masques. `genanki` ne fournit pas ce contrat natif complet et les marqueurs PDF ne contiennent pas les régions à masquer. L’étude [NATIVE_OCCLUSION.md](NATIVE_OCCLUSION.md) démontre un aller-retour réellement natif avec le moteur officiel Anki, deux masques et deux cartes synthétiques. Ce prototype reste séparé du chemin d’export de l’application ; l’éditeur de masques pour les huit schémas reste à intégrer.

Workflow sûr : télécharger le ZIP, ouvrir une image de `media/` ou une zone `cards/NNN/source-N.png` dans un client Anki compatible Occlusion native, dessiner les masques et vérifier la carte. Cette étape dépend des fonctions du client Anki ; elle n’est pas automatisée par l’application web. L’application reste gratuite, mais ce document ne promet pas qu’un client iPad particulier propose gratuitement l’édition d’occlusions.

## Extraction et limites

Le moteur est séparé en étapes dans `engine.py` : extraction des caractères/coordonnées/images, détection globale des limites, association des puces séparées, identification prudente des titres, niveaux selon la position horizontale du **texte**, association des images, puis HTML. `exporter.py` gère l’éligibilité, les archives Anki et la sauvegarde des sources.

- Chaque marqueur donne une entrée, même vide ou composée uniquement d’images. Une entrée sans titre nécessite une correction.
- Le texte extrait n’est ni résumé, ni traduit, ni corrigé. Les caractères `®`, `©`, etc. ne sont plus supprimés. Les glyphes Wingdings reconnus comme puces peuvent être traités comme tels.
- Les caractères plus petits ou décalés (notamment le petit « 2 » de la formule O2 du PDF de biologie) conservent leurs tailles et positions relatives en HTML, sans réécriture de leurs caractères. Si le texte de la ligne est corrigé, les anciennes tailles ne sont pas appliquées au nouveau texte : vérifier les indices/exposants après édition.
- Les lignes physiques restent distinctes au verso. Une continuation géométriquement probable est marquée dans les données ; on ne fusionne pas des puces successives. Les retraits PDF restent visibles, sans limite à trois niveaux.
- Seuls des titres avec preuve typographique ou un plan de puces établi par les retraits peuvent donner du contexte ; les phrases précédentes ne sont pas utilisées arbitrairement. Le premier paragraphe et les parents proposés doivent être confirmés. La structure sémantique ne peut pas être garantie automatiquement.
- Images et schémas vectoriels sont conservés dans l’ordre géométrique, avec leurs transformations et superpositions visibles. Un média très volumineux est limité à 16 mégapixels avec avertissement. Le PDF original est conservé dans le ZIP.
- Les colonnes, rotations, superpositions et puces isolées sont signalées lorsqu’elles sont détectées. L’ordre géométrique n’est pas une garantie d’ordre sémantique pour tous les documents.
- Les PDF scannés sans couche texte nécessitent un OCR, non implémenté. Le décodage d’une police PDF incorrecte peut produire des caractères incertains. La comparaison visuelle et le PDF source restent indispensables ; **la fidélité automatique à 100 % n’est pas démontrée**.
- Le PDF est envoyé au serveur Streamlit lors de l’import. Aucune API d’IA ni service payant n’est utilisé. Les PDF privés de test ne doivent pas être ajoutés au dépôt.

## Développement et tests

Python 3.12 a été utilisé pour cette validation. Depuis le dépôt existant :

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
.venv/bin/python -m streamlit run app.py --server.headless=true
```

Dans l’environnement cloud préparé, utiliser `/workspace/.venvs/anki-studio/bin/python` à la place de `.venv/bin/python`. Utiliser le checkout existant ; un worktree supplémentaire n’est pas nécessaire.

Les tests synthétiques créent leurs PDF en mémoire : marqueurs vides, image seule, phrase unique, titres enveloppés, pages multiples, page très longue, sept niveaux, puces séparées, symboles, images entre textes, schémas vectoriels, Cloze, intégrité `.apkg`, ZIP source et parcours Streamlit (édition, validation, export partiel, invalidation). L’upload est simulé dans AppTest ; les autres widgets et leurs relances sont exercés. Ce n’est pas un test Safari réel.

Pour vérifier les PDF de cours, les placer dans un dossier privé **hors dépôt**, avec les noms ci-dessous, puis :

```sh
ANKI_REFERENCE_DIR=/chemin/vers/pdf-prives .venv/bin/python -m pytest -q
```

| Fichier | Basic | Cloze | Occlusion | Statut de cette validation |
|---|---:|---:|---:|---|
| `Anki 2 ANTHROPO .pdf` | 9 | 1 | 1 | Confirmé : 11 marqueurs, 1 image ; 9 Basic et 1 Cloze natives exportées ; Occlusion conservée dans les sources |
| `Anki 2 HISTO.pdf` | 16 | 0 | 0 | Confirmé sur la copie compressée : 16 marqueurs, 49 images ; 16 Basic exportées dans le test |
| `Anki 1 BIO.pdf` | 48 | 3 | 7 | Confirmé sur la copie compressée : 58 marqueurs, 43 images ; 48 Basic et 3 Cloze natives exportées ; Occlusions conservées dans les sources |

Les tests réels comparent d’abord les nombres rapportés aux lignes brutes du PDF, puis vérifient la conservation des éléments et textes, des images et l’export. Ils sont explicitement ignorés si le fichier manque. Les noms du tableau sont les noms canoniques utilisés par les tests ; les copies compressées fournies ont été liées à ces noms dans un dossier privé hors dépôt. La validation porte sur ces copies, sans supposer leur identité visuelle avec les PDF non compressés. Les cartes Glandes exocrines / Mérocrine / Apocrine ont désormais des régressions **sur le PDF réel d’histologie**, en complément des fixtures synthétiques : texte exact, parents, niveaux, retraits, images (0 / 4 / 2) et ordre. Les trois PDF totalisent **85 marqueurs et 93 occurrences d’images**. La revue critique a révélé que les anciens exports de 73 Basic comprenaient six réponses vides. Les six Basic sont désormais résolues et les quatre Cloze ont des suppressions natives : les exports de test contiennent **73 Basic + 4 Cloze = 77 notes/cartes**. Les huit Occlusions restent explicitement exclues du paquet courant, sans remplacement par de simples images. Aucun élément source n’est supprimé. Les corrections des dix passages sont des recettes explicites dans `reviewed_passages.json`, appliquées seulement après correspondance du texte complet et du type. Elles extraient les titres du texte source et conservent le passage intégral au verso ; elles ne prétendent pas résoudre automatiquement des passages différents.

Le contrôle renforcé compare aussi les mots et la ponctuation au second lecteur PDF **Poppler** (`pdftotext`), puis les retraits et l’ordre des images au HTML effectivement généré. Les retours de ligne et espaces typographiques sont distingués des changements de mots. Pour exécuter l’import/rendu avec le moteur officiel Anki dans un interpréteur séparé :

```sh
python3 -m venv /chemin/vers/anki-check
/chemin/vers/anki-check/bin/python -m pip install anki==26.9.3
ANKI_REFERENCE_DIR=/chemin/vers/pdf-prives \
  ANKI_TEST_PYTHON=/chemin/vers/anki-check/bin/python \
  .venv/bin/python -m pytest -q
```

`pdftotext` doit être installé pour le contrôle indépendant. Les contrôles dont l’outil, l’interpréteur ou le PDF manque sont explicitement ignorés ; une suite sans PDF privés ne démontre pas la fidélité sur ces cours. Le job CI `native-anki` vérifie le Cloze synthétique et l’aller-retour d’Occlusion native synthétique avec le moteur officiel ; les PDF privés restent hors GitHub.

Voir [REVIEW.md](REVIEW.md) pour la revue critique et [VALIDATION.md](VALIDATION.md) pour les résultats exécutés et les contrôles restant à faire avant déploiement.
