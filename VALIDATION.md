# Validation après revue critique — 1 novembre 2026

Branche : `fix/pdf-conversion`. Aucune fusion et aucun déploiement. La revue détaillée est dans [REVIEW.md](REVIEW.md).

## Résultats réellement exécutés

**60 tests réussis, aucun échec, aucun test ignoré**, avec les trois PDF et l’interpréteur Anki officiel activés :

```sh
ANKI_REFERENCE_DIR=/workspace/.anki-studio/reference-pdfs \
  ANKI_TEST_PYTHON=/workspace/.venvs/anki-import-check/bin/python \
  /workspace/.venvs/anki-studio/bin/python -m pytest -q
```

Le dossier privé contient l’anthropologie fournie et des liens vers les copies compressées de biologie et d’histologie, sous leurs noms canoniques. Aucun PDF ni paquet de cours n’est ajouté au dépôt.

| Document testé | Basic détectées | Cloze | Occlusion | Total | Images (occurrences) | Basic exportables dans le test |
|---|---:|---:|---:|---:|---:|---:|
| Anthropologie | 9 | 1 | 1 | 11 | 1 | 7 |
| Histologie compressée | 16 | 0 | 0 | 16 | 49 | 16 |
| Biologie compressée | 48 | 3 | 7 | 58 | 43 | 44 |
| Total | 73 | 4 | 8 | 85 | 93 | 67 |

Les nombres de marqueurs sont confirmés indépendamment sur les PDF. Le marquage des notes comme « validées » est simulé **dans les tests uniquement** ; ce n’est pas une validation pédagogique.

### Texte et ponctuation

Les 556 lignes de texte de cours non vides après les marqueurs (181 histologie, 291 biologie, 84 anthropologie) sont contrôlées : provenance PyMuPDF, puis décodage indépendant Poppler, comparaison de la séquence des mots/caractères de ponctuation au titre propre et au HTML du verso. Le test vérifie aussi qu’aucun mot Poppler après le premier marqueur n’est laissé sans représentation (marqueurs et glyphes de puces traités séparément).

Les espaces typographiques et les coupures physiques de ligne ne constituent pas des mots ajoutés ou supprimés. Poppler séparait le petit chiffre 2 de O2 dans la carte Protéines : leurs boîtes se touchent avec un écart de -0,002 point. Le contrôle joint uniquement de telles boîtes jointives, pas les vrais espaces entre mots. La taille réduite de ce chiffre est désormais conservée dans le HTML par un span de taille relative ; aucune substitution du texte en Unicode différent n’est faite.

### Retraits, images et titres

Les coordonnées du premier mot de chaque ligne sont comparées à Poppler ; les marges et niveaux sont lus dans le HTML rendu, pas uniquement dans le JSON. Les niveaux observés sont 0–4 en histologie et 0–3 dans les deux autres documents. Les puces séparées et les lignes enveloppées restent distinctes ; les glyphes de puces sont normalisés en HTML sans transformer un vrai ® dans le contenu.

Les 93 placements d’images sont comptabilisés et comparés aux PDF ; leur ordre est contrôlé dans le HTML. Les médias des exports Basic sont importés dans Anki et comparés par SHA-256 : 49 fichiers uniques pour l’histologie, 34 pour la biologie (une image répétée partage son fichier), aucun pour les Basic d’anthropologie. Les images des Occlusions restent dans les sources et les aperçus.

Glandes exocrines, Mérocrine et Apocrine ont des assertions de texte exact, contexte, niveaux et retraits. Leurs nombres d’images sont 0, 4 et 2. La transition vers Morphologie remplace correctement le parent Mode et nature de la sécrétion. En anthropologie, les longs paragraphes précédents ne sont plus réutilisés comme titres parents ; Descola est conservé.

Des zones source ont aussi été inspectées visuellement, notamment Apocrine, Protéines/O2 et le paragraphe Il contredit… en anthropologie. Cette inspection ciblée n’est pas une lecture visuelle exhaustive de tous les pixels des 85 cartes.

### Export et interface

Le moteur officiel **Anki 26.9.3**, installé dans un environnement séparé, importe réellement les trois paquets corrigés (16, 44 et 7 notes Basic), puis un paquet synthétique Cloze (1 note donnant 2 cartes). Les tests vérifient les champs, numéros, médias et le rendu recto/verso via Anki ; les réponses masquées du Cloze sont absentes du texte visible de la question et présentes dans la réponse.

Les contrôles SQLite, modèles (question **et réponse**), champs, archives et médias de l’application passent. Les tests Streamlit vérifient l’édition, les changements de carte, la validation, l’export partiel, l’invalidation des téléchargements et la récupération unique du titre source. `pip check`, Ruff (`F,E9`) et `git diff --check` passent.

Le serveur Streamlit avait été démarré et sa santé HTTP vérifiée pendant la préparation précédente. La revue courante ajoute les parcours AppTest ; elle ne prétend pas avoir redémarré ou déployé le site public.

## Corrections manuelles restantes

Six Basic contiennent une affirmation complète prise comme recto et aucun verso distinct :

- **Biologie nº 16, 17, 18, 54** : Polymère, Déshydratation, hydrolyse, Symbiose.
- **Anthropologie nº 7, 8** : paragraphe sur la nature domestique et paragraphe Écrit « Par delà nature et culture ».

Elles ne sont plus exportées en tant que réponses vides. Leur texte reste intact. Dans l’éditeur, choisir un titre/concept pertinent, cocher « Replacer aussi le titre source au début du verso », enregistrer, comparer et revalider. Le moteur ne fabrique pas de question à partir d’une affirmation.

Les 4 Cloze sources n’indiquent pas les mots à masquer : elles nécessitent des suppressions explicites. Les 8 Occlusions ne sont pas des exports natifs ; le ZIP conserve toutes les sources.

## Non vérifié / non garanti

- Safari sur un vrai iPad, téléchargements et disposition sur cet appareil.
- Rendu graphique dans le client Anki iPad effectivement utilisé ; l’import et le rendu HTML du moteur officiel ont été testés, pas son navigateur embarqué.
- Reconnaissance des mots inscrits dans les pixels des images, ni lisibilité parfaite de toutes les petites annotations après compression.
- Identité visuelle des copies compressées avec les deux fichiers initiaux trop volumineux.
- Justesse sémantique automatique de tous les titres parents : elle reste à confirmer visuellement ; ni les comptages ni le second lecteur ne la prouvent.
- Résultats de la nouvelle CI distante : les commandes passent localement ; les PDF privés ne sont pas dans GitHub.

Versions locales : Python 3.12.14, Streamlit 1.66.1, PyMuPDF 1.28.2, genanki 0.13.1, Anki 26.9.3. La suite précédente de 45 tests et ses exports de 73 Basic étaient insuffisants pour conclure à des cartes utilisables : six réponses vides y passaient. Les résultats de ce rapport remplacent cette conclusion.
