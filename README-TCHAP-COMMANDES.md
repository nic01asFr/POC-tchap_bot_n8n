# Commandes Tchap intégrées

Ce bot intègre les commandes spéciales de Tchap, permettant d'envoyer des messages avec des formats et effets spéciaux. Ces commandes sont directement inspirées des commandes natives de Tchap.

## Commandes de formatage

| Commande | Description | Exemple |
|----------|-------------|---------|
| `!spoiler` | Envoie le message flouté | `!spoiler Ceci est un secret` |
| `!shrug` | Ajoute ¯\\\_(ツ)\_/¯ en préfixe du message | `!shrug Peu importe` |
| `!tableflip` | Ajoute (╯°□°）╯︵ ┻━┻ en préfixe du message | `!tableflip C'est inacceptable` |
| `!unflip` | Ajoute ┬──┬ ノ( ゜-゜ノ) en préfixe du message | `!unflip Restons calmes` |
| `!lenny` | Ajoute ( ͡° ͜ʖ ͡°) en préfixe du message | `!lenny Intéressant` |
| `!plain` | Envoie un message en texte brut, sans interprétation Markdown | `!plain # Ceci n'est pas un titre` |
| `!html` | Envoie un message en HTML | `!html <b>Texte en gras</b>` |
| `!me` | Affiche une action | `!me réfléchit au problème` |

## Effets visuels

| Commande | Description | Exemple |
|----------|-------------|---------|
| `!rainbow` | Envoie le message coloré aux couleurs de l'arc-en-ciel | `!rainbow Message multicolore` |
| `!rainbowme` | Envoie une action colorée aux couleurs de l'arc-en-ciel | `!rainbowme danse joyeusement` |
| `!confetti` | Envoie le message avec des confettis | `!confetti Félicitations !` |
| `!fireworks` | Envoie le message avec des feux d'artifice | `!fireworks Bonne année !` |
| `!hearts` | Envoie le message avec des cœurs | `!hearts Je vous adore` |
| `!rainfall` | Envoie le message avec effet de pluie | `!rainfall Il pleut aujourd'hui` |
| `!snowfall` | Envoie le message avec effet de neige | `!snowfall Joyeux Noël` |
| `!spaceinvaders` | Envoie le message avec thème spatial | `!spaceinvaders Décollage imminent` |

## Notes importantes

1. Les effets visuels sont simulés avec des émojis car les véritables effets visuels dépendent généralement de JavaScript côté client.
2. Ces commandes sont intégrées pour rendre l'interaction avec le bot plus naturelle pour les utilisateurs habitués à Tchap.
3. La syntaxe des commandes est identique à celle de Tchap, facilitant la transition.

## Différences avec Tchap natif

- Dans le bot, tous les effets sont préfixés par `!`, alors que dans Tchap certains utilisent `/`.
- Les effets visuels complexes (confettis, pluie, neige, etc.) sont simulés par des émojis plutôt que par des animations.
- Toutes les commandes fonctionnent dans tous les types de salons, sans restriction.

## Activation

Les commandes Tchap sont activées par défaut. Si vous souhaitez les désactiver, modifiez la configuration `groups_used` dans le fichier `config.py` en retirant `"tchap"` de la liste.