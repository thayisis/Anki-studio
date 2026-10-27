# Anki Studio — prototype 0.1

Une première version gratuite, locale et modifiable. Interface Streamlit, comparaison PDF et carte, correction HTML et export `.apkg` des cartes classiques.

## Démarrage sur Mac

1. Installer Python 3.11+.
2. Dans le Terminal, ouvrir ce dossier : `cd /chemin/vers/anki_studio`
3. Installer : `python3 -m pip install -r requirements.txt`
4. Démarrer : `python3 -m streamlit run app.py --server.address 0.0.0.0`
5. Ouvrir sur Mac : `http://localhost:8501`.
6. Sur iPad, connecté au même Wi-Fi, ouvrir `http://ADRESSE_IP_DU_MAC:8501` (remplacer par l'IP locale du Mac). Le Mac doit rester allumé. Ne pas exposer ce serveur sur Internet sans sécurisation.

## Limitations importantes

- Il faut un PDF dont les marqueurs CARTE sont sur des lignes isolées.
- Le premier texte après CARTE devient le recto, les autres lignes le verso. C'est une **hypothèse**, à adapter à la structure exacte des PDF de l'utilisateur.
- L'indentation est déduite des coordonnées X des lignes : elle n'est pas encore validée contre les règles précises de l'utilisateur.
- Les images ne sont pas extraites ni ajoutées aux cartes. Les cartes CLOZE et OCCLUSION sont détectées, mais leur export est bloqué tant que leur prise en charge n'est pas développée.
- L'aperçu est HTML, pas un rendu garanti identique au moteur d'AnkiMobile.
- Pas de sauvegarde permanente des modifications, de tests exhaustifs, ni de validation automatique de fidélité.
- Utiliser uniquement des PDF de confiance ; le HTML des champs est affiché tel quel dans l'interface.

## Étape suivante

Tester sur un vrai PDF représentatif et définir les règles exactes de segmentation, hiérarchie, images, cloze et occlusion avant de qualifier la conversion de fiable.
