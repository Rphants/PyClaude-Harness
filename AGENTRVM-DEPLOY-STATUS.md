# AgentRVM Deploy Status

Assessed on `2026-04-01`.

Source of truth for this review was the GitHub repo `Rphants/agentrvm` on `master`. `~/Downloads/agentrvm` does not exist on this machine, and shell network access is blocked here, so I could not clone or run a fresh local build myself. Build status below is inferred from the repo contents and GitHub Actions history.

## Quick Answer

### 1) Can it build?

Yes for the static site build, with one important caveat: I did not run it locally.

Evidence:
- `package.json` uses `pnpm`-compatible scripts and defines `build` as `next build`.
- `next.config.ts` sets `output: "export"`, which matches `firebase.json` hosting from `out/`.
- `.github/workflows/firebase-deploy.yml` runs `pnpm install --frozen-lockfile` and `pnpm run build`.
- Latest visible live deploy workflow run was `#35`, completed successfully on **March 21, 2026 at 10:58 PM GMT-5** for commit `fd6626e`.

Assessment:
- Static Hosting build path looks healthy.
- This is not the same as proving the repo is fully deployable end to end, because the current workflow only covers Hosting.

### 2) Is Firebase config present?

Yes.

Present in repo:
- `.firebaserc` with default project `serene-sentinel-487518-c1`
- `firebase.json`
- `firestore.rules`
- `functions/voice-demo/`
- `.github/workflows/firebase-deploy.yml`
- `.github/workflows/pr-check.yml`
- `.env.example`

What that config shows:
- Hosting serves the static export from `out/`
- Firestore rules are checked into the repo
- A Firebase function codebase exists at `functions/voice-demo`
- The repo expects the `firestore-send-email` extension

### 3) Any blockers for production?

## Blockers

### Blocking for full-stack production deploys

1. **GitHub Actions only deploys Firebase Hosting, not the backend Firebase pieces.**
   - Both `.github/workflows/firebase-deploy.yml` and `.github/workflows/pr-check.yml` use `FirebaseExtended/action-hosting-deploy@v0`.
   - They do **not** deploy:
     - `functions/voice-demo`
     - `firestore.rules`
     - the `firestore-send-email` extension declared in `firebase.json`
   - Result: pushes to `master` do not guarantee that repo backend changes are actually in production.

2. **The voice-demo backend depends on secrets that cannot be verified from the repo and are not documented in the repo env example.**
   - `functions/voice-demo/src/index.ts` requires Firebase secrets:
     - `ELEVENLABS_API_KEY`
     - `SLACK_WEBHOOK_URL`
   - The repo does not provide a checked-in deployment checklist proving those secrets are configured in the target Firebase project.

## Risks / Gaps

These are not hard blockers for a Hosting-only landing page push, but they are production-readiness gaps:

1. **Environment documentation is incomplete.**
   - `.env.example` includes Firebase web config and analytics keys, but it does **not** include `NEXT_PUBLIC_VOICE_DEMO_API`.
   - Both GitHub workflows inject `NEXT_PUBLIC_VOICE_DEMO_API`, so a fresh setup is not fully reproducible from repo docs alone.

2. **Docs are stale around deployment.**
   - `README.md` badge links point to `deploy.yml`, but the actual workflow file is `firebase-deploy.yml`.
   - `README.md` still shows `npm install` and manual Hosting-only deployment commands, while the repo is standardized on `pnpm` in CI.

3. **CI proves build, not test coverage at deploy time.**
   - The live deploy workflow runs `pnpm run build`.
   - It does not run `pnpm test` before deploying.

## Bottom Line

- **Static Firebase Hosting:** looks deployable.
- **Full repo as a production system:** **not fully ready** unless you are comfortable with manual backend deployment and manual secret management.

The main blocker is not “the site fails to build.” The main blocker is that the current deployment path does not fully ship or verify the Firebase backend that the repo also contains.
