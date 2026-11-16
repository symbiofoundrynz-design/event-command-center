# Event Command Center

![Fictional AI-generated event venue used in the demo](docs/media/ecc-github-preview.webp)

**A self-hosted, single-operator event management platform.**

Event Command Center combines a guest-facing information site with a separate private operations dashboard. Its backend is Python/Flask, its records live in PostgreSQL, and its web interface is built with HTML, CSS and vanilla JavaScript.

This is a **standalone, generic source edition** of a real deployed event-management application, prepared for portfolio review. It contains **no original client identities, guest records, private photos, private host addresses, or production configuration**. The source has been refactored into a reusable demonstration. **Core Docker/PostgreSQL runtime acceptance passed on an isolated Linux host on 16 November 2026**, with guest/operator isolation, fictional RSVP, persistence, publication/restore and photo workflows tested. It is a portfolio demonstration, not a production-security certification; see [verification](docs/VERIFICATION.md).

## What it does

- Guest information pages, RSVP collection and a moderated photo gallery
- Bundled fictional event imagery: a guest hero and four example gallery scenes (shown until an operator publishes their own gallery photos)
- Single-operator dashboard with live/draft content publishing, version history and restore
- Guest-party tracker, attendees, duplicate review, CSV import and invitation preparation
- Photo upload, private/public selection, display optimization, captions and ordering
- Run sheet, checklist, budget tracking, vendor records and activity log
- Optional integration hooks for fixed operator-controlled external-access commands

**One operator, many guests.** "Single-operator" means one trusted host administers the installation, not that only one person can view the event site. The application does **not** offer multi-user accounts or a customer invitation-authentication system.

## Design and boundaries

```text
                         LOCAL HOST
  +----------------------------------------------------------+
  |  127.0.0.1:8080  ->  Nginx guest-only allowlist          |
  |                         |                                |
  |                      Flask API <---> PostgreSQL           |
  |                         |              (private volume)  |
  |  127.0.0.1:8081  ->  Nginx operator proxy                 |
  |    private only        (internal key)     Photo volume    |
  +----------------------------------------------------------+
            |
            +-- Optional Tailscale Funnel to guest :8080
                (explicit external operator action only)

        NEVER expose :8081, the backend :8082 or PostgreSQL.
```

The public guest reverse proxy routes **only** the guest pages, RSVP endpoints and visible gallery media. Other paths return 404. The dashboard proxy injects a separate internal operator key, which the app also checks for administrative paths. Both published host ports bind to **127.0.0.1**, and the backend/database have **no host-published ports**.

**This is isolation, not full user authentication.** Any process with access to the host's loopback dashboard can administer the instance. Keep the operator dashboard on a trusted single-user machine. Do not bind the dashboard to a public interface or a shared tailnet. Admin actions also have a browser-origin guard, but a full security audit is outstanding.

## Local start (Docker Compose)

Requirements: Docker Engine with Compose v2, a local host where ports 8080 and 8081 are free, and Python 3.10+ to generate local secrets. The images and application packages download on first build; unlike the original production delivery, this repository does **not** bundle offline wheels.

```bash
# In a new, non-production checkout:
python3 scripts/init_env.py
# Generates random DB_PASSWORD, APP_SECRET_KEY and OPERATOR_PROXY_KEY in .env
# Never commit, print or share .env.

docker compose up --build -d
```

Open **http://127.0.0.1:8080/** for the guest experience and **http://127.0.0.1:8081/dashboard** for the operator. You can inspect the local service health through `http://127.0.0.1:8081/health`.

The installer **does not** touch an existing application, a system PostgreSQL installation, Nginx service files, systemd units or any private infrastructure. Compose uses named volumes `postgres_data` and `photo_data` scoped to this project. **Do not use `docker compose down -v` unless you intend to delete this instance's data volumes.**

To stop this installation without erasing its database and uploads:

```bash
docker compose down
```

The default event content is fictional. Editing content, tracking RSVPs and publishing occur in your local database. The CSV export and Gmail composer are manual operator workflows; this app does not send email itself.

## Optional public availability: Tailscale Funnel

The application is local-only by default. The host operator can deliberately make **only the guest-side port** reachable from the public internet using Tailscale Funnel. Follow the current [Tailscale Funnel documentation](https://tailscale.com/docs/features/tailscale-funnel) and [CLI reference](https://tailscale.com/docs/reference/tailscale-cli/funnel). For supported client versions the operator-side commands are:

```bash
# These commands are examples only. Do not run unless public exposure is approved.
tailscale funnel --bg 8080
# Confirm exposure before sharing a URL:
tailscale funnel status
# Close the Funnel for the default HTTPS listener:
tailscale funnel --https=443 off
# Verify the resulting state:
tailscale funnel status
```

Funnel can resume after reboot when started with `--bg`: **always check the status**, and do not assume stopping Docker closes a previously configured Funnel. Funnel makes the guest-side service public; it **does not authenticate guests or implement invite-only restrictions**. All published guest information (including the dashboard field for additional guest information) is visible to anyone who can reach the guest service. The dashboard's Client Access buttons are deliberately inactive until independently reviewed fixed commands are configured. Host-side Funnel toggles are **not automatically connected** to this container.

**Publication-readiness boundary:** the RSVP endpoint currently accepts public submissions and collects personal and dietary information. Do not expose a real event through Funnel until rate limiting, abuse protection, data handling/retention, backup/restore, and privacy/security tests have been completed and accepted. Invite-only access is a separate future feature, not part of this repository.

## Structure

```text
app/app.py                    Flask routes, schema and event workflows
app/templates/                Operator dashboard and generic guest site
app/static/                   Application styles, client-side logic and fictional demo imagery
deploy/nginx/                 Separate guest/operator reverse-proxy surfaces
compose.yaml                  Local-only container orchestration
Dockerfile                    Unprivileged application process
scripts/init_env.py           First-run local secret generation
requirements.txt              Python package requirements
docs/                         Boundaries, provenance and verification state
tests/                        Local/static checks
```

## Important limitations

- This source passed an isolated Docker/PostgreSQL runtime acceptance exercise on an isolated Linux host (16 November 2026). It is **not a production security certification**, and a fresh third-party installation has not been independently tested.
- The default deployment is intended for an individual trusted operator on one host. It has **no identity-based administrator login**; securing the host and operator loopback remains essential.
- No data import/migration from the original private instance is bundled or implied.
- No payment, inventory or web-shop functions are included.
- The original branded experience, original client imagery, event sounds, supplied offline wheels, and live-server replacement script are intentionally **excluded**. Only separately created fictional AI demonstration visuals are bundled.
- Third-party runtime packages are installed independently and retain their own licenses. See [Third-party notes](docs/THIRD_PARTY_NOTICES.md).
- The six fictional AI-generated WebP demo visuals are **not covered by the MIT source-code license**. They are offered under [CC BY 4.0 to the extent SymbioFoundry holds licensable rights](DEMO_IMAGE_LICENSE.md); see their [source and rights record](docs/DEMO_VISUAL_ASSETS.md).
- This code must not be pointed at an existing deployed event's database or photo store.

## Licensing and attribution

SymbioFoundry-owned original source and documentation are provided under the [MIT License](LICENSE). The six bundled fictional AI-generated WebP visuals are separately offered under [CC BY 4.0](DEMO_IMAGE_LICENSE.md), to the extent SymbioFoundry holds licensable rights. Neither license grants rights in third-party packages, names, trademarks, personal information or original private-event material. Copyright (c) 2026 SymbioFoundry.

Developed through human-directed engineering and AI-assisted implementation. Presented as a portfolio example of self-hosted application architecture and operational control.

**Status:** Owner-approved public source release candidate (16 November 2026). Core runtime acceptance PASSED on a temporary, localhost-only Linux test stack. The owner approved public GitHub publication and the separate fictional-image licensing terms. At package preparation time, no GitHub publication or original private-event deployment changes had been made. Not certified for production deployment.
