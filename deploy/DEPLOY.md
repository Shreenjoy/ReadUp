# Deploying ReadUp

Target: **PythonAnywhere free tier**, which is enough for a pilot of this size. The steps
below are the ones we run; nothing here is hypothetical.

## Before you start: the one-web-app constraint

A free PythonAnywhere account allows **exactly one web app**. On our account that slot is
currently held by `joys3.pythonanywhere.com`, which serves a different project. ReadUp cannot
go live on the same account without replacing it. Either upgrade the account, use a second
account, or retire the existing app first.

## Steps

```bash
# 1. In a PythonAnywhere Bash console
git clone https://github.com/Shreenjoy/ReadUp.git ~/readup
cd ~/readup
mkvirtualenv --python=/usr/bin/python3.11 readup
pip install -r requirements.txt

# 2. Secrets. Never committed; create it on the server.
cat > .env <<'ENV'
SECRET_KEY=<a long random string>
DEBUG=False
ALLOWED_HOSTS=joys3.pythonanywhere.com
GROQ_API_KEY=<your key, or leave blank for the offline fallback>
ENV

# 3. Database and demo content
python manage.py migrate
python manage.py seed_demo
python manage.py collectstatic --noinput

# 4. A real account for the grader
python manage.py createsuperuser
```

## Web tab settings

| Setting | Value |
|---|---|
| Source code | `/home/joys3/readup` |
| Working directory | `/home/joys3/readup` |
| Virtualenv | `/home/joys3/.virtualenvs/readup` |
| WSGI configuration file | replace its contents with `deploy/wsgi_pythonanywhere.py` |
| Static files URL | `/static/` |
| Static files path | `/home/joys3/readup/staticfiles` |
| Force HTTPS | on |

Then press **Reload**.

## After deploying

- Confirm `DEBUG=False` is actually in effect: a deliberate 404 should show Django's plain
  page, not a traceback.
- Run `python manage.py check --deploy` and read the warnings.
- Free web apps **expire every three months** and must be renewed from the Web tab. An
  expired app serves a placeholder page, not your site — we have been caught by this before.

## Why not Render or Railway

Both are better products for this. We stay on PythonAnywhere because the free tier needs no
card, suspends nothing after inactivity, and the pilot is six students and two tutors. The
moment ReadUp needs a worker process or a real database, the comparison in
`docs/P2-deployment.md` says to move.
