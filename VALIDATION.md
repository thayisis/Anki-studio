# Validation après revue critique — 2 novembre 2026

Branche : `fix/pdf-conversion`. Aucune fusion et aucun déploiement. La revue détaillée est dans [REVIEW.md](REVIEW.md).

## Corrections V9 après essai Safari iPad

- Rectos : notion exacte et au plus le parent immédiat ; hiérarchie complète conservée dans `source_context`. Les notions ambiguës longues ne sont pas résumées arbitrairement et sont signalées.
- Définitions : les suffixes explicatifs reconnus passent une seule fois au début du verso ; les mots et la ponctuation sont comparés à la source. Un séparateur de catégories n’est pas déplacé automatiquement. Classification prudente, limitée aux preuves lexicales et aux notions vérifiées des cours ; les autres cas sont avertis.
- Apocrine : comparaison visuelle directe du recadrage du PDF d’histologie ; cinq puces textuelles distinctes, phrase mucine réunie en un paragraphe, deux images dans l’ordre. Les lignes et niveaux physiques restent dans les données et sont vérifiés indépendamment avec Poppler.
- Export : 16 notes Histologie, 51 Biologie et 10 Anthropologie immédiatement, sans validation individuelle ; total 73 Basic + 4 Cloze. Import de ces paquets avec le moteur officiel Anki, vérification des champs, questions/réponses, suppressions et pixels. Les huit Occlusions non préparées restent exclues explicitement sans bloquer ces 77 notes. L’export complet des huit Occlusions reste testé avec des masques de contrôle uniquement.
- Précontrôle : contenu comparé en séquence de mots et ponctuation, images sources présentes dans l’ordre, hash des médias, retraits finis, verso non vide et syntaxe Cloze. Modifications/incomplétudes textuelles signalées comme fidélité non validée ; structure, images manquantes/altérées, verso vide et suppression absente bloquent seulement la note concernée.
- Les contrôles embarqués Basic/Cloze vérifient SQLite, modèles et médias ; l’import avec le moteur officiel est exécuté dans les tests. L’export mixte natif utilise aussi ce moteur et un réimport lors de l’export.

## Résultats réellement exécutés

**123 tests réussis, aucun échec, aucun test ignoré**, avec les trois PDF et l’interpréteur Anki officiel activés :

```sh
ANKI_REFERENCE_DIR=/workspace/.anki-studio/reference-pdfs \
  ANKI_TEST_PYTHON=/workspace/.venvs/anki-import-check/bin/python \
  /workspace/.venvs/anki-studio/bin/python -m pytest -q
```

Le dossier privé contient l’anthropologie fournie et des liens vers les copies compressées de biologie et d’histologie, sous leurs noms canoniques. Aucun PDF ni paquet de cours n’est ajouté au dépôt.

| Document testé | Basic | Cloze | Occlusion | Total | Images source | Notes exportées dans le test complet |
|---|---:|---:|---:|---:|---:|---:|
| Anthropologie | 9 | 1 | 1 | 11 | 1 | 11 |
| Histologie compressée | 16 | 0 | 0 | 16 | 49 | 16 |
| Biologie compressée | 48 | 3 | 7 | 58 | 43 | 58 |
| Total | 73 | 4 | 8 | 85 | 93 | 85 |

Les nombres de marqueurs sont confirmés indépendamment sur les PDF. Le marquage des notes comme « validées » et les rectangles attribués aux huit Occlusions sont simulés **dans les tests uniquement**. Chaque Occlusion réelle est d’abord vérifiée vierge de masques ; le test lui ajoute un rectangle géométrique de contrôle, sans proposer de cible pédagogique. Aucun de ces rectangles n’est préchargé dans l’application.

### Texte et ponctuation

Les 556 lignes de texte de cours non vides après les marqueurs (181 histologie, 291 biologie, 84 anthropologie) sont contrôlées : provenance PyMuPDF, puis décodage indépendant Poppler, comparaison de la séquence des mots/caractères de ponctuation au titre propre et au HTML du verso. Pour les dix répartitions revues, le concept du recto est contrôlé comme extrait littéral et le passage complet est contrôlé au verso : le concept n’est pas compté deux fois comme contenu source. Les annotations Cloze sont retirées uniquement pour comparer les caractères d’origine. Le test vérifie aussi qu’aucun mot Poppler après le premier marqueur n’est laissé sans représentation (marqueurs et glyphes de puces traités séparément).

Les espaces typographiques et les coupures physiques de ligne ne constituent pas des mots ajoutés ou supprimés. Poppler séparait le petit chiffre 2 de O2 dans la carte Protéines : leurs boîtes se touchent avec un écart de -0,002 point. Le contrôle joint uniquement de telles boîtes jointives, pas les vrais espaces entre mots. La taille réduite de ce chiffre est désormais conservée dans le HTML par un span de taille relative ; aucune substitution du texte en Unicode différent n’est faite.

### Retraits, images et titres

Les coordonnées du premier mot de chaque ligne sont comparées à Poppler ; les marges et niveaux sont lus dans le HTML rendu, pas uniquement dans le JSON. Les niveaux observés sont 0–4 en histologie et 0–3 dans les deux autres documents. Les puces distinctes restent séparées ; les lignes de continuation géométrique sont réunies dans le même paragraphe HTML, sans modifier les lignes de provenance ; les glyphes de puces sont normalisés en HTML sans transformer un vrai ® dans le contenu.

Les 93 placements d’images sont comptabilisés et comparés aux PDF ; leur ordre est contrôlé dans le HTML. Les médias des exports Basic sont importés dans Anki et comparés par SHA-256 : 49 fichiers uniques pour l’histologie, 34 pour la biologie (une image répétée partage son fichier), aucun pour les Basic d’anthropologie. Les images des Occlusions restent dans les sources et les aperçus.

Glandes exocrines, Mérocrine et Apocrine ont des assertions de texte exact, contexte, niveaux et retraits. Leurs nombres d’images sont 0, 4 et 2. La transition vers Morphologie remplace correctement le parent Mode et nature de la sécrétion. En anthropologie, les longs paragraphes précédents ne sont plus réutilisés comme titres parents ; Descola est conservé.

Des zones source ont aussi été inspectées visuellement, notamment Apocrine, Protéines/O2 et le paragraphe Il contredit… en anthropologie. Cette inspection ciblée n’est pas une lecture visuelle exhaustive de tous les pixels des 85 cartes.

### Export et interface

Le moteur officiel **Anki 26.9.3** importe les trois paquets complets : Histologie 16 Basic ; Biologie 48 Basic + 3 Cloze + 7 Occlusions ; Anthropologie 9 Basic + 1 Cloze + 1 Occlusion, soit 85 notes/cartes avec un rectangle de contrôle par Occlusion. Les 73 Basic et 4 Cloze restent aussi testées par leur chemin d’export précédent, sans Occlusion validée. Un paquet synthétique Cloze (1 note donnant 2 cartes) est aussi vérifié. Les tests vérifient les champs, numéros, médias et le rendu recto/verso via Anki ; les réponses masquées du Cloze sont absentes du texte visible de la question et présentes dans la réponse.

Les contrôles SQLite, modèles (question **et réponse**), champs, archives et médias de l’application passent. Les tests Streamlit vérifient l’édition, les changements de carte, la validation, l’export partiel, l’invalidation des téléchargements, la récupération unique du titre source et les parcours d’export sur la Basic Polymère et la Cloze énergie du PDF réel. Les aperçus masquent/révèlent la suppression active. `pip check`, Ruff (`F,E9`) et `git diff --check` passent.

Un serveur Streamlit uniquement local est démarré automatiquement par les tests navigateur : import PDF, dessin, aperçu, validation par numéro, validation de note, téléchargement ZIP intègre, puis invalidation de l’export après une modification. Le changement de carte préserve les zones et validations ; une nouvelle note reste vierge. Le site public n’est ni modifié ni déployé.

## Dix passages résolus

Les six Basic anciennement exclues (Biologie 16/17/18/54 et Anthropologie 7/8) sont maintenant réparties en concepts littéraux au recto et passages complets au verso, sans mot supprimé, ajouté ou corrigé. Les dix passages sont reconnus par leur texte complet et leur type via des recettes explicites, sans dépendre du nom du PDF ni du numéro de carte. Les passages différents ne sont pas réécrits par ces recettes.

Les quatre Cloze utilisent chacune `c1` : **un apport continu d’énergie**, **changements évolutifs**, **l’endosymbiose**, **sous-cultures**. Ces cibles sont des choix pédagogiques proposés, littéraux et modifiables ; les PDF ne contenaient pas d’annotations de suppression. Le champ natif `Text` contient seulement le passage annoté, sans titre supplémentaire qui révèlerait la réponse. L’égalité entre les mots et la ponctuation du verso démasqué et du PDF est testée pour les dix cas ; seuls les espaces des retours de ligne physiques sont normalisés. La validation individuelle Basic/Cloze est désormais facultative.

Voir [CARD_CORRECTIONS.md](CARD_CORRECTIONS.md) pour les rectos et cibles exacts. Les transformations sont aussi exercées sur des PDF synthétiques Unicode en CI.

## Occlusion native : intégration vérifiée

L’éditeur web et le chemin d’export natif sont maintenant intégrés. Aucune zone n’est créée automatiquement. Les zones sont dessinées, déplacées et redimensionnées à la main, en coordonnées normalisées liées au hash du canevas. Chacune des cartes générées doit être prévisualisée puis explicitement validée. Tout changement annule la validation et le téléchargement, y compris pendant un déplacement avant relâchement du pointeur.

Les huit notes réelles ont été exportées/importées par le moteur officiel avec des masques de contrôle. Le test **modifie ensuite le masque de chacune des huit notes via `update_image_occlusion_note()` après import**, tout en vérifiant que l’image reste identique. Le modèle porte `originalStockKind=6`, les champs natifs tagués et les templates officiels. Les masques demeurent des formes distinctes : aucune image aplatie n’est substituée.

Les deux images de Biologie 15 sont composées selon leurs placements PDF ; leurs fichiers extraits originaux sont aussi conservés et contrôlés dans le paquet. Le backend s’exécute dans un processus Anki isolé par export et vérifie l’archive par réimport avant de la proposer au téléchargement. Les événements répétés/périmés, le rapprochement commit/aperçu, les coordonnées invalides, les validations partielles et les groupes de rectangles sont testés.

Les tests navigateur Chromium exécutent réellement les gestes tactiles émulés de dessin, déplacement, redimensionnement et défilement, ainsi que zoom, changement de largeur, événements de stylet synthétiques, annulation/rétablissement, regroupement et suppression. Les interactions sont aussi vérifiées au travers du vrai composant dans Streamlit. La hauteur de l’iframe est bornée par son contenu, sans boucle de croissance lors des redimensionnements.

Voir [NATIVE_OCCLUSION.md](NATIVE_OCCLUSION.md) pour les étapes d’utilisation et les limites matérielles.

## Non vérifié / non garanti

- Safari sur un vrai iPad, téléchargements et disposition sur cet appareil.
- Rendu graphique dans le client Anki iPad effectivement utilisé ; l’import et le rendu HTML du moteur officiel ont été testés, pas son navigateur embarqué.
- Reconnaissance des mots inscrits dans les pixels des images, ni lisibilité parfaite de toutes les petites annotations après compression.
- Identité visuelle des copies compressées avec les deux fichiers initiaux trop volumineux.
- Justesse sémantique automatique de tous les titres parents : elle reste à confirmer visuellement ; ni les comptages ni le second lecteur ne la prouvent.
- Exécution graphique du canevas natif dans le client Anki cible : import, édition des formes et HTML natif vérifiés par le moteur officiel ; pas de client Anki graphique exécuté.
- Apple Pencil physique : événements de stylet synthétiques seulement. Le toucher est émulé dans Chromium ; rejet de paume, interruptions iPadOS et Safari réel non vérifiés.
- Hébergeur final : la nouvelle dépendance `anki==26.9.3` a été installée/testée ici (Linux manylinux_2_35, glibc ≥ 2.35), pas sur le site public.
- Résultats de la nouvelle CI distante : les commandes passent localement ; les PDF privés ne sont pas dans GitHub.

Versions locales : Python 3.12.14, Streamlit 1.66.1, PyMuPDF 1.28.2, genanki 0.13.1, Anki 26.9.3. La suite précédente de 45 tests et ses exports de 73 Basic étaient insuffisants pour conclure à des cartes utilisables : six réponses vides y passaient. La revue suivante avait exclu ces six Basic et n’exportait que 67 notes. Les dix passages sont désormais résolus : les 77 notes Basic/Cloze ont été rétablies, puis l’intégration Occlusion porte le test complet à 85 notes après annotation et validation explicites. L’éditeur et les huit Occlusions natives sont maintenant intégrés ; la validation physique Safari iPad / Pencil reste ouverte. Les rectangles pédagogiques réels restent à dessiner et vérifier par l’utilisateur, sans préremplissage automatique.
