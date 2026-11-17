# Himachal Travel — combined upgrade
Same Render service, GitHub folder and existing ADMIN_PASSWORD. Upload the files directly inside himachal-travel-updated, not a nested folder. Start command: python server.py. Build: python -m compileall .

BEFORE deploying: preserve existing bookings, tour edits, reviews and photos. The old version has no database export; if shell or disk access is available, take a consistent SQLite backup of private_bookings.sqlite3 using Python sqlite3 backup API. Otherwise manually record existing bookings/package details securely and retain original photos; do not deploy if losing records is unacceptable. Never commit databases or credentials to GitHub.

For durable storage attach a paid Render persistent disk at /var/data and set DATA_DIR=/var/data. Restore the database backup to /var/data/private_bookings.sqlite3 before accepting customers. Free Render storage is temporary. New Admin Panel has a private SQLite backup download. Do not use real payments until durable storage and backups are verified.

Optional payment variables RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET (test pair first). Admin confirms availability, then creates hosted payment link with agreed total and currency (INR/USD/EUR subject to merchant approval). Customer enters booking ID and email at /#track to access the link. Admin verifies payment with provider manually; no webhook, automatic refunds or automatic receipt implemented. Handle failed create calls by checking provider dashboard before retry. Cancel unpaid link before cancelling booking; paid cancellations/refunds must be handled and reconciled manually. Test mode is not real payment. Define and publish actual merchant refund/cancellation/privacy terms before activation; included text is informational only.

Optional email BREVO_API_KEY and EMAIL_FROM (verified sender). WhatsApp WA_ACCESS_TOKEN, WA_PHONE_NUMBER_ID, WA_API_VERSION, WA_STATUS_TEMPLATE, WA_TEMPLATE_LANGUAGE (default en_US). Template body parameters in order: booking reference, status, tour name. Consent required. Notifications triggered on changed booking status; provider acceptance is not delivery confirmation. No automated retries.

Admin /admin; booking tracking /#track; reviews /#reviews; sitemap /sitemap.xml. Activity metric counts homepage requests, not unique people. Gallery uses uploaded package photos. Google verification tag retained. Basic SEO only; no ranking guarantee.

Local HTTP tests passed for login, booking, status, reviews, tracking, backup and simulated payment link/status. Live provider calls, browser layout, live deployment and data migration not verified. Customer accounts, translation, coupons, PDF receipts, full analytics and refunds are not implemented.
