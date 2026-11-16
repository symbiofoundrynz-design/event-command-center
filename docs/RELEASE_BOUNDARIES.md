# Publication boundaries and source provenance

## Scope

A standalone, generic GitHub portfolio candidate for Event Command Center, based on an existing functioning private event-management system. Intended for one trusted host/operator, with an explicitly separated guest interface and optional external availability.

This repository is a **derivative source snapshot**, not a deployment upgrade or migration package for the existing private instance.

## Excluded from the original source packet

- Original private-client names, addresses, links, defaults and place-specific branding
- All client-themed image assets, people portraits, music and other audio (rights not independently cleared)
- Offline binary Python wheels and existing private system deployment/install script
- Real database files, credentials, user records, uploaded photographs, host service units, and operator tunnel commands

The private source packet remains separate and was **not modified** by this publication staging task. No original personal or guest records were copied.

## Changed in this candidate

- Name and default demo content generalized to Event Command Center
- Generic visitor design with fictional AI-generated guest hero and sample gallery, replacing original event-specific imagery/audio
- Isolated Docker Compose deployment using PostgreSQL, Flask/Gunicorn and two Nginx ports, localhost-only by default
- Application-side operator-key boundary and additional origin check for operator mutations
- Public gallery media checked against published photo records, not path alone
- No installed Funnel commands or privileged host-control access; operator may configure the host separately
- Sample gallery is an HTML-only fallback when the operator has no published photos; no demo photo database records, migrations or production photo volume changes
- New docs, source release boundaries and tests

The fictional demo WebP assets are distinct from original client media; their provenance and file hashes are recorded in [Demo visual assets](DEMO_VISUAL_ASSETS.md), with the owner-approved [CC BY 4.0 rights statement](../DEMO_IMAGE_LICENSE.md). The source ZIP supplied by the visual production team includes the original composite for internal provenance; it is deliberately excluded from this GitHub candidate.

## Approval gates

**Public source publication and fictional image redistribution terms were approved by the owner on 16 November 2026.** Foundry-authored software/docs use the root MIT license; the six fictional WebP images have separate CC BY 4.0 terms (to the extent licensable rights are held). A public *source repository* is not the same as exposing a functioning public service. Core runtime and a targeted privacy scan have passed; broader checks below remain documented limitations for this portfolio-source release and gates before real-world internet exposure.

For public source publishing (approved) and any future live public deployment (not approved):

1. **Independent source privacy scan: PASS on v0.2 package** for known original client identifiers, private endpoints and included client media; results are recorded in the publication audit. Anonymous RSVP is retained for this source demo and must be reassessed before an internet-facing production deployment.
2. **Core isolated Docker/PostgreSQL acceptance: PASS (2026-11-16).** Full HEIF/media edge cases, formal mobile/browser coverage, backup/restore and production security acceptance remain deliberately untested for the portfolio-source release; see verification record.
3. Security assessment of operator boundary, HTTP request headers, CSRF, media access, rate limiting, abuse controls, and available ports.
4. Accessibility, privacy information for guests, data retention and backup/restore arrangements.
5. Verification of third-party package redistribution requirements; dependency and image vulnerability checks.
6. **Public GitHub publication: owner-approved 2026-11-16** for the license-documented release candidate. This is *not* authorization to expose a real deployed event, modify the original host or enable external ingress.

## Non-goals

- Pop-up webshop; payments or stock management
- Invitation-only access/authentication (not currently implemented)
- Production deployment or update to an existing private host
- Automatic Funnel opening/closing or self-hosted service remote control
- Client records or real photos; third-party graphics/media
