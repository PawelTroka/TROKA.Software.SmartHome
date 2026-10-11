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

## Fizyka public routes

`fizyka.dk` is hosted on the same machine through its dedicated Fizyka Cloudflare
Tunnel connector. HTTPS `www.fizyka.dk` and `alpha.fizyka.dk` redirect to the apex;
`old.fizyka.dk` serves the independent read-only, noindex reference. These routes
and the application's origin policy are owned by
[PhysicsForEveryone](https://github.com/PawelTroka/PhysicsForEveryone), not this
repository's Traefik configuration. Do not duplicate the origin or tunnel in
the SmartHome Compose stack. See [Fizyka hosting boundaries](fizyka-hosting.md)
for ownership, cleanup exclusions and recovery links.
