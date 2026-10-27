# Anki Studio V2

Prototype Streamlit gratuit, utilisable depuis Safari sur iPad.

## Déploiement sur GitHub

Remplacez les fichiers `app.py`, `requirements.txt` et `README.md` à la racine de votre dépôt GitHub par ceux de cette archive. Faites **Commit changes**. Streamlit Community Cloud redémarre normalement automatiquement l'application.

## Nouveautés

- Découpe des sections par marqueurs `CARTE`, `CARTE CLOZE`, `CARTE OCCLUSION`.
- Aperçu de la **zone du PDF original** correspondant à la carte, même pour les PDF d'une seule page très longue.
- Prévisualisation recto/verso et édition HTML.
- Aperçu des images présentes dans les sections.
- Export `.apkg` avec médias pour les documents ne contenant que des cartes classiques.
- Blocage de l'export complet si des cartes Cloze ou Occlusion sont présentes.

## Limites connues

- L'indentation est estimée par les positions horizontales et doit être vérifiée.
- Les images sont ajoutées après le texte, pas nécessairement à leur position exacte.
- Les clozes et occlusions ne sont pas encore exportables.
- Le PDF est envoyé au serveur Streamlit lors de l'import, même si aucune API d'IA n'est utilisée.
- Les PDF très volumineux peuvent dépasser les ressources du service gratuit.
- Cette V2 est un prototype de test, pas une conversion garantie fidèle.
