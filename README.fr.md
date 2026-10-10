# Ingress Checkpoint Bot

🇬🇧 [English version](README.md)

Bot Telegram léger et asynchrone qui donne les **checkpoints** et **septicycles** Ingress en heure de France.

## Fonctionnalités

- Prochain checkpoint avec décompte, checkpoints du jour, de demain ou d'une date donnée
- Prochains checkpoints à une heure précise (`/cp 14H`)
- Septicycle en cours et suivant, septicycle `yyyy.nn`, liste d'une année entière
- Heure d'été gérée (`Europe/Paris`, modifiable via `BOT_TZ`)
- Tout est calculé localement ; aucune donnée utilisateur n'est écrite sur disque
- Contrôle d'accès optionnel via [res.blue](https://res.blue) (OneRing) : seuls les agents approuvés sur 1R peuvent utiliser les commandes

## Commandes

| Commande | Effet |
|---|---|
| `/today` | Checkpoints du jour |
| `/next` ou `/cp` | Prochain checkpoint |
| `/tomorrow` | Checkpoints de demain |
| `/cp yyyy-mm-dd` | Checkpoints du jour donné |
| `/cp xxH` | Prochains checkpoints à l'heure xx |
| `/cycle`, `/sp`, `/septicycle` | Prochain septicycle |
| `/sp yyyy.nn` | Septicycle nn de l'année yyyy |
| `/sp yyyy` | Début et fin de tous les septicycles de l'année |
| `/help`, `/tos` | Aide, conditions d'utilisation |

## Prérequis

- Python 3.10+ (3.11 dans l'image Docker)
- Un token de bot Telegram (via [@BotFather](https://t.me/BotFather))

## Installation

```bash
git clone https://github.com/alithiel31/ingress-cp-bot.git
cd ingress-cp-bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Crée un fichier `.env` à la racine (modèle : `.env.example`) :

```env
TELEGRAM_TOKEN=ton_token_botfather
BOT_TZ=Europe/Paris
```

Le fichier `.env` est ignoré par Git.

### Authentification res.blue (optionnelle)

Renseigne `ONERING_APIKEY` dans `.env` (onglet API de ton profil OneRing ; le propriétaire de la clé doit avoir un score d'au moins 5).
Le bot vérifie alors l'ID Telegram de chaque utilisateur via `GET /api/v1/agent-info?telegramid=…` et ne sert
que les agents **approuvés sur 1R** ; `/start`, `/help` et `/tos` restent publics. Sans clé, le bot est public.
Les résultats sont gardés en mémoire (1 h si approuvé, 5 min si refusé) pour rester sous la limite de
100 requêtes/heure, et l'ID Telegram est transmis à res.blue. Si res.blue est injoignable, l'accès est refusé.

## Lancer

```bash
python main.py
```

### Avec Docker

```bash
docker compose up -d --build
docker compose logs -f
```

L'image tourne avec un utilisateur non-root. Le bot écrit un *heartbeat* toutes les 30 s dans
`/app/data` (volume `bot_data`) ; le `HEALTHCHECK` passe le conteneur en `unhealthy` s'il a plus de 2 minutes.

## Tests

```bash
python -m unittest discover -s tests -v
```

La CI GitHub Actions (`.github/workflows/ci.yml`) lance les tests puis construit l'image Docker.

## Fonctionnement

- Checkpoint : un toutes les 5 h (multiples de 5 h du timestamp Unix, UTC).
- Septicycle : 35 checkpoints = 175 h (multiples de 175 h du timestamp Unix).
- Numérotation `yyyy.nn` : n-ième septicycle dont le début tombe dans l'année `yyyy` (heure locale),
  à partir de 1. C'est une convention du bot : `cycle_label()` dans `ingress.py` si tu veux l'adapter.

## Structure

- `main.py` : branchement Telegram (python-telegram-bot), heartbeat
- `commands.py` : commandes → texte de réponse
- `ingress.py` : calculs purs, sans dépendance
- `auth.py` : authentification res.blue (OneRing) optionnelle, avec cache en mémoire
- `tests/` : tests unitaires

## Confidentialité

Voir [PRIVACY.md](PRIVACY.md).

## Licence

[MIT](LICENSE)
