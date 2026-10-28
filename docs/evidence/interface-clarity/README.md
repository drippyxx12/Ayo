# Interface clarity previews

`overview-390.png` and `overview-1440.png` show the current Jinja dashboard at mobile and desktop widths, rendered locally in Chromium using explicitly synthetic, nonpersonal fixture data. They are static UI previews, not live research results or screenshots of the hosted deployment. No account, credential, customer data or external provider was used.

Actual application browser verification is recorded separately in [interface-clarity-browser.json](../interface-clarity-browser.json): 135 HTTP and 135 screen checks at 390px, 768px and 1440px, using a disposable local PostgreSQL schema and offline fixtures. These include registration, research filtering/comparison, work, conversations, tenant isolation and reopening after login.
