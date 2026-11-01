# Validation — 1 novembre 2026

Branche locale : `fix/pdf-conversion`. Aucun déploiement, publication d’environnement ou modification de configuration publiée n’a été effectué pendant cette mission.

## Résultats exécutés

| Contrôle | Résultat |
|---|---|
| Régressions initiales sur le moteur précédent | 3 échecs, 1 réussite : carte image seule supprimée, marqueurs vides supprimés, symbole ® supprimé |
| Suite finale avec le PDF d’anthropologie fourni | **45 réussites, 0 ignoré, 0 échec** |
| PDF réels | Anthropologie et copies compressées d’Histologie et Biologie : tous exécutés |
| Streamlit AppTest | 3 tests passent : sélection/validation par note, export partiel, édition du titre/texte/retrait, récupération du titre au verso, invalidation de la validation et du téléchargement après édition |
| Serveur Streamlit | Démarrage effectif ; `/_stcore/health` renvoie `ok`, `/` renvoie du HTML |
| Dépendances | `pip check` : aucune incompatibilité détectée |
| Vérifications statiques | Ruff (`F,E9`) et `git diff --check` passent |

Commande de la suite finale (le dossier est propre à cette session ; voir README pour les autres environnements) :

```sh
ANKI_REFERENCE_DIR=/workspace/.anki-studio/reference-pdfs \
  /workspace/.venvs/anki-studio/bin/python -m pytest -q
```

Versions installées : Python 3.12.14, Streamlit 1.66.1, PyMuPDF 1.28.2, genanki 0.13.1. La version minimale PyMuPDF du dépôt a été relevée à la version utilisée pour ces contrôles. La CI ajoutée exécute les tests synthétiques et ignore explicitement les PDF privés absents ; elle n’a pas encore été exécutée sur GitHub.

## Mesures sur le fichier réel

`Anki 2 ANTHROPO .pdf` : une longue page de 816 × 2156 points PDF ; comptage indépendant des lignes brutes : **9 CARTE, 1 CARTE CLOZE, 1 CARTE OCCLUSION**, soit 11.

- Ancien moteur : 10 cartes rendues. Nouveau moteur : les 11 entrées sont conservées.
- L’Occlusion, auparavant supprimée, contient une image conservée dans l’ordre, avec sa puce isolée associée.
- Les identifiants de tous les éléments source après le premier marqueur sont représentés dans les titres ou les blocs, y compris les puces attachées. Chaque ligne de texte extraite est retrouvée sans réécriture dans le titre ou le verso. Le test contrôle aussi le nombre d’occurrences d’images.
- La hiérarchie typographiquement attestée « Descola » fournit le contexte des sous-concepts concernés ; aucune phrase précédente arbitraire n’est utilisée comme titre parent.
- Export de test, toutes les notes marquées validées **dans le test seulement** : 9 notes Basic, 9 cartes Anki. La Cloze n’a pas de suppression explicite dans le PDF ; elle est exclue avec motif. L’Occlusion est exclue avec motif.
- Ces contrôles ne constituent pas une validation pédagogique ou visuelle humaine des 9 notes. L’application demande toujours la comparaison avec le PDF.

Les deux PDF initiaux dépassaient la limite de transfert de 32 Mio. Les nouvelles copies compressées ont pu être lues et testées. Le dossier privé de test contient des liens vers ces copies, sous les noms canoniques du README ; aucun PDF n’a été ajouté au dépôt.

| PDF effectivement testé | Basic | Cloze | Occlusion | Total | Occurrences d’images | Basic exportées dans le test |
|---|---:|---:|---:|---:|---:|---:|
| Anthropologie | 9 | 1 | 1 | 11 | 1 | 9 |
| Histologie compressée | 16 | 0 | 0 | 16 | 49 | 16 |
| Biologie compressée | 48 | 3 | 7 | 58 | 43 | 48 |
| Total | 73 | 4 | 8 | 85 | 93 | 73 |

La conservation de toutes les lignes physiques et de toutes les positions d’images est comparée à une extraction PyMuPDF indépendante du découpage du moteur. Chaque export de test vérifie les notes, cartes, modèles, champs et médias ; le marquage « validé » est simulé dans les tests et ne remplace pas la validation humaine.

L’examen réel a révélé un défaut que les contrôles de conservation ne suffisaient pas à détecter : le contexte d’Histologie était absent car les sections ne sont pas en gras. Le moteur reconnaît maintenant le plan de puces établi par l’indentation et le poursuit entre les marqueurs. Il ne reprend pas simplement les dernières lignes. Les corrections ajoutent aussi le rendu de la puce à côté de son image, au lieu d’un point vide supplémentaire après elle.

Les trois cartes réelles d’histologie ont des assertions de texte exact transcrit, hiérarchie, retraits, nombres d’images et ordre :

- **Glandes exocrines** : 8 lignes textuelles au verso, niveaux `[0,1,1,1,1,1,0,1]`, retraits `[0,20.02,20.02,20.02,20.02,20.02,0,20.02]` points PDF, aucune image.
- **Mérocrine** : 6 lignes textuelles, 4 images et leurs puces associées. Parents : titre intégral de Glandes exocrines → Classification et diagnostic → Mode et nature de la sécrétion.
- **Apocrine** : 7 lignes textuelles, dont 2 continuations de la phrase sur la mucine, 2 images et leurs puces. Mêmes parents que Mérocrine ; le contenu de Mérocrine n’est pas ajouté au titre.

La transition vers « Morphologie » est aussi vérifiée : elle remplace le parent « Mode et nature de la sécrétion » pour les cartes suivantes. Une fixture synthétique indépendante couvre cette logique dans la CI sans PDF privé. Les copies compressées ne permettent pas de promettre la résolution des images des fichiers initiaux ; leur fidélité à ces originaux n’a pas été comparée.

## Ce qui a changé

- `engine.py` : étapes séparées, frontières entre pages, rétention des marqueurs vides/images seules, lignes et symboles préservés, retraits réels sans limite de niveaux, puces séparées, images intercalées et schémas vectoriels, contexte prudent, avertissements et provenance.
- `exporter.py` : export partiel Basic/Cloze, identifiants stables par PDF, vérification SQLite/modèles/champs/médias/numéros de cartes, ZIP source complet. Le test synthétique mixte vérifie 2 notes (Basic + Cloze) donnant 3 cartes.
- `app.py` : édition sans HTML, disposition verticale possible sur iPad, validation indépendante, invalidation après correction, affichage de chaque exclusion et sauvegarde des sources.
- `tests/`, `requirements-dev.txt`, `.github/workflows/tests.yml` : suite reproductible et CI. Les PDF privés sont ignorés et restent hors dépôt.
- `requirements.txt`, `README.md`, `.gitignore` et ce rapport : dépendance, utilisation, limites et preuves.

## Limites et décision de déploiement

**Prêt pour revue et essai encadré des Basic/Cloze ; pas validé comme remplacement définitif de production.** Aucun déploiement n’a été demandé ou effectué.

Avant généralisation : terminer la revue visuelle humaine des cartes et de la lisibilité des images compressées, essayer les interactions/téléchargements sur Safari iPad et importer les archives dans le client Anki réellement utilisé. Les archives ont été contrôlées directement ; aucun client Anki graphique ou Safari réel n’a été exécuté ici.

L’Occlusion native n’est pas implémentée. Le modèle officiel Anki et ses exigences ont été examinés ; un simple marqueur ne fournit pas les masques. Le ZIP conserve le matériel pour une création manuelle dans un client compatible. L’OCR, les mises en page complexes et la restitution sémantique automatique à 100 % restent hors des garanties de cette version.
