# H04b local Docker OIDC acceptance

This fixture runs the complete protocol flow on the local machine:

- Keycloak provides discovery, Authorization Code + PKCE, tokens, JWKS, and logout.
- nginx terminates HTTPS for `idp.localhost`, `ui.localhost`, and `gateway.localhost` on port 8443.
- data-ui receives the callback at `https://ui.localhost:8443/auth/callback`.
- the Rust gateway validates access tokens with JWKS, issuer, audience, expiry, and role bindings.

Run from `data-proxy/`:

```bash
./examples/smoke-h04b-docker.sh
```

The smoke writes builds, certificates, browser artifacts, and the report below
`/Volumes/fushilu/.caches/data-nexus/h04b`. It uses fixed local-only accounts and a local CA;
no secrets or generated output are written to Git. A public cloud server is not required for
protocol and role-mapping acceptance. Public DNS, a publicly trusted certificate, firewall rules,
and the production IdP tenant remain deployment checks.
