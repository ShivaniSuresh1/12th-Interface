# Deploying the dashboard (Streamlit Community Cloud + Supabase + Google)

Without any secrets the app runs in **local dev mode**: email accounts live in
`profiles/_accounts.json` (passwords hashed), the 6-digit code is shown on
screen instead of emailed, and "Continue with Google" is greyed out. Add the
three pieces below to turn on real accounts. Each is free.

## 1. Supabase: accounts, email codes, saved profiles (~10 min)

1. Create a project at https://supabase.com (free plan). Save the database password somewhere.
2. **SQL Editor → New query**, paste and run:

   ```sql
   create table public.student_profiles (
     student_id text primary key,
     email      text unique,
     data       jsonb not null,
     updated_at timestamptz default now()
   );
   -- Locked down: only the app's server (service_role key) can read/write.
   alter table public.student_profiles enable row level security;
   ```

3. **Authentication → Sign In / Providers → Email**: keep *Enable Email provider*
   and *Confirm email* on. Set *Email OTP Length* to 6.
4. **Authentication → Emails → Templates → Confirm signup**: replace the body with

   ```html
   <h2>Your 12th Interface code</h2>
   <p>Enter this code to confirm your email: <b>{{ .Token }}</b></p>
   ```

5. **Email sending (required for strangers to get codes).** Supabase's built-in
   sender only delivers to your own team's addresses. Under
   **Authentication → Emails → SMTP Settings**, turn on custom SMTP. The easiest
   free option is a Gmail account:
   - Turn on 2-Step Verification for that Google account, then create an
     **App password** at https://myaccount.google.com/apppasswords.
   - Host `smtp.gmail.com`, port `465`, username = the Gmail address,
     password = the 16-character app password, sender = the same address.
6. **Project Settings → API**: copy the *Project URL*, the *anon public* key and
   the *service_role* key into the `[supabase]` secrets (step 3).

## 2. Google sign-in (~10 min)

1. https://console.cloud.google.com → create a project.
2. **APIs & Services → OAuth consent screen**: External, app name
   "The 12th Interface", your email as support/developer contact. Add yourself
   (and teammates) as test users, or click *Publish app* so anyone can sign in.
3. **APIs & Services → Credentials → Create credentials → OAuth client ID**,
   type *Web application*. Under *Authorized redirect URIs* add
   - `https://YOUR-APP.streamlit.app/oauth2callback`
   - `http://localhost:8501/oauth2callback` (for testing on your laptop)
4. Copy the client ID and secret into `[auth.google]` (step 3).

## 3. Paste the secrets into Streamlit Cloud

share.streamlit.io → your app → **⋮ → Settings → Secrets**. Paste the contents of
`.streamlit/secrets.toml.example` with your real values filled in, and save. The
app restarts with real sign-in. For local testing, put the same text in
`.streamlit/secrets.toml` (gitignored) and set `redirect_uri` to the localhost URL.

## Notes

- The service_role key bypasses row-level security, so it must only ever live in
  Streamlit secrets (server side). It never reaches the browser.
- Google users and email users with the same address share one profile.
- Email sign-ins last for the browser tab; Google sign-ins are remembered by a
  cookie for 30 days.
