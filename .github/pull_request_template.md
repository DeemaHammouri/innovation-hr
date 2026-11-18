## What and why

<!-- One or two sentences: what changes, and the problem it solves. -->

## How it was checked

- [ ] Backend tests pass on SQLite (`python manage.py test --noinput`)
- [ ] Backend tests pass on PostgreSQL (if the change touches the database, locks or migrations)
- [ ] Frontend: `npx tsc --noEmit`, `npm run lint`, `npm run i18n:check`, `npm test`
- [ ] A test fails without this change and passes with it

## Checklist

- [ ] New text exists in both `en.json` and `ar.json`; layout works right-to-left
- [ ] New endpoints declare the capability they need; `docs/PERMISSIONS.md` regenerated if roles changed
- [ ] New settings or environment variables are in `backend/.env.example` and `docs/DEPLOYMENT.md`
- [ ] No secrets, personal data or database files in the diff
- [ ] Migrations included, and `makemigrations --check` shows nothing new from this change
