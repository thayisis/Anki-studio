# Passages Basic et Cloze corrigés — 1 novembre 2026

Les dix passages ont été relus dans les zones correspondantes des PDF fournis. Les corrections s’appliquent seulement si le **passage complet** et le type correspondent à une entrée de `reviewed_passages.json`. Elles ne dépendent ni du numéro de carte, ni du nom de fichier. Les espaces de composition peuvent varier ; la transcription du fichier JSON ne remplace jamais les caractères du PDF dans le verso.

Ce sont des répartitions et annotations explicitement revues pour ces cours, pas une promesse de compréhension sémantique de tous les PDF. Un passage différent ne reçoit aucune de ces corrections. En cas de cible coupée différemment ou ambiguë, la carte reste conservée avec un avertissement et doit être corrigée dans l’éditeur.

## Six Basic résolues

| PDF / nº source | Recto propre | Verso |
|---|---|---|
| Biologie 16 | Polymère | `Polymère = assemblage de monomères similaires (ex. amidon)` |
| Biologie 17 | Déshydratation | `Déshydratation : assemblage de monomères par élimination d’eau` |
| Biologie 18 | hydrolyse | `hydrolyse : rupture de la liaison par intervention d’eau` |
| Biologie 54 | Symbiose | `Symbiose : association étroite entre deux espèces différentes vivant ensemble pour un bénéfice mutuel` |
| Anthropologie 7 | Descola — La « nature domestique » | Les trois lignes originales, de `La « nature domestique » est  utilisé…` à `de la culture`, intégralement et dans l’ordre. |
| Anthropologie 8 | Descola — Par delà nature et culture | Les trois lignes originales, de `Écrit « Par delà nature et culture »…` à `ordres « Pq je suis moi et pas qlqun d’autres»)`, intégralement et dans l’ordre. |

La casse, les fautes du cours, les doubles espaces et les caractères sont conservés au verso. Le concept du recto est un extrait littéral, sans question ou fait inventé. Le mot-concept est aussi présent dans la phrase source au verso : cette répétition est volontaire pour conserver la définition complète, plutôt que la tronquer. La récupération du titre source est déjà effectuée une seule fois ; les enregistrements ultérieurs ne peuvent pas le rajouter.

## Quatre Cloze natives résolues

| PDF / nº source | Cible exacte de `c1` | Contexte visible dans la question |
|---|---|---|
| Biologie 5 | un apport continu d’énergie | Systèmes vivants en état de non-équilibre —> nécessite […] |
| Biologie 6 | changements évolutifs | La diversité du vivant résulte des […] |
| Biologie 55 | l’endosymbiose | Théorie de […] pour l’origine des mitochondries et chloroplastes, suivie de toute la justification originale. |
| Anthropologie 2 | sous-cultures | La culture n’est pas qu’ethnique, les métiers par exemple crée des […], avec toute la suite originale. |

Les PDF indiquent seulement `CARTE CLOZE` : **ils ne contiennent pas d’annotations désignant ces cibles**. Les suppressions sont des choix pédagogiques proposés sur demande, littéraux et modifiables, pas une récupération prétendue des intentions de l’auteur. Aucune correction de grammaire ou information de cours n’est ajoutée.

Chaque passage complet devient le champ natif `Text`, avec une suppression `{{c1::…}}`. Un titre d’affichage séparé n’est pas préfixé au champ `Text`, ce qui évite de révéler la réponse ou répéter le passage. Chaque note donne une carte ; la validation humaine reste obligatoire avant export. L’éditeur montre les annotations ; les aperçus recto/verso masquent et révèlent la suppression active.

## Vérifications exécutées

- Texte de chaque verso reconstruit sans annotations Cloze **strictement égal aux lignes source**, espaces et ponctuation inclus.
- Rectos extraits des passages source ; contexte Descola confirmé et conservé.
- Un `c1` unique par Cloze, cible absente de la question visible et présente dans la réponse.
- Tests sur les PDF réels et fixtures synthétiques Unicode sans fichiers privés pour la CI.
- Fidélité Poppler des trois PDF maintenue ; le titre-concept dérivé n’est pas compté une seconde fois comme contenu source.
- Import des paquets réels et rendu des quatre Cloze par le moteur officiel Anki 26.9.3.

Les six Basic et quatre Cloze ne sont plus des exclusions techniques : les exports de test comprennent **73 Basic + 4 Cloze = 77 notes/cartes**, avant validation pédagogique de l’utilisateur. Les huit Occlusions restent distinctes : voir [NATIVE_OCCLUSION.md](NATIVE_OCCLUSION.md).
