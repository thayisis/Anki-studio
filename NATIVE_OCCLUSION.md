# Image Occlusion native — éditeur et export intégrés

Les huit notes Occlusion des PDF sont maintenant prises en charge par l’éditeur web et le modèle natif officiel Anki. **Aucune zone n’est prédéfinie** dans le code des cours : l’utilisateur dessine les rectangles et valide chaque carte générée.

## Utilisation dans le navigateur

1. Sélectionner une note Occlusion. L’éditeur montre l’image source non masquée. Le titre est facultatif si le PDF ne contient qu’une image.
2. Utiliser **Dessiner**, puis faire glisser le doigt, le Pencil ou la souris. Utiliser **Déplacer / redimensionner** et les poignées pour ajuster les rectangles. Annuler/rétablir, supprimer une zone et effacer toutes les zones sont disponibles.
3. Utiliser **Défiler** et le zoom pour naviguer dans une grande image. Les coordonnées sont normalisées sur l’image, indépendamment du zoom, de la largeur du navigateur et de l’orientation.
4. Choisir le numéro de carte Anki d’un rectangle. Plusieurs rectangles de même numéro forment une carte ; des numéros différents donnent plusieurs cartes.
5. Afficher **Aperçu masqué** pour chaque numéro, puis vérifier sa case de validation sous l’éditeur. **Révéler** et **Image seule** montrent les réponses et la source intacte.
6. Valider la fidélité de la note puis préparer le `.apkg`. Une carte non prévisualisée ou non validée ne peut pas être exportée. Toute modification des rectangles, de leurs numéros ou du contenu annule la validation et l’ancien téléchargement.

Le composant est local, sans bibliothèque JavaScript chargée depuis un tiers. Il utilise SVG et Pointer Events, avec capture du pointeur et gestion de `pointercancel`. La vue de défilement évite de dessiner pendant la navigation. Limites : 500 rectangles et 99 numéros par note ; tailles minimales de 8 pixels à l’écran (zoomer pour les petites légendes).

## Images conservées

| PDF / nº | Contenu | Images source |
|---|---|---:|
| Biologie 7 | Classification du vivant | 1 |
| Biologie 15 | Groupes fonctionnels | 2 |
| Biologie 19 | Quatre groupes de macromolécules | 1 |
| Biologie 31 | Exemples d’acides aminés | 1 |
| Biologie 32 | Vingt acides aminés | 1 |
| Biologie 50 | Transport de protéines | 1 |
| Biologie 52 | Maladie de Tay-Sachs | 1 |
| Anthropologie 9 | Totémisme / Naturalisme / Animisme / Analogisme | 1 |

Les images extraites non masquées restent inchangées. Une image unique est réutilisée byte pour byte comme base native. Pour Biologie 15, un canevas non masqué compose les deux images selon leurs positions et leur espacement PDF ; les deux fichiers extraits originaux sont aussi conservés dans le paquet et accessibles dans un volet du verso. Les masques restent des formes séparées : aucun rectangle n’est peint dans les pixels.

Le PDF original, les images et le manifeste des masques sont conservés dans le ZIP source. Les coordonnées sont liées au hash du canevas ; une image modifiée ne peut pas réutiliser une validation précédente. La composition multi-image actuelle concerne une page PDF ; une note Occlusion à images réparties sur plusieurs pages est conservée avec avertissement et n’est pas exportée automatiquement.

## Export réellement natif

Quand la sélection inclut une Occlusion, `native_export.py` prépare les données et lance un **processus Anki isolé par export**. Il importe les Basic/Cloze du chemin existant, puis crée les notes via `Collection.add_image_occlusion_note()` avec le modèle officiel :

- type Cloze et **`originalStockKind == 6`** ;
- champs/tag natifs Occlusion, Image, Header, Back Extra, Comments ;
- formes `{{c1::image-occlusion:rect:left=…:top=…:width=…:height=…:oi=1}}` ;
- templates `anki.imageOcclusion.setup()` et `image-occlusion-canvas`.

L’archive est exportée par Anki, réimportée dans une autre collection et vérifiée avant téléchargement : nombres de notes/cartes, GUID, champs Basic/Cloze, type natif, coordonnées et groupes de masques, image et médias par SHA-256. Le réimport du même paquet est testé sans duplication. Le vérificateur ne suppose pas qu’une archive native moderne a la structure SQLite legacy de `genanki`.

Si seules des Basic/Cloze sont incluses, leur chemin d’export précédent reste disponible. Aucun échec natif ne déclenche un remplacement silencieux par une image ou une note Basic.

Références officielles : [modèle](https://github.com/ankitects/anki/blob/main/rslib/src/image_occlusion/notetype.rs), [formes et propriétés](https://github.com/ankitects/anki/blob/main/rslib/src/image_occlusion/imageocclusion.rs).

## Vérifications exécutées

- Les huit notes réelles sont d’abord vérifiées **sans aucun masque initial**.
- Les tests leur attribuent explicitement des rectangles géométriques **de contrôle uniquement**, simulent aperçu/validation et exportent les trois documents : **73 Basic, 4 Cloze et 8 notes Occlusion**. Ces rectangles de test ne sont ni préchargés dans l’application ni proposés comme réponses pédagogiques.
- Le moteur officiel importe les huit notes puis modifie leur masque via `update_image_occlusion_note()` ; l’image reste identique et les formes demeurent natives et éditables.
- Regroupement de rectangles, numéros distincts, refus d’export avant revue, modification en cours, changement d’image, événements répétés/périmés et messages rapprochés sont couverts.
- Chromium teste le toucher émulé (dessiner, déplacer, redimensionner, défiler), les événements de stylet synthétiques, l’annulation, le regroupement, le zoom et le changement de largeur.
- Un vrai serveur Streamlit local teste l’import PDF, le composant, l’aperçu, les validations, le téléchargement et son invalidation après modification. Le changement de carte doit préserver les zones enregistrées et laisser une nouvelle note vierge.

## Limites clairement distinguées

**Pas de test physique sur Safari iPad ni Apple Pencil.** Le toucher est émulé dans Chromium ; les événements de stylet sont synthétiques. Le rejet de paume, les interruptions système d’iPadOS et le comportement du Pencil réel doivent encore être essayés sur l’appareil.

Le moteur officiel Anki 26.9.3 a vérifié import, édition des masques et HTML natif ; l’exécution graphique du canevas dans le client Anki de l’utilisateur n’a pas été testée. Aucun masque pédagogique des huit schémas n’est considéré validé sans intervention de l’utilisateur.

La dépendance serveur est `anki==26.9.3`, roue Linux `manylinux_2_35` utilisée ici avec Python 3.12. La compatibilité de l’hébergeur final (notamment glibc ≥ 2.35) devra être contrôlée avant tout déploiement, qui n’est pas effectué par cette PR. Aucun logiciel local ni service payant n’est requis pour utiliser l’éditeur web.
