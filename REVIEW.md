# Revue critique de la PR nº 1

La branche a été revue sans fusion et sans déploiement. **L’ancien bilan « 45 tests passent / 73 Basic exportées » ne suffisait pas à démontrer la fidélité ni l’utilisabilité.** Des vérifications indépendantes et des imports Anki réels ont été ajoutés.

## Défauts confirmés et corrigés

| Priorité | Module | Défaut avant revue | Correction / preuve |
|---|---|---|---|
| Haute | `exporter.py` | Six Basic avec verso vide passaient dans l’export après validation. | Protection générique par exclusion des versos vides ; les six passages sont maintenant répartis explicitement et intégralement depuis les PDF (voir CARD_CORRECTIONS.md). Tests réels : Bio 16/17/18/54, Anthropo 7/8. |
| Haute | `engine.py` | Le plan d’alinéas pouvait reprendre un long paragraphe précédent comme parent de titres d’anthropologie. | Les paragraphes enveloppés ne deviennent plus des labels de section sans preuve typographique. Tests sur toutes les cartes concernées et fixture synthétique ; contexte Descola maintenu. |
| Moyenne | `engine.py` | Le chiffre plus petit de O2 devenait de taille normale : la comparaison du texte seul masquait cette différence scientifique. | Conservation des tailles et décalages des fragments PDF dans le HTML ; caractères inchangés. Test sur la carte Protéines du PDF de biologie et fixture synthétique. Si une ligne est éditée, les anciens fragments ne remplacent jamais le nouveau texte. |
| Moyenne | `engine.py` | Les mappings Unicode de Wingdings pouvaient afficher ®, § ou } comme puces au lieu de leur forme imprimée. | Normalisation des seules puces en •, numérotation conservée, vrais symboles dans le texte inchangés. |
| Moyenne | `app.py` | La récupération du titre source pouvait dupliquer le texte après plusieurs enregistrements ; les niveaux JSON ne suivaient pas toujours les retraits édités. | Récupération idempotente et désactivée après usage ; recalcul des niveaux ; tests de relances réelles AppTest. Les modifications annulent validation et téléchargements. |
| Moyenne | `exporter.py` | Le contrôle des modèles ne comparait que le recto ; le manifeste source pouvait conserver un verso dérivé périmé si les blocs avaient été modifiés. | Contrôle des deux templates et recalcul du verso dans le manifeste. Import et rendu recto/verso avec le moteur officiel Anki. |

## Étendue du contrôle

- Les trois PDF, 85 marqueurs et 93 occurrences d’images ; aucun cours privé ajouté au dépôt.
- 556 lignes textuelles non vides : décodage Poppler indépendant, mots et ponctuation comparés au HTML, vérification d’absence de mots non représentés, retraits mesurés et ordre des médias rendu.
- Cartes réelles Glandes exocrines / Mérocrine / Apocrine, avec texte exact et contexte ; transition Morphologie ; cas d’anthropologie où le parent était un paragraphe.
- Depuis la correction des dix passages : import réel de 73 Basic et 4 Cloze dans trois collections temporaires Anki ; import d’un Cloze synthétique à deux cartes et aller-retour d’une Occlusion native synthétique ; champs et médias contrôlés, questions/réponses rendues par Anki. Aucun appel à un service payant.
- Relecture de l’interface, dépendances, documentation, exclusions Git et CI : le job natif Anki est isolé ; aucune étape de déploiement. Les tests privés restent explicitement ignorés quand les PDF sont absents, sans être décrits comme vérifiés.

## Décision

**Ne pas considérer cette revue comme une autorisation de fusionner ou déployer.** Les défauts confirmés ont été corrigés et les résultats de test renforcés. Les six Basic et les quatre Cloze sont maintenant résolues sur les passages fournis : voir [CARD_CORRECTIONS.md](CARD_CORRECTIONS.md). Les huit Occlusions sont maintenant prises en charge par l’éditeur manuel et l’export natif vérifié par Anki, détaillés dans [NATIVE_OCCLUSION.md](NATIVE_OCCLUSION.md). La validation Safari iPad, les petites légendes dans les images et la revue sémantique exhaustive des titres ne sont pas démontrées.

Voir [VALIDATION.md](VALIDATION.md) pour les commandes, résultats et limites précises.
