"""Read-only check of a deployed API. Run from your own machine:

    python -m scripts.check_deploy https://your-api.onrender.com https://your-app.vercel.app

It makes plain HTTP requests only: no login, no LLM provider, nothing is written.
Exit code 0 when every check passes. The first call can take about a minute
while a sleeping free-tier instance wakes up."""

import sys

import httpx

TIMEOUT = 90.0


class Report:
    def __init__(self) -> None:
        self.failures = 0

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        print(f"{'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))
        if not ok:
            self.failures += 1


def run_checks(api: str, web: str, report: Report) -> None:
    check = report.check
    with httpx.Client(timeout=TIMEOUT, follow_redirects=False) as client:
        r = client.get(f"{api}/health")
        check("/health answers 200", r.status_code == 200, f"HTTP {r.status_code}")

        r = client.get(f"{api}/ready")
        check("/ready answers 200 (database reachable)", r.status_code == 200, f"HTTP {r.status_code}")

        for path in ("/docs", "/redoc", "/openapi.json"):
            r = client.get(f"{api}{path}")
            check(f"{path} is closed (404)", r.status_code == 404, f"HTTP {r.status_code}; ENVIRONMENT must be production")

        def preflight(origin: str) -> httpx.Response:
            return client.options(
                f"{api}/keys",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "authorization",
                },
            )

        r = preflight(web)
        allowed = r.headers.get("access-control-allow-origin")
        check("CORS allows your web origin", allowed == web, f"allow-origin={allowed!r}")
        check("CORS allows credentials", r.headers.get("access-control-allow-credentials", "").lower() == "true")

        r = preflight("http://evil.example")
        allowed = r.headers.get("access-control-allow-origin")
        check("CORS refuses an unknown origin", allowed is None, f"allow-origin={allowed!r}")

        r = client.get(f"{api}/keys")
        check("an API call without a login is refused (401)", r.status_code == 401, f"HTTP {r.status_code}")


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    api, web = argv[1].rstrip("/"), argv[2].rstrip("/")
    report = Report()
    try:
        run_checks(api, web, report)
    except httpx.HTTPError as exc:
        print(f"FAIL  could not reach {api}: {exc.__class__.__name__}")
        return 1
    print()
    print("All checks passed." if report.failures == 0 else f"{report.failures} check(s) failed.")
    return 0 if report.failures == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
