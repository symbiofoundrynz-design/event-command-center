# Verification record — staged GitHub candidate

## Scope of validation

Current package is created from a reviewed private ZIP in a new staging directory. No private host, existing database or external repository was modified. Archive extraction was path-checked. Static analysis and self-contained app route checks are described below; the separate live Docker/PostgreSQL acceptance section records additional runtime testing.

## Verified in isolated staging (2026-11-16 NZDT)

- Original 28 MB deployment ZIP opened and inventoried. Only source application files were selectively carried into the candidate; original event media, offline wheels, client configuration and production installer were excluded.
- Python application and local secret generator passed `py_compile`; both client-side JavaScript files passed `node --check`.
- All **11 Python unittest cases PASS** using local isolated dependencies (Flask 3.1.3, Werkzeug 3.1.8, Psycopg 3.3.4). No real PostgreSQL instance was accessed.
- Nginx 1.26.3 accepted the substituted reverse-proxy configuration through `nginx -t`.
- **11 local reverse-proxy HTTP checks PASS:** guest home/RSVP/static access, blocked guest admin routes/API/admin CSS, accessible private operator dashboard/API, private photo access restricted to the operator side, and guest-supplied operator-key spoofing rejected.
- Source text scanned for original client names, private network addresses, host-specific install paths and contact email addresses. No original client identifiers were found in published application code, templates or README.
- No GitHub repository, live deployment, Foundry Library artifact, service, database or Tailscale Funnel was changed by these tests.

## Checks to run or repeat on a clean machine

```bash
python3 -m compileall -q app scripts tests
node --check app/static/guest-site.js
node --check app/static/dashboard.js
python3 -m unittest discover -s tests -v
# After generating .env on a disposable host:
docker compose config -q
docker compose up --build -d
curl -i http://127.0.0.1:8080/
curl -i http://127.0.0.1:8080/dashboard     # expect 404
curl -i http://127.0.0.1:8080/api/dashboard/state  # expect 404
curl -i http://127.0.0.1:8081/dashboard     # expect 200
```

Expected status checks were repeated on the isolated Docker network/host for v0.2; repeat them on any fresh deployment. Never use a real production database or photo volume for this test.

## Live isolated Docker/PostgreSQL acceptance — 2026-11-16 NZDT

Isolated runtime testing was approved and performed on a Linux Docker host against the v0.2 archive SHA-256 `fb1dcb75f1c72661bc14f2ec6cf7c8608837fffa3aa7740f08bf2f2189440dba`. This subsequent packaging revision changes public documentation only; application and artwork bytes are unchanged. Source manifest and ZIP integrity PASS. Docker Engine 29.1.3, Compose v2.40.3, PostgreSQL 17-alpine and Nginx stable-alpine. Both host ports were loopback-bound (`127.0.0.1:8080` guest, `127.0.0.1:8081` operator). No Tailscale Funnel use, original event system changes or GitHub publication.

Observed checks:
- Docker Compose configuration, image pulls and app image build PASS; all three `db`, `app`, `web` containers healthy.
- Live HTTP surface checks **16/16 PASS**: guest pages/API/visuals available, guest operator paths and forged admin header blocked, operator interface functional.
- Fictional RSVP submission and dashboard readback PASS; PostgreSQL record and aggregate counters persisted after Compose container teardown/recreation with named volumes preserved.
- Seeded content version recognized; draft remained unpublished; cross-origin mutation rejected; new publication visible; version restoration returned to original demo state; synthetic RSVP preserved.
- Fictional photo upload and operator library PASS; unpublished photo inaccessible on public ingress; publish/unpublish and media access revocation PASS; final photo remained private.
- Invitation preparation/status and public isolation PASS; no actual emails sent.
- Run sheet and checklist CRUD PASS. Budget and vendor CRUD PASS on corrected numeric-aware acceptance assertions; a prior strict numeric-type assertion failed in test harness, not the application. Test-added operational records removed afterward.
- Fictional CSV import, two attendees, soft deletion and restoration PASS; final imported record soft-deleted and audit history retained.
- Pre-existing host services were not intentionally modified during these tests.

These are runtime acceptance checks on a disposable isolated project, not penetration testing or a production acceptance certificate. Internal execution receipts are retained separately and are not part of the public repository.

## Not verified / deliberately deferred

- Tailscale Funnel start/stop, external HTTPS connectivity or internet-facing deployment
- Production threat-model/penetration assessment, rate limiting, public-form abuse controls, comprehensive CSRF analysis
- Database backup and restore and disaster recovery
- Formal mobile/cross-browser and accessibility evaluation, actual guest privacy/retention notices
- HEIF and unusual-media upload handling, performance/load testing
- Exact upstream dependency/license/vulnerability inventory for a pinned installation date
- Provider-specific/third-party image rights beyond those licensable by SymbioFoundry; copyright protection of AI-generated material can vary by jurisdiction. The owner approved separate CC BY 4.0 redistribution terms to the extent of held rights (2026-11-16).

**State: OWNER-APPROVED SOURCE PUBLICATION CANDIDATE — core isolated runtime acceptance PASS; GitHub publication and CC BY 4.0 image terms approved 2026-11-16, to the extent of held licensable rights. Not production accepted.**

## v0.2 fictional visual integration — 2026-11-16

- The owner approved the v0.2 fictional visual selection for integration. Six WebP exports were checked against the supplied manifest by SHA-256 and dimensions. No composite source image or original client photograph is included.
- CSS hero references `app/static/demo/ecc-demo-hero.webp`; four gallery assets are displayed only when the published photo list is empty. Existing published-photo behavior is retained.
- Guest Nginx ingress now allowlists `/static/demo/` only in addition to its original explicit guest CSS/JS routes. Operator-facing static resources remain blocked from the guest ingress.
- See accompanying candidate integration receipt for actual validation results. Isolated Docker/PostgreSQL end-to-end acceptance remains outstanding.
- The owner subsequently approved public redistribution terms for the demo images under CC BY 4.0 (to the extent of held licensable rights). The subsequent live runtime checks above supersede the original pre-Docker staging limitation.
