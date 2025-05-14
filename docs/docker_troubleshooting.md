# Docker Local Image Troubleshooting Guide

This document outlines the steps to build, run, inspect, and troubleshoot Docker images locally on an ARM64 platform. Follow these instructions in order to ensure a smooth workflow.

---

## Prerequisites

- Docker Desktop (or Docker Engine) installed
- [docker buildx](https://docs.docker.com/buildx/working-with-buildx/) enabled
- Access to your private gem registry with the `sidekiq-secret`
- Bash shell (or compatible terminal)

---

## 1. Build the Image for ARM64

Use `docker buildx` to build a multi-platform image targeting Linux ARM64.

```bash
# Build the image for linux/arm64 and tag it
docker buildx build   --platform linux/arm64   --build-arg BUNDLE_GEMS__CONTRIBSYS__COM={sidekiq-secret}   -t jt-arm64:test .
```

- `--platform linux/arm64` ensures the image is built for ARM64 architecture.
- `--build-arg BUNDLE_GEMS__CONTRIBSYS__COM` passes your private gem registry secret.
- `-t jt-arm64:test` tags the resulting image.

> **Tip:** If you plan to run this image immediately on your local Docker engine, add `--load` before `--platform`:
>
> ```bash
> docker buildx build --load >   --platform linux/arm64 >   --build-arg BUNDLE_GEMS__CONTRIBSYS__COM={sidekiq-secret} >   -t jt-arm64:test .
> ```

---

## 2. Run the Container

Start an interactive Bash session in the newly built container:

```bash
docker run -it jt-arm64:test
```

- The `-it` flags allocate a pseudo-TTY and keep STDIN open, giving you a shell inside the container.

---

## 3. Verify Running Containers

List all running containers to confirm the container started successfully:

```bash
docker ps
```

- This command displays a table of active containers, including their IDs, names, and status.

---

## 4. Access a Running Container

If you need to open a shell in an already running container, use `docker exec`:

```bash
docker exec -it <container_id_or_name> bash
```

- Replace `<container_id_or_name>` with the ID or name from `docker ps` output.
- The `-it` flags work as above to give you an interactive Bash shell.

---

## 5. Clear Builder Cache

If your builds are failing or you want to free up space, prune the builder cache:

```bash
docker builder prune -a
```

- The `-a` flag removes all unused build caches.
- You will be prompted to confirm; type `y` to proceed.

---

## 6. Image Not Found? Use `--load`

If Docker cannot find the image after a `buildx build`, ensure you loaded it into the local engine:

```bash
# Include --load when building
docker buildx build --load --platform linux/arm64   --build-arg BUNDLE_GEMS__CONTRIBSYS__COM={sidekiq-secret}   -t jt-arm64:test .
```

- `--load` automatically imports the built image into your local Docker images.

---

## Summary

By following these steps, you can build, run, inspect, and troubleshoot Docker images locally, especially when targeting non-native architectures like ARM64. Clearing the builder cache and using `--load` are key techniques to resolve common build and image-not-found issues.
