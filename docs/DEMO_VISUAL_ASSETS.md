# Fictional demonstration visuals — source and rights record

**Integration date:** 2026-11-16 NZDT  
**Art direction:** SymbioFoundry, approved by the project owner for integration  
**Source:** `ECC_DEMO_VISUAL_ASSETS_FINAL_CUT_v02_20261116.zip` / `ASSET_MANIFEST.md`

All six WebP images were generated for this project as **fictional AI venue imagery** using the owner's selected second concept. They depict no real named event, client, or venue and are not photographs of actual facilities. The visual production team exported them by cropping a single generated panel composite (1672 × 941 overall), upscaling with LANCZOS and mild sharpening. The 1920×1080 and 1600×1200 exports are not native capture resolution.

| File | Location | Pixels | SHA-256 | Accessible description |
|---|---|---:|---|---|
| `ecc-demo-hero.webp` | `app/static/demo/` | 1920 × 1080 | `d94065bf16eafff6a2d50fc0e726b1c2b953be795364e99ee3a0191b7879cc06` | Contemporary timber-and-stone event pavilion with landscaped coastal grounds at sunset |
| `ecc-demo-gallery-venue.webp` | `app/static/demo/` | 1600 × 1200 | `5bfa6bf229718877d7cfb8e89af8362bc65a43e995f0f2cfc3eff3a03fc6e9fc` | Timber pergola walkway and landscaped entrance |
| `ecc-demo-gallery-tables.webp` | `app/static/demo/` | 1600 × 1200 | `76bd7b678bc8def5662798cc81cefc602d5b878b6fa4e565695dce865f8ff1dd` | Prepared timber dining tables and floral decorations |
| `ecc-demo-gallery-presentation.webp` | `app/static/demo/` | 1600 × 1200 | `3fb5ab139ffd5e931ac4e212a7bb4d747db1579776fff9e7742cf243bc54dc91` | Small event presentation space with chairs and screen |
| `ecc-demo-gallery-details.webp` | `app/static/demo/` | 1600 × 1200 | `25cba3d4619e001a7fdb41e9eca19d92f696edc36520cfff86f2237e753fa4df` | Flowers and a candle by a coastal venue window |
| `ecc-github-preview.webp` | `docs/media/` | 1200 × 630 | `d1841372db94bec433d22782b7f2939527e61cab77a5c3b6f92330fa212b5cd3` | Panoramic modern garden and coastal venue |

## Integration behavior

The hero image is decorative CSS and is shaded under a dark left-side contrast overlay. With zero operator-published photos, the four fictional gallery images are rendered as labeled examples; as soon as actual published gallery records exist, those replace the HTML fallback. Static demo files are publicly fetchable because they contain no private content. The gallery demo files are **not** inserted into PostgreSQL or the operator's Photo Library.

## Licensing and distribution boundary

The root MIT `LICENSE` covers SymbioFoundry-owned **software and documentation only**; it does not automatically license the fictional WebP imagery. The asset manifest records that these images were generated for this project, rather than sourcing client photos or third-party stock images. **The project owner approved public redistribution of the six listed WebP assets on 16 November 2026 under [CC BY 4.0](../DEMO_IMAGE_LICENSE.md), to the extent SymbioFoundry holds applicable licensable rights.** The images are AI-generated, and the extent of copyright protection and provider-related rights can vary; the license grants no rights beyond those held by the licensor. No claim is made to exclusive venue photography or to the original composite as an independently verified master photograph.

The original generated composite `source/a_clean_professional_high_resolution_event_venue.png` remains in the separate visual source packet for provenance and is **not bundled** in this public-repository candidate.
