# Publishing to Docker Hub

This guide covers how to build and publish the unsealed-networks Docker image to Docker Hub.

## Prerequisites

- Docker installed and running
- Docker Hub account
- Database built at `data/unsealed.db`

## Build and Test Locally

```bash
# From project root
docker build -t unsealed-networks .

# Test it works
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | \
  docker run -i --rm unsealed-networks stdio

# Should return JSON response with server info
```

## Login to Docker Hub

```bash
docker login
# Enter your Docker Hub username and password
```

## Tag and Push

```bash
# Tag with your username
docker tag unsealed-networks devonjones/unsealed-networks:latest

# Optional: Also tag with version
docker tag unsealed-networks devonjones/unsealed-networks:0.0.1

# Push to Docker Hub
docker push devonjones/unsealed-networks:latest
docker push devonjones/unsealed-networks:0.0.1  # if versioned
```

## Verify

```bash
# Pull and test from Docker Hub
docker pull devonjones/unsealed-networks:latest
docker run -i --rm devonjones/unsealed-networks:latest stdio
```

## Image Details

- **Base:** python:3.11-slim
- **Size:** ~355MB (includes 80MB database)
- **Contents:**
  - Python 3.11 runtime
  - uv package manager
  - unsealed-networks package
  - Complete SQLite database (2,897 documents)
  - MCP server (stdio and SSE modes)

## Multi-Platform Builds (Optional)

To build for multiple architectures (AMD64 and ARM64):

```bash
# Create and use buildx builder
docker buildx create --name multiarch --use
docker buildx inspect --bootstrap

# Build and push multi-platform
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t devonjones/unsealed-networks:latest \
  --push \
  .
```

## Automated Builds (Future)

Consider setting up GitHub Actions to automatically build and push on:
- New tags (for releases)
- Pushes to main branch (for latest)

Example workflow location: `.github/workflows/docker-publish.yml`

## Usage by End Users

Once published, anyone can run:

```bash
# Pull and run
docker pull devonjones/unsealed-networks:latest
docker run -i --rm devonjones/unsealed-networks:latest stdio
```

No source code, no database setup, no Python installation required!

## Updating the Image

When updating the database or code:

1. Update version in `pyproject.toml`
2. Rebuild database: `uv run unsealed-networks load-db ...`
3. Rebuild image: `docker build -t unsealed-networks .`
4. Test locally
5. Tag with new version: `docker tag unsealed-networks devonjones/unsealed-networks:0.0.2`
6. Push: `docker push devonjones/unsealed-networks:0.0.2`
7. Update latest tag: `docker tag unsealed-networks devonjones/unsealed-networks:latest`
8. Push latest: `docker push devonjones/unsealed-networks:latest`

## Security Notes

- Database is read-only in the container
- No credentials or secrets in image
- All data is public record
- Runs as non-root user (TODO: add USER directive to Dockerfile)
