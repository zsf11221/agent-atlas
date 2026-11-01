# Forest redesign: release gate

Status: BLOCKED — do not merge this branch to main yet.

## Design acceptance
- Use a real, locally hosted, high-resolution illustrated forest/waterfall/castle scene, not the geometric `assets/forest-landscape.svg` placeholder.
- Sidebar and hero need separate mobile crops. Real project metadata must remain from `data/projects.json`.
- No invented likes, followers, verification badges, mint eligibility or free-mint claims.
- No blockchain contract deployment is required for the website.

## Publication checks
1. Verify artwork license and commit the background asset under `assets/`.
2. Desktop 1440px, tablet 768px, mobile 390px visual review.
3. Ensure no overflow, text-on-image contrast, and keyboard/focus accessibility.
4. Validate bilingual text, search, featured projects, favorites, free/paid lists, detail drawer.
5. Verify `data/projects.json` and `data/opportunities.json` loading, hourly pipeline status, and 60s refresh.
6. Verify GitHub Pages/Cloudflare Pages preview before merging.
7. Merge to main only after tests pass; Cloudflare Pages then publishes agentatlas.vip.

## What is already verified
The existing production HTML references `assets/forest-landscape.svg`, the simplified geometric illustration the user rejected. That asset does not meet visual acceptance.
