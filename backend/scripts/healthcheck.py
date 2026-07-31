#!/usr/bin/env python
"""Container healthcheck.

Probes readiness over the loopback interface, but sends the site's real Host
header: TrustedHostMiddleware rejects anything else with a 400, and we do not
want to widen the trusted-host list just to satisfy a health probe.

Exit 0 = ready, non-zero = not ready (Docker marks the container unhealthy).
"""

import os
import sys
import urllib.error
import urllib.request

PORT = os.environ.get("PORT", "8000")
# Fall back to the value the app itself defaults to, so the probe still works
# if DOMAIN is somehow unset.
HOST_HEADER = os.environ.get("DOMAIN", "pk-prem.com")
PATH = os.environ.get("HEALTHCHECK_PATH", "/ready")

request = urllib.request.Request(
    f"http://127.0.0.1:{PORT}{PATH}",
    headers={"Host": HOST_HEADER},
)

try:
    with urllib.request.urlopen(request, timeout=5) as response:
        sys.exit(0 if response.status == 200 else 1)
except urllib.error.HTTPError as exc:
    print(f"healthcheck: HTTP {exc.code}", file=sys.stderr)
    sys.exit(1)
except Exception as exc:  # noqa: BLE001 - any failure means "not ready"
    print(f"healthcheck: {type(exc).__name__}: {exc}", file=sys.stderr)
    sys.exit(1)
