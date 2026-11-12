# Anki Studio

Application Streamlit gratuite pour convertir des PDF balisés en notes Anki, avec comparaison au document original. Utilisation dans un navigateur, notamment Safari sur iPad ; aucune installation locale n’est nécessaire pour l’utilisateur de l’application hébergée.

## Workflow gratuit PDF → ChatGPT manuel → Anki

1. Importer un PDF avec les marqueurs textuels `CARTE`, `CARTE CLOZE` ou `CARTE OCCLUSION`, ou réouvrir un **projet Anki Studio ZIP** créé par cette version.
2. Choisir **Sans IA** pour garder les rectos extraits et utiliser l’éditeur existant, ou **ChatGPT manuel (gratuit)** pour préparer un lot de cartes. Aucun compte/API payant ni clé n’est requis par l’application.
3. Choisir la première carte et le nombre de cartes du lot, puis **Générer le JSON et le prompt**. Copier le prompt via le bouton de copie du bloc, puis le coller dans ChatGPT. Le JSON léger garde les textes, les puces, les continuations et les retraits ; ni PDF, ni pixels, ni base64 ne sont envoyés. Les images restent dans Anki Studio et dans le projet. Les textes copiés sont partagés avec ChatGPT par l’utilisateur.
4. Coller la réponse JSON de ChatGPT, ou importer son fichier `.json`, puis **Appliquer les corrections JSON**. Le lot doit être complet : toute réponse incomplète, clé supplémentaire (notamment un verso), mauvais identifiant, doublon, autre document ou modification locale depuis la préparation fait refuser **tout le lot sans modifier les cartes**. Les blocs Markdown `json` autour de la réponse sont acceptés.
5. Exporter les `.apkg` **sans validation individuelle obligatoire**, pour Basic, Cloze et Occlusion. Les occlusions exigent des masques dessinés, terminés et géométriquement valides ; la revue par numéro reste facultative et son absence est signalée. Les cartes impossibles à exporter restent dans le tableau des problèmes et dans le projet ; elles ne bloquent pas les autres cartes. Une Cloze sans suppression reste à annoter dans l’éditeur, une Occlusion sans masque reste à dessiner.
6. Télécharger le **projet réimportable ZIP** pour reprendre sur iPad ou dans une nouvelle session : PDF original, toutes les cartes et leurs corrections, médias non masqués, coordonnées, masques et lot ChatGPT actif. Le réimport vérifie le PDF et les médias contre leurs sources (200 Mo maximum, compressés et décompressés). Les gestes de revue d’occlusion sont réinitialisés au réimport, sans empêcher l’export des masques terminés. Le dossier source ZIP historique reste disponible pour l’audit ; il n’est pas le nouveau format de projet et ne peut pas être réimporté directement.

Les identifiants de l’échange sont les GUID Anki de la PR existante : stables pour le même PDF, numéro et type de note, même après correction du recto ou réouverture. Un autre fichier PDF, même visuellement similaire, constitue un autre document. Un seul lot est actif à la fois ; préparer le suivant remplace le précédent. Sauvegarder le projet après préparation permet de quitter l’application avant de revenir avec la réponse de ChatGPT.

Le prompt demande des questions précises pour les puces explicatives uniques, y compris les paragraphes pris pour titres. Il distingue en histologie critères, mode/nature de sécrétion, morphologie, rôle et localisation. Les corrections reçues changent uniquement les rectos : **aucun bloc existant du verso n’est réécrit, retiré ou déplacé**. Lorsqu’un titre est remplacé ou que `move_source_title=true`, son contenu source manquant est ajouté au début du verso, une seule fois. Les suffixes de définition déjà déplacés par V9 ne sont pas dupliqués. Les suppressions Cloze du recto doivent rester identiques ; les types et masques natifs ne sont jamais modifiés par ChatGPT.

Le JSON est un transport, pas une validation médicale : aucun appel à ChatGPT n’est réalisé ou prétendu testé par Anki Studio. L’utilisateur effectue l’échange manuellement et reste responsable de la qualité sémantique des questions. La fidélité intégrale de tout PDF arbitraire ne peut pas être garantie ; la source originale reste conservée.

### Basic et Cloze

Les Basic utilisent les champs natifs `Front` / `Back`. Un verso vide (ou ne contenant que des puces sans texte ni image) est explicitement exclu, même après validation. Corriger le titre et utiliser la récupération du titre source au verso avant de réexporter ; cette récupération ne peut pas dupliquer le texte lors d’enregistrements successifs. Les titres distincts ne sont pas recopiés inutilement au verso. Pour une définition isolée, le mot-concept du recto peut aussi figurer dans la phrase complète au verso afin de préserver son libellé original.

Les Cloze utilisent un modèle natif Anki de type Cloze (`Text` / `Extra`, filtre `{{cloze:Text}}`). Le marqueur `CARTE CLOZE` ne précise pas les mots à masquer. Les quatre passages des cours fournis ont maintenant des suppressions littérales proposées et modifiables (voir [CARD_CORRECTIONS.md](CARD_CORRECTIONS.md)). Pour les autres passages, l’utilisateur peut saisir `{{c1::texte}}`, `{{c2::autre texte::indice}}`, etc. dans le titre ou une ligne. Les suppressions vides, incomplètes ou imbriquées sont refusées explicitement. Un même numéro produit une seule carte ; plusieurs numéros produisent plusieurs cartes.

La validation individuelle Basic/Cloze est facultative. L’export ne laisse jamais une Occlusion ou une Cloze incomplète bloquer les Basic exportables. Chaque archive produite est contrôlée avant téléchargement : base SQLite, nombre de notes/cartes, types des modèles, noms des champs, rectos/versos, numéros de Cloze et contenu exact des médias.

### Image Occlusion native

Les huit notes Occlusion recensées lors de la revue précédente peuvent être annotées dans un **éditeur visuel web**, puis exportées au format natif Anki. Les images sont vierges de masques au départ : l’application n’en crée jamais automatiquement.

Dessiner au doigt, au Pencil ou à la souris ; déplacer et redimensionner avec les poignées. Le mode Défiler et le zoom permettent de naviguer sans dessiner. Les rectangles sont associés à des numéros : même numéro = même carte Anki. Prévisualiser chaque numéro masqué, cocher sa vérification, puis éventuellement valider la note avant export. Toute modification annule ces validations et le téléchargement précédent. Les masques et pixels sont séparés et restent éditables dans un client Anki compatible après import.

Un export mixte utilise le moteur officiel Anki dans un processus isolé, avec vérification par réimport. Les Basic/Cloze seules conservent le chemin précédent. L’éditeur ne charge aucune ressource externe. Le ZIP source conserve PDF, images non masquées et coordonnées ; le projet ZIP permet aussi de reprendre l’édition. Biologie 15 comporte deux images : leur composition conserve les placements PDF et les deux fichiers originaux restent dans le paquet.

Voir [NATIVE_OCCLUSION.md](NATIVE_OCCLUSION.md) pour les huit schémas, la validation, le format et les limites. **Le toucher émulé Chromium est testé ; Safari sur un vrai iPad et l’Apple Pencil physique ne le sont pas.**

## Export immédiat et présentation (acquis V9)

Après conversion, utiliser « Exporter toutes les cartes en .apkg ». Sans case à cocher pour Basic/Cloze, les trois cours donnent immédiatement 73 Basic et 4 Cloze. Les huit Occlusions restent exclues tant que leurs masques manuels ne sont pas préparés et terminés. Une Occlusion sans masque n’est jamais annoncée prête à étudier.

Le tableau de correction distingue les exclusions bloquantes des avertissements. Un verso vide, une Cloze sans suppression, une image manquante/altérée, un ordre d’images modifié ou un retrait invalide exclut uniquement la note concernée. Un texte modifié ou incomplet est explicitement signalé, jamais certifié fidèle. Si des notes sont exclues, utiliser « Exporter les cartes valides en .apkg » ; les autres anomalies restent visibles comme avertissements. Le ZIP conserve toutes les sources.

Le recto garde la notion exacte et au plus le parent immédiat ; la hiérarchie complète reste dans `source_context`. Les définitions après deux-points identifiées avec preuve lexicale ou dans les notions vérifiées des cours passent en tête du verso, avec leur ponctuation originale. Les séparateurs de catégories ne sont pas déplacés. Les deux-points ambigus restent en place avec un avertissement : ce classement prudent n’est pas une analyse sémantique universelle.

## Extraction et limites

Le moteur est séparé en étapes dans `engine.py` : extraction des caractères/coordonnées/images, détection globale des limites, association des puces séparées, identification prudente des titres, niveaux selon la position horizontale du **texte**, association des images, puis HTML. `exporter.py` gère l’éligibilité, les archives Anki et la sauvegarde des sources.

- Chaque marqueur donne une entrée, même vide ou composée uniquement d’images. Une entrée sans titre nécessite une correction.
- Le texte extrait n’est ni résumé, ni traduit, ni corrigé. Les caractères `®`, `©`, etc. ne sont plus supprimés. Les glyphes Wingdings reconnus comme puces peuvent être traités comme tels.
- Les caractères plus petits ou décalés (notamment le petit « 2 » de la formule O2 du PDF de biologie) conservent leurs tailles et positions relatives en HTML, sans réécriture de leurs caractères. Si le texte de la ligne est corrigé, les anciennes tailles ne sont pas appliquées au nouveau texte : vérifier les indices/exposants après édition.
- Les lignes physiques restent séparées dans les données source. Les continuations géométriques sont réunies dans un même paragraphe HTML ; deux puces successives ne sont jamais fusionnées. Les retraits PDF restent visibles, sans limite à trois niveaux.
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

La dépendance officielle Anki demande une plateforme compatible (roue Linux manylinux_2_35 testée ici, glibc ≥ 2.35). La compatibilité de l’hébergeur public n’est pas présumée et aucun déploiement n’est effectué.

Dans l’environnement cloud préparé, utiliser `/workspace/.venvs/anki-studio/bin/python` à la place de `.venv/bin/python`. Utiliser le checkout existant ; un worktree supplémentaire n’est pas nécessaire.

Les tests synthétiques créent leurs PDF en mémoire : marqueurs vides, image seule, phrase unique, titres enveloppés, pages multiples, page très longue, sept niveaux, puces séparées, symboles, images entre textes, schémas vectoriels, Cloze, intégrité `.apkg`, ZIP source et parcours Streamlit (édition, validation, export partiel, invalidation). L’upload est simulé dans AppTest ; les autres widgets et leurs relances sont exercés. Ce n’est pas un test Safari réel.

Pour vérifier les PDF de cours, les placer dans un dossier privé **hors dépôt**, avec les noms ci-dessous, puis :

```sh
ANKI_REFERENCE_DIR=/chemin/vers/pdf-prives .venv/bin/python -m pytest -q
```

Les chiffres suivants proviennent de la revue précédente. Dans le nouvel environnement du 12 novembre, les PDF privés sont absents : **120 tests passent et 32 sont ignorés**, dont ceux sur les cours réels. Voir [VALIDATION.md](VALIDATION.md) pour distinguer les nouveaux tests des résultats historiques.

| Fichier | Basic | Cloze | Occlusion | Statut de cette validation |
|---|---:|---:|---:|---|
| `Anki 2 ANTHROPO .pdf` | 9 | 1 | 1 | Confirmé : 11 marqueurs, 1 image ; 9 Basic et 1 Cloze natives exportées ; Occlusion native disponible après dessin et validation |
| `Anki 2 HISTO.pdf` | 16 | 0 | 0 | Confirmé sur la copie compressée : 16 marqueurs, 49 images ; 16 Basic exportées dans le test |
| `Anki 1 BIO.pdf` | 48 | 3 | 7 | Confirmé sur la copie compressée : 58 marqueurs, 43 images ; 48 Basic et 3 Cloze natives exportées ; 7 Occlusions natives disponibles après dessin et validation |

Les tests réels comparent d’abord les nombres rapportés aux lignes brutes du PDF, puis vérifient la conservation des éléments et textes, des images et l’export. Ils sont explicitement ignorés si le fichier manque. Les noms du tableau sont les noms canoniques utilisés par les tests ; les copies compressées fournies ont été liées à ces noms dans un dossier privé hors dépôt. La validation porte sur ces copies, sans supposer leur identité visuelle avec les PDF non compressés. Les cartes Glandes exocrines / Mérocrine / Apocrine ont désormais des régressions **sur le PDF réel d’histologie**, en complément des fixtures synthétiques : texte exact, parents, niveaux, retraits, images (0 / 4 / 2) et ordre. Les trois PDF totalisent **85 marqueurs et 93 occurrences d’images**. La revue critique a révélé que les anciens exports de 73 Basic comprenaient six réponses vides. Les six Basic sont désormais résolues et les quatre Cloze ont des suppressions natives : les exports de test contiennent **73 Basic + 4 Cloze = 77 notes/cartes**. Les huit Occlusions sont maintenant prises en charge nativement après dessin et validation manuels. Les tests des trois paquets complets vérifient **85 notes/cartes** avec un masque de contrôle par note Occlusion ; les masques de contrôle ne sont pas proposés dans l’application. Aucun élément source n’est supprimé. Les corrections des dix passages sont des recettes explicites dans `reviewed_passages.json`, appliquées seulement après correspondance du texte complet et du type. Elles extraient les titres du texte source et conservent le passage intégral au verso ; elles ne prétendent pas résoudre automatiquement des passages différents.

Le contrôle renforcé compare aussi les mots et la ponctuation au second lecteur PDF **Poppler** (`pdftotext`), puis les retraits et l’ordre des images au HTML effectivement généré. Les retours de ligne et espaces typographiques sont distingués des changements de mots. Pour exécuter l’import/rendu avec le moteur officiel Anki dans un interpréteur séparé :

```sh
python3 -m venv /chemin/vers/anki-check
/chemin/vers/anki-check/bin/python -m pip install anki==26.9.3
ANKI_REFERENCE_DIR=/chemin/vers/pdf-prives \
  ANKI_TEST_PYTHON=/chemin/vers/anki-check/bin/python \
  .venv/bin/python -m pytest -q
```

`pdftotext` doit être installé pour le contrôle indépendant. Pour les tests du navigateur, installer aussi Chromium (`python -m playwright install --with-deps chromium` ou navigateur système). Les contrôles dont l’outil, le navigateur, l’interpréteur ou le PDF manque sont explicitement ignorés ; une suite sans PDF privés ne démontre pas la fidélité sur ces cours. Les jobs CI vérifient les formats natifs et les interactions du composant dans Chromium, sans déploiement ; les PDF privés restent hors GitHub.

Voir [REVIEW.md](REVIEW.md) pour la revue critique et [VALIDATION.md](VALIDATION.md) pour les résultats exécutés et les contrôles restant à faire avant déploiement.
