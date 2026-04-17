# verify-production-image

A reusable composite GitHub Action that inspects a freshly-built container
image and fails the workflow if it looks like a development-stage build. This
is the **belt-and-suspenders guard** for bd-6699.

## Why this exists (incident a1sb)

In April 2026 we discovered that the production app had been running a
**development-stage container image for several weeks**. Every database query
had been crashing that entire time.

Root cause: `.github/workflows/blue-green-deploy.yml` used
`docker/build-push-action` **without** a `target:` input. Docker Buildx then
defaulted to the *last* stage in our multi-stage `Dockerfile`, which is
`development` — an image that:

- Runs as `root` (no `USER appuser` directive)
- Skips the `libodbc2` / `msodbcsql18` installation
- Carries a `version="2.5.0-dev"` label
- Uses `uvicorn --reload` directly instead of our production `entrypoint.sh`

This dev image got pushed to GHCR as `:latest` / `:main` / `:<sha>`, Azure App
Service happily pulled it, and prod was silently broken for weeks. See
commits `6a7306a` and `1c1bd54` for the `target: production` fix.

**This action is the second line of defence.** If someone ever removes,
misspells, or refactors away the `target:` line again, this guard will fail
the pipeline before the image can reach production.

## What it checks

Given an image reference, the action:

1. `docker pull`s the image from the registry.
2. `docker inspect`s it and asserts via `jq`:
   - `.Config.Labels.version` is present and does **not** end in `-dev`.
   - `.Config.User == "appuser"` (not root, not empty).
   - `.Config.Entrypoint` contains `entrypoint.sh`.
3. `docker run --rm --entrypoint sh <image> -c '...'` and asserts the
   container has:
   - `libodbc.so.2` registered with `ldconfig` (from the `libodbc2` package).
   - `/opt/microsoft/msodbcsql18/lib64/libmsodbcsql-18.*.so.*` on disk
     (the Microsoft ODBC Driver 18 itself).

Any failure is a hard stop. Every error message references this README so a
future responder knows exactly what's going on.

## Inputs

| Name        | Required | Description                                                       |
| ----------- | -------- | ----------------------------------------------------------------- |
| `image-ref` | yes      | Fully qualified image ref, e.g. `ghcr.io/org/app:sha-abc123` or `ghcr.io/org/app@sha256:...` |

## How to use it

Call the action in the **same job** that just pushed the image (the job must
have already run `actions/checkout@v4` and `docker/login-action@v3`). Place
it **immediately after** the `docker/build-push-action` (or
`docker buildx build --push`) step so a bad image is caught before any
deploy step can consume it.

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build and push
        id: build
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          target: production      # <-- keep this!
          tags: ghcr.io/htt-brands/azure-governance-platform:sha-${{ github.sha }}

      - name: Verify production image (a1sb guard)
        uses: ./.github/actions/verify-production-image
        with:
          image-ref: ghcr.io/htt-brands/azure-governance-platform@${{ steps.build.outputs.digest }}
```

Prefer `@sha256:<digest>` over a mutable tag — it's immutable and removes any
race between push and verify.

## Scope: where to wire it in

Wire the guard into **every workflow job that pushes an image to GHCR under a
tag that could land in production**. As of this writing that means:

- `blue-green-deploy.yml` — pushes `:latest`, `:main`, `:<sha>`
- `deploy-staging.yml` — pushes `:staging`, `:sha-<sha>` (staging slot feeds
  into the blue-green swap, so staging images can become prod images)
- `deploy-production.yml` — pushes `:latest`, `:sha-<sha>`

Do **not** add the guard to dev-only or preview workflows whose images can
never reach production. The guard will (correctly) fail on those.

## What to do when it fires

**Don't disable it.** It is doing its job. Instead:

1. Look at the failed step's log. The specific assertion that failed tells
   you what's wrong with the image:
   - `version label ends with -dev` → the build targeted the wrong stage.
     Check `target:` in the build step. Should be `target: production`.
   - `user expected 'appuser'` → same story, wrong stage.
   - `entrypoint does not reference entrypoint.sh` → same story.
   - `ODBC regression check FAILED` → either wrong stage, or the production
     stage in the Dockerfile has regressed its ODBC install. Check the
     `apt-get install ... libodbc2 ... msodbcsql18` block in `Dockerfile`.
2. Fix the `Dockerfile` or the workflow, not the guard.
3. Re-run the workflow.

## Local smoke test

You can run the same checks locally against an image that's already in GHCR:

```bash
docker pull ghcr.io/htt-brands/azure-governance-platform:sha-<tag>
docker inspect ghcr.io/htt-brands/azure-governance-platform:sha-<tag> | jq '.[0].Config | {Labels, User, Entrypoint}'
docker run --rm --entrypoint sh ghcr.io/htt-brands/azure-governance-platform:sha-<tag> \
  -c 'ldconfig -p | grep libodbc.so.2 && ls /opt/microsoft/msodbcsql18/lib64/libmsodbcsql-18.*.so.*'
```

A known-good reference image: `:6a7306a` (the commit where `target:
production` was restored). A known-bad reference image (if still in GHCR):
any build from before commit `6a7306a` on `main`.
