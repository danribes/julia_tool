# julia_tool — SAT Buzon Tributario watcher
#
# This image runs the HEADLESS path: mailbox polling, anti-phishing verification,
# RFC lookup, classification, alerting, and the e.firma (client-certificate) portal
# fetch. The CIEC flow needs a VISIBLE browser so an operator can solve the captcha
# and therefore cannot run in this headless container — run CIEC clients on a host
# with a display.
#
# Secrets and runtime state are NEVER baked into the image. Provide them at run time
# via volumes: config.yaml, clients.secret, .token_cache.bin, state.sqlite, downloads/.
# The master password is passed through the JULIA_MASTER_PW environment variable.
#
#   docker build -t julia_tool .
#   docker run --rm -e JULIA_MASTER_PW=... \
#     -v "$PWD/config.yaml:/app/config.yaml:ro" \
#     -v "$PWD/clients.secret:/app/clients.secret" \
#     -v "$PWD/.token_cache.bin:/app/.token_cache.bin" \
#     -v "$PWD/downloads:/app/downloads" \
#     julia_tool --once

FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

WORKDIR /app

# Install the package (dependencies resolved from pyproject) plus the Chromium
# browser and its system libraries, in a single layer.
COPY pyproject.toml ./
COPY julia_tool ./julia_tool
RUN pip install --no-cache-dir . \
    && playwright install --with-deps chromium

# Drop privileges: run as a non-root user that owns the workdir and browser cache.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /app/downloads \
    && chown -R appuser:appuser /app /ms-playwright
USER appuser

# Default command is a safe dry-run. Override for real runs (see header).
ENTRYPOINT ["python", "-m", "julia_tool.main"]
CMD ["--once", "--dry-run"]
