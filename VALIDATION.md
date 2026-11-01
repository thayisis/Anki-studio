# Validation après revue critique — 1 novembre 2026

Branche : `fix/pdf-conversion`. Aucune fusion et aucun déploiement. La revue détaillée est dans [REVIEW.md](REVIEW.md).

## Résultats réellement exécutés

**101 tests réussis, aucun échec, aucun test ignoré**, avec les trois PDF et l’interpréteur Anki officiel activés :

```sh
ANKI_REFERENCE_DIR=/workspace/.anki-studio/reference-pdfs \
  ANKI_TEST_PYTHON=/workspace/.venvs/anki-import-check/bin/python \
  /workspace/.venvs/anki-studio/bin/python -m pytest -q
```

Le dossier privé contient l’anthropologie fournie et des liens vers les copies compressées de biologie et d’histologie, sous leurs noms canoniques. Aucun PDF ni paquet de cours n’est ajouté au dépôt.

| Document testé | Basic détectées | Cloze | Occlusion | Total | Images (occurrences) | Notes exportées (Basic + Cloze) |
|---|---:|---:|---:|---:|---:|---:|
| Anthropologie | 9 | 1 | 1 | 11 | 1 | 10 |
| Histologie compressée | 16 | 0 | 0 | 16 | 49 | 16 |
| Biologie compressée | 48 | 3 | 7 | 58 | 43 | 51 |
| Total | 73 | 4 | 8 | 85 | 93 | 77 |

Les nombres de marqueurs sont confirmés indépendamment sur les PDF. Le marquage des notes comme « validées » est simulé **dans les tests uniquement** ; ce n’est pas une validation pédagogique.

### Texte et ponctuation

Les 556 lignes de texte de cours non vides après les marqueurs (181 histologie, 291 biologie, 84 anthropologie) sont contrôlées : provenance PyMuPDF, puis décodage indépendant Poppler, comparaison de la séquence des mots/caractères de ponctuation au titre propre et au HTML du verso. Pour les dix répartitions revues, le concept du recto est contrôlé comme extrait littéral et le passage complet est contrôlé au verso : le concept n’est pas compté deux fois comme contenu source. Les annotations Cloze sont retirées uniquement pour comparer les caractères d’origine. Le test vérifie aussi qu’aucun mot Poppler après le premier marqueur n’est laissé sans représentation (marqueurs et glyphes de puces traités séparément).

Les espaces typographiques et les coupures physiques de ligne ne constituent pas des mots ajoutés ou supprimés. Poppler séparait le petit chiffre 2 de O2 dans la carte Protéines : leurs boîtes se touchent avec un écart de -0,002 point. Le contrôle joint uniquement de telles boîtes jointives, pas les vrais espaces entre mots. La taille réduite de ce chiffre est désormais conservée dans le HTML par un span de taille relative ; aucune substitution du texte en Unicode différent n’est faite.

### Retraits, images et titres

Les coordonnées du premier mot de chaque ligne sont comparées à Poppler ; les marges et niveaux sont lus dans le HTML rendu, pas uniquement dans le JSON. Les niveaux observés sont 0–4 en histologie et 0–3 dans les deux autres documents. Les puces séparées et les lignes enveloppées restent distinctes ; les glyphes de puces sont normalisés en HTML sans transformer un vrai ® dans le contenu.

Les 93 placements d’images sont comptabilisés et comparés aux PDF ; leur ordre est contrôlé dans le HTML. Les médias des exports Basic sont importés dans Anki et comparés par SHA-256 : 49 fichiers uniques pour l’histologie, 34 pour la biologie (une image répétée partage son fichier), aucun pour les Basic d’anthropologie. Les images des Occlusions restent dans les sources et les aperçus.

Glandes exocrines, Mérocrine et Apocrine ont des assertions de texte exact, contexte, niveaux et retraits. Leurs nombres d’images sont 0, 4 et 2. La transition vers Morphologie remplace correctement le parent Mode et nature de la sécrétion. En anthropologie, les longs paragraphes précédents ne sont plus réutilisés comme titres parents ; Descola est conservé.

Des zones source ont aussi été inspectées visuellement, notamment Apocrine, Protéines/O2 et le paragraphe Il contredit… en anthropologie. Cette inspection ciblée n’est pas une lecture visuelle exhaustive de tous les pixels des 85 cartes.

### Export et interface

Le moteur officiel **Anki 26.9.3**, installé dans un environnement séparé, importe réellement les trois paquets corrigés : Histologie 16 Basic ; Biologie 48 Basic + 3 Cloze ; Anthropologie 9 Basic + 1 Cloze, soit 77 notes/cartes. Un paquet synthétique Cloze (1 note donnant 2 cartes) est aussi vérifié. Les tests vérifient les champs, numéros, médias et le rendu recto/verso via Anki ; les réponses masquées du Cloze sont absentes du texte visible de la question et présentes dans la réponse.

Les contrôles SQLite, modèles (question **et réponse**), champs, archives et médias de l’application passent. Les tests Streamlit vérifient l’édition, les changements de carte, la validation, l’export partiel, l’invalidation des téléchargements, la récupération unique du titre source et les parcours d’export sur la Basic Polymère et la Cloze énergie du PDF réel. Les aperçus masquent/révèlent la suppression active. `pip check`, Ruff (`F,E9`) et `git diff --check` passent.

Le serveur Streamlit avait été démarré et sa santé HTTP vérifiée pendant la préparation précédente. La revue courante ajoute les parcours AppTest ; elle ne prétend pas avoir redémarré ou déployé le site public.

## Dix passages résolus

Les six Basic anciennement exclues (Biologie 16/17/18/54 et Anthropologie 7/8) sont maintenant réparties en concepts littéraux au recto et passages complets au verso, sans mot supprimé, ajouté ou corrigé. Les dix passages sont reconnus par leur texte complet et leur type via des recettes explicites, sans dépendre du nom du PDF ni du numéro de carte. Les passages différents ne sont pas réécrits par ces recettes.

Les quatre Cloze utilisent chacune `c1` : **un apport continu d’énergie**, **changements évolutifs**, **l’endosymbiose**, **sous-cultures**. Ces cibles sont des choix pédagogiques proposés, littéraux et modifiables ; les PDF ne contenaient pas d’annotations de suppression. Le champ natif `Text` contient seulement le passage annoté, sans titre supplémentaire qui révèlerait la réponse. L’égalité stricte entre verso démasqué et lignes PDF est testée pour les dix cas, espaces et ponctuation inclus. Les modifications doivent toujours être validées par l’utilisateur avant export.

Voir [CARD_CORRECTIONS.md](CARD_CORRECTIONS.md) pour les rectos et cibles exacts. Les transformations sont aussi exercées sur des PDF synthétiques Unicode en CI.

## Occlusion native : étude validée, intégration ouverte

Les huit schémas ont été inspectés. Ils ne définissent pas les rectangles à masquer. Le prototype natif a créé 1 note synthétique, 2 masques et 2 cartes ; il les a exportés puis réimportés dans une autre collection Anki, avec vérification du stock natif `originalStockKind=6`, des formes actives/inactives, des coordonnées, du média inchangé et des templates `anki.imageOcclusion.setup()`.

**7 tests d’étude passent** (6 entrées invalides refusées et 1 aller-retour natif). Aucune image avec masques dessinés définitivement n’est substituée à une Occlusion native. Le prototype ne participe pas à l’export courant de l’application. L’éditeur de zones, la validation des cibles des huit notes et le chemin d’export natif côté application restent à développer : [NATIVE_OCCLUSION.md](NATIVE_OCCLUSION.md).

## Non vérifié / non garanti

- Safari sur un vrai iPad, téléchargements et disposition sur cet appareil.
- Rendu graphique dans le client Anki iPad effectivement utilisé ; l’import et le rendu HTML du moteur officiel ont été testés, pas son navigateur embarqué.
- Reconnaissance des mots inscrits dans les pixels des images, ni lisibilité parfaite de toutes les petites annotations après compression.
- Identité visuelle des copies compressées avec les deux fichiers initiaux trop volumineux.
- Justesse sémantique automatique de tous les titres parents : elle reste à confirmer visuellement ; ni les comptages ni le second lecteur ne la prouvent.
- Masquage et exécution graphique JavaScript des huit Occlusions sur Safari / Anki : seul le prototype natif headless synthétique a été éprouvé.
- Résultats de la nouvelle CI distante : les commandes passent localement ; les PDF privés ne sont pas dans GitHub.

Versions locales : Python 3.12.14, Streamlit 1.66.1, PyMuPDF 1.28.2, genanki 0.13.1, Anki 26.9.3. La suite précédente de 45 tests et ses exports de 73 Basic étaient insuffisants pour conclure à des cartes utilisables : six réponses vides y passaient. La revue suivante avait exclu ces six Basic et n’exportait que 67 notes. Les dix passages sont désormais résolus : les résultats actuels de 77 notes supportées remplacent ces deux états antérieurs. Le projet reste ouvert sur les huit Occlusions natives et la validation Safari iPad.
