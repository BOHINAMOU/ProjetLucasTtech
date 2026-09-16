# Déployer LucasTech sur un VPS Hostinger

Guide pour installer le site sur votre serveur Hostinger, à côté du site
que vous y hébergez déjà. Toutes les commandes ci-dessous s'exécutent en
SSH sur le serveur (`ssh votre_utilisateur@votre_ip`).

## 0. Prérequis

- Un VPS Hostinger sous Ubuntu/Debian avec accès SSH root ou sudo.
- Nginx déjà installé (déjà le cas puisqu'un autre site y tourne).
- Un nom de domaine (ou sous-domaine) pointé vers l'IP du serveur —
  chez Hostinger, dans hPanel → Domaines → DNS, ajouter un enregistrement
  `A` vers l'IP du VPS.

## 1. Installer Python et les dépendances système

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip git nginx
# Si vous utilisez PostgreSQL en production (recommandé) :
sudo apt install -y postgresql libpq-dev
```

## 2. Créer un utilisateur dédié et cloner le projet

```bash
sudo adduser --system --group --home /home/lucastech lucastech
sudo -iu lucastech
git clone https://github.com/BOHINAMOU/ProjetLucasTtech.git ~/lucastech
cd ~/lucastech/LucasTech
```

## 3. Environnement virtuel Python

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Base de données

**Option simple (SQLite)** — fonctionne, mais évitez si le site doit
grandir : un seul fichier, pas de sauvegardes incrémentales faciles.

**Option recommandée (PostgreSQL)** :
```bash
sudo -u postgres psql -c "CREATE DATABASE lucastech;"
sudo -u postgres psql -c "CREATE USER lucastech WITH PASSWORD 'choisissez-un-mot-de-passe-fort';"
sudo -u postgres psql -c "ALTER ROLE lucastech SET client_encoding TO 'utf8';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE lucastech TO lucastech;"
```

## 5. Fichier `.env`

```bash
cp .env.example .env
nano .env
```

Remplissez au minimum :
```ini
SECRET_KEY=<généré ci-dessous>
DEBUG=False
DATABASE_URL=postgres://lucastech:motdepasse@localhost:5432/lucastech
# ou, pour rester en SQLite :
# DATABASE_URL=sqlite:////home/lucastech/lucastech/LucasTech/db.sqlite3

ALLOWED_HOSTS=lucastech.tg,www.lucastech.tg
CSRF_TRUSTED_ORIGINS=https://lucastech.tg,https://www.lucastech.tg
USE_HTTPS=False   # à repasser à True une fois le certificat SSL confirmé (étape 9)

GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
EMAIL_HOST_USER=...
EMAIL_HOST_PASSWORD=...
```

Générer une vraie `SECRET_KEY` :
```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

⚠️ Utilisez des **nouvelles** valeurs pour `GOOGLE_CLIENT_SECRET` et
`EMAIL_HOST_PASSWORD` si vous avez suivi l'audit de sécurité précédent —
les anciennes ont été exposées publiquement et doivent être régénérées
avant d'être remises en production, ici comme ailleurs.

## 6. Migrations, fichiers statiques, compte admin

```bash
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

## 7. Lancer avec Gunicorn (systemd)

Toujours en tant que root/sudo cette fois (sortir de l'utilisateur
`lucastech` avec `exit` ou `Ctrl+D`) :

```bash
sudo cp ~lucastech/lucastech/LucasTech/deploy/gunicorn.service /etc/systemd/system/lucastech.service
sudo systemctl daemon-reload
sudo systemctl enable --now lucastech
sudo systemctl status lucastech
```

## 8. Nginx

```bash
sudo cp ~lucastech/lucastech/LucasTech/deploy/nginx.conf /etc/nginx/sites-available/lucastech
sudo nano /etc/nginx/sites-available/lucastech   # adapter domaine/chemins si besoin
sudo ln -s /etc/nginx/sites-available/lucastech /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

Le site doit maintenant répondre en HTTP sur votre domaine.

## 9. HTTPS (certbot)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d lucastech.tg -d www.lucastech.tg
```

Une fois confirmé que `https://lucastech.tg` fonctionne, repassez
`USE_HTTPS=True` dans le `.env`, puis :
```bash
sudo systemctl restart lucastech
```

## Mettre à jour le site après un nouveau commit

```bash
sudo -iu lucastech
cd ~/lucastech/LucasTech
git pull
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
exit
sudo systemctl restart lucastech
```

## Dépannage rapide

- `sudo systemctl status lucastech` + `sudo journalctl -u lucastech -f` : logs Gunicorn/Django.
- `sudo tail -f /var/log/nginx/error.log` : erreurs Nginx.
- Erreur 502 : Gunicorn n'est probablement pas démarré ou le socket
  `/run/lucastech/gunicorn.sock` n'existe pas — vérifier `systemctl status lucastech`.
- Images/CSS cassés : relancer `collectstatic`, vérifier les chemins dans `nginx.conf`.
