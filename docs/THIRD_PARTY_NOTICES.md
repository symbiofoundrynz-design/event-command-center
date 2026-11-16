# Third-party components and redistribution

This repository includes **project-owned source and a separate, AI-generated fictional demo-image set**, but does not bundle Python wheels, container image layers or third-party audiovisual works.

Runtime dependencies (resolved separately during installation):

- Flask, Jinja2, Werkzeug and Flask transitive packages
- Psycopg 3, PostgreSQL and PostgreSQL-alpine container image
- Gunicorn
- Pillow and optional HEIF support through pillow-heif
- Nginx-alpine container image
- Python container base image
- Tailscale, if the host operator elects to use external availability (not included in this project)

Each upstream component retains its own license and distribution requirements. This list is **not** a complete transitive dependency license audit; pin/review package and container image versions before a production release. Consult upstream LICENSE/NOTICE materials for exact revisions.

The original event-themed photos, audio, ornamental SVGs and any portraits were deliberately omitted because their separate rights were not verified for redistribution. The replacement fictional visuals were generated for this candidate and are documented in [Demo visual assets](DEMO_VISUAL_ASSETS.md). Their public redistribution terms were owner-approved on 16 November 2026; the six bundled WebP assets are separately offered under [CC BY 4.0](../DEMO_IMAGE_LICENSE.md), limited to licensable rights held by SymbioFoundry. This does not license original client media or third-party assets.

The root MIT LICENSE applies only to material owned and authorized by SymbioFoundry.
