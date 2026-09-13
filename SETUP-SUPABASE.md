# Connecting Supabase

Takes about ten minutes. Until it is done the site works exactly as it does now —
the **Add a listing** button falls back to opening a GitHub issue, so nothing is lost.

## 1. Create the project

1. Go to **<https://supabase.com>** → sign in with GitHub → **New project**
2. Name it `design-jobs-india`, pick the **Mumbai (ap-south-1)** region — it is closest,
   so the site stays fast in India
3. Set a database password and save it somewhere. You will not need it again for this.
4. Wait for the project to finish provisioning

## 2. Create the tables

1. In the left sidebar open **SQL Editor** → **New query**
2. Open `supabase/schema.sql` from this repo, copy the whole file, paste it in
3. Press **Run**

You should see `Success. No rows returned`. That is correct — it created tables,
not data.

## 3. Copy the two public keys into the site

**Settings → API**, then copy:

| Supabase calls it | Put it in `site/config.js` as |
|---|---|
| Project URL | `SUPABASE_URL` |
| `anon` `public` | `SUPABASE_ANON_KEY` |

```js
window.DJI_CONFIG = {
  SUPABASE_URL: "https://abcdefgh.supabase.co",
  SUPABASE_ANON_KEY: "eyJhbGci...",
};
```

Commit and push. **Both of these are safe to publish** — row-level security decides
what the anon key may do, which is: insert a pending submission, and read approved
listings. Nothing else.

## 4. Add the private key to GitHub Actions

Still on **Settings → API**, reveal the **`service_role`** key.

> This one is not safe to publish. It bypasses row-level security entirely.
> It goes only in GitHub secrets and your local `.env` — never in `site/config.js`.

Repo → **Settings → Secrets and variables → Actions → New repository secret**, twice:

| Name | Value |
|---|---|
| `SUPABASE_URL` | the same project URL |
| `SUPABASE_SERVICE_KEY` | the `service_role` key |

## 5. Check it works

Open the site, click **+ Add a listing**, submit something test.

Then in Supabase → **Table Editor → submissions**, you should see the row with
`status = pending`.

## Approving submissions

Nothing a stranger submits ever appears publicly until you approve it. In Supabase →
**Table Editor → submissions**, change `status` from `pending` to `approved`. The next
hourly run pulls it in and it shows on the site tagged `community`.

To reject, set it to `rejected` — the row stays for your records but never publishes.

### Why a bot cannot flood the site

- Row-level security only permits inserting rows with `status = 'pending'`, so a
  submission cannot approve itself no matter what the browser sends.
- The form carries a hidden honeypot field. A human never sees or fills it; scripts
  fill everything. The database policy rejects any row where it is non-empty.
- `fill_seconds` records how long the form was open. A submission completed in under
  two seconds was not typed by a person — useful when reviewing the queue.
- The public can only read `status = 'approved'`, so an unreviewed queue is invisible.

The worst outcome of a bot attack is a longer moderation queue, never a polluted site.

## Local development

```bash
cp .env.example .env      # then fill in SUPABASE_URL and SUPABASE_SERVICE_KEY
./run.sh sync pull        # bring approved submissions into the local database
./run.sh sync push        # mirror listings up
```
