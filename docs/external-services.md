# External service settings

These settings live outside Docker and Git, but are required for the public
home-server routes to behave as expected.

## Cloudflare

The `troka.software` zone has **Always Use HTTPS** enabled under SSL/TLS > Edge
Certificates as of 2026-08-21. This applies to the apex and proxied subdomains.
A raw HTTP request must be answered at the Cloudflare edge without reaching the
home router:

```sh
curl -I http://troka.software/
curl -I http://cloud.troka.software/status.php
```

Both checks should return `301 Moved Permanently` with the same HTTPS URL in the
`Location` header. Do not create or store Cloudflare API tokens in this
repository; restore this setting manually through the Cloudflare dashboard.
