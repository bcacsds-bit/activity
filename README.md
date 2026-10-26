# CAMPUS UNLOCKED — QR awareness simulation

A Flask prototype for an institution-approved campus QR-code engagement and awareness activity.

## Before use

This is a prototype, not a security-audited production application. Do not deploy publicly or collect real personal data until the college approves the exact purpose, privacy notice, access controls, hosting arrangement, retention date, and deletion procedure.

The landing page preserves the surprise about the later cybersecurity lesson, but it must not conceal that name, phone number, email, and campus role are collected to administer the Campus Unlocked activity. Replace every privacy placeholder with approved details. Participation consent and optional future-update consent are separate.

## Local run

1. Install Python 3.10+.
2. Create and activate a virtual environment.
3. Install dependencies: `pip install -r requirements.txt`
4. Set secrets:

   ```bash
   export FLASK_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
   export QRTRAP_ADMIN_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
   ```

5. Start the app: `python app.py`
6. Open `http://127.0.0.1:5000`.

## Admin summary

The admin route is disabled unless `QRTRAP_ADMIN_TOKEN` is set. Example:

```bash
curl -H "X-Admin-Token: YOUR_TOKEN" http://127.0.0.1:5000/admin/summary
```

Do not put the admin token in a URL, poster, repository, or browser-side code. A production deployment should use institutional SSO or a VPN and an approved database.

## Required deployment safeguards

- Fill in the privacy notice's authorised office/contact and specific deletion date.
- Configure a strong `FLASK_SECRET_KEY`; remove the development fallback.
- Serve over HTTPS and set `COOKIE_SECURE=1`.
- Use a supported production server behind a correctly configured HTTPS reverse proxy; do not expose Flask's development server.
- Have IT review authentication, authorisation, rate limiting, database access, backups, hosting provider logs, and data location.
- Restrict identifiable registrations to named, authorised staff.
- Define deletion of live records and applicable backups; test it before launch.
- Do not collect passwords, student IDs, financial information, or unnecessary identifiers.
- Remove posters at the end of the approved campaign.
- If participants include minors, obtain institution-specific guidance before launch.

## Metrics and limitations

Landing-page visits are requests, not confirmed scans or unique people. Registrations and reveal acknowledgements are counted separately. The app does not intentionally store IP addresses, browser fingerprints, user-agent strings, or referrers. Server/hosting logs may still collect technical data; configure and review those separately.

The prototype does not include email delivery, automated deletion, institutional SSO, a hardened admin interface, or production-grade rate limiting. It requires review before public deployment.


## Visual refresh (v3)
The landing page now uses a premium campus-exclusive drop aesthetic, a gold gift illustration, and the quote “ALL THAT GLITTERS IS NOT GOLD.” The post-submission reveal delivers the cybersecurity lesson more directly. This remains a prototype; complete and approve the privacy notice, deletion workflow, hosting, and security controls before collecting real participant data.

The quote “ALL THAT GLITTERS IS NOT GOLD” is intentionally shown only on the post-submission reveal page, not on the landing/home page, to preserve the surprise.


## Branding and response-reporting additions
- Shared header/footer brand the Department of Cyber Security with Data Science, The Anonymous Lab (Department Association), and Cipher X (Department Club) on both the landing and reveal pages.
- The reveal page includes a short optional feedback survey.
- Feedback is stored in the events table without names, phone numbers, email addresses, registration IDs, or session IDs.
- Restricted admin summary (`/admin/summary`, with `X-Admin-Token`) shows aggregate feedback counts.
- Restricted CSV export (`/admin/feedback.csv`, with `X-Admin-Token`) exports aggregate response counts only.
- A report template is supplied separately. Populate it only with real campaign results; do not present blank or example counts as collected data.

This is still a prototype. Before collecting real data, review privacy and security, replace all privacy notice placeholders, implement the approved deletion process, use institution-approved HTTPS hosting, and restrict administrative access.


## Render + hosted PostgreSQL deployment

This package supports a PostgreSQL `DATABASE_URL` for hosted deployments and keeps SQLite for local use. Before collecting real personal information, obtain institutional approval and replace all privacy placeholders. This is still a prototype and has not undergone a security audit.

1. Create a PostgreSQL database with a provider that suits your retention needs (for example, Neon). Copy its pooled/direct connection string and ensure SSL is required.
2. Push this folder to a private GitHub repository (do not commit `.env`, real secrets, or a database URL).
3. In Render, create **New → Web Service** and connect the repository.
4. Build command: `pip install -r requirements.txt`
5. Start command: `gunicorn app:app`
6. Add environment variables in Render: `DATABASE_URL`, a random `FLASK_SECRET_KEY`, a separate random `QRTRAP_ADMIN_TOKEN`, and `COOKIE_SECURE=1`. Do not add the database password to the repository.
7. Deploy and test `/health`, the registration flow, reveal page, anonymous feedback, and reporting/export before distributing the QR code.
8. Export and verify the report data after the activity. Confirm the database provider's free-tier limits and retention terms; do not assume free-tier data is backed up indefinitely.

**Important:** Render free web services sleep when idle and their local filesystem is ephemeral. This app uses the hosted PostgreSQL database whenever `DATABASE_URL` is configured, so submissions are not stored on the web service's temporary disk. Free-tier uptime, limits, and retention still apply. The app's current admin page displays identifiable registration details; restrict it and the admin token to authorised staff only.
