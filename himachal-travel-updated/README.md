# Himachal Travel with Gourav Shrama
Mountain Blue English-language starter website. All assets included, no dependencies besides Python 3 for the local server.

## Run on Windows
1. Extract the ZIP. Install Python 3 if needed.
2. Open the extracted folder in File Explorer. Type `cmd` in the address bar and press Enter.
3. Run `python server.py` (or `py server.py`).
4. Open http://localhost:8000 in a browser. Keep the terminal open.
5. WhatsApp booking is configured for +91 8091246213. Test the button before public launch.

The online booking form stores pending enquiries in private_bookings.sqlite3. It does not confirm availability or charge money. The database is blocked from public GET and HEAD requests. Use a local SQLite viewer to inspect enquiries. No admin interface or email notifications are included. Prices and itineraries are examples, not verified offers. The mountain illustrations are decorative, not actual destination photographs.

## Before public launch
Use verified package prices and real destination photos you have rights to use. Confirm hotel/transport arrangements, safety and seasonal constraints, business registration, taxes, insurance and any applicable permits. Add actual contact details, privacy notice, terms, cancellation/refund policy and operator identity. Use a production server with HTTPS, secure admin access, spam/rate limits, backups and appropriate data retention. Configure an approved payment gateway using server-side order creation, verified webhook signatures, and payment reconciliation; never collect card details directly. International payment capability depends on the provider and business approval. Do not deploy this local development server directly to the public internet. Static hosting alone will not run the booking API.
