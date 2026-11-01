# Étude des huit Occlusions natives

## Conclusion technique

L’export réellement natif est **faisable avec le moteur officiel Anki**. Un prototype synthétique crée une note Image Occlusion, deux masques rectangulaires, deux cartes, exporte le paquet et le réimporte dans une autre collection. Les masques restent structurés et éditables ; ils ne sont jamais dessinés définitivement dans une image.

Cette preuve ne signifie pas que les huit Occlusions du cours sont intégrées à l’application. L’export actuel des cours inclut Basic et Cloze seulement ; le ZIP conserve les huit notes Occlusion et leurs images. Le projet reste ouvert sur cette intégration.

## Huit schémas examinés visuellement

| PDF / nº | Contenu visible dans l’image | Images source | Décisions de masquage à présenter dans un éditeur |
|---|---|---:|---|
| Biologie 7 | Classification du vivant | 1 | Noms des domaines/règnes, codes, ou les deux ; définir une carte par cible ou un groupe. |
| Biologie 15 | Tableaux des groupes fonctionnels | 2 | Choisir entre noms, structures et propriétés ; composer un canevas commun aux deux images sans perdre leur ordre. |
| Biologie 19 | Tableau des quatre groupes de macromolécules | 1 | Choisir les cellules à masquer, sans cacher en même temps tous les indices utiles. |
| Biologie 31 | Quelques exemples d’acides aminés | 1 | Noms et abréviations, structures, ou classification de polarité ; conserver les annotations manuscrites. |
| Biologie 32 | Les vingt acides aminés | 1 | Lettre, abréviation, nom et caractère essentiel : plusieurs exercices possibles à distinguer. |
| Biologie 50 | Le transport de protéines | 1 | Légendes du schéma ou étapes du texte ; préserver les deux parties visibles. |
| Biologie 52 | Maladie de Tay-Sachs | 1 | Titre ou éléments du texte clinique ; aucun diagnostic supplémentaire n’est généré. |
| Anthropologie 9 | Tableau Totémisme / Naturalisme / Animisme / Analogisme | 1 | Noms des quatre cases, intitulés des axes, ou exercice combiné. |

Ce sont des possibilités d’exercice, pas des masques présentés comme déjà validés. Les fichiers ne contiennent ni rectangles de masquage ni annotations PDF indiquant les réponses à cacher. Quatre notes n’ont pas de titre textuel en dehors du bitmap. Ces données et les légendes sont conservées dans les sources.

## Contrat natif vérifié

Références officielles examinées :

- [Modèle Image Occlusion](https://github.com/ankitects/anki/blob/main/rslib/src/image_occlusion/notetype.rs)
- [Parseur des formes et propriétés](https://github.com/ankitects/anki/blob/main/rslib/src/image_occlusion/imageocclusion.rs)

Le prototype appelle `Collection.add_image_occlusion_notetype()` et `add_image_occlusion_note()` :

- modèle de type Cloze **avec `originalStockKind == 6`** ; un Cloze générique ne suffit pas ;
- champs natifs Occlusion, Image, Header, Back Extra, Comments et tags de champs natifs ;
- masques dans Occlusion, par exemple `{{c1::image-occlusion:rect:left=0.1:top=0.1:width=0.3:height=0.2:oi=1}}` ;
- une image de base intacte et des masques séparés ; mêmes numéros regroupant plusieurs formes, numéros différents produisant différentes cartes ;
- templates natifs avec `anki.imageOcclusion.setup()` et `image-occlusion-canvas`.

`native_io.py` étudie seulement la sérialisation rectangulaire : coordonnées normalisées bornées dans l’image, valeurs finies, surface positive, numéros 1–99. Les masques vides ou invalides sont refusés, jamais transformés en notes Basic de substitution.

## Test exécuté

```sh
ANKI_TEST_PYTHON=/workspace/.venvs/anki-import-check/bin/python \
  /workspace/.venvs/anki-studio/bin/python -m pytest tests/test_native_occlusion.py -q
```

**7 tests passent** : six refus d’entrées invalides et un aller-retour natif. Celui-ci vérifie la collection exportée puis réimportée : 1 note, 2 cartes, 2 masques, stock natif, coordonnées des formes, média inchangé par SHA-256, formes active/inactive et templates natifs. L’essai utilise une image synthétique, pas un schéma du cours.

## Intégration restant à développer

1. Éditeur tactile de rectangles et regroupement des cibles, avec aperçu masque actif/inactif et validation par note.
2. Conservation des coordonnées normalisées et d’un manifeste lié au PDF et au canevas. Les deux images de Biologie 15 doivent être composées à partir de leurs placements source, sans nouvelle interprétation du cours.
3. Chemin d’export via le moteur officiel, isolé par session/export, conservant les identifiants et le type natif. Ne pas injecter seulement les templates dans `genanki`.
4. Vérification/import de ce format natif par le moteur officiel : le vérificateur SQLite legacy actuel de l’application ne doit pas supposer la même structure d’archive.
5. Contrôle du canevas et des interactions sur Safari iPad et dans le client Anki cible.

La roue Anki testée est 26.9.3, Linux `manylinux_2_35` : Python et glibc de l’hébergement final doivent être vérifiés avant d’ajouter cette dépendance à l’application. Aucune installation sur l’iPad ni aucun service payant ne serait requis pour l’édition web ; cette expérience n’est pas encore intégrée.

Le test headless vérifie le modèle, les données et le HTML natifs, **pas l’exécution graphique JavaScript du canevas dans un vrai navigateur**. L’Occlusion du cours n’est donc pas annoncée comme prête à utiliser ou déployée.
