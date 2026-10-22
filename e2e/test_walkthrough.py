"""The demo: a labelled walkthrough of every workflow, with assertions.

Each step paints a banner naming what is about to happen, performs the action, and then asserts the
observable outcome. The banner is injected by the test, so the production bundle carries no demo
chrome, and the walkthrough cannot drift from the product without failing.

    pytest e2e                     # headless, CI
    E2E_HEADED=1 pytest e2e -s     # watchable demo with screenshots and video
"""

from __future__ import annotations

import csv
import io
import os
import re
import time
from pathlib import Path

from playwright.sync_api import Page, expect, sync_playwright

ARTIFACTS = Path(__file__).resolve().parent / "artifacts"
HEADED = os.environ.get("E2E_HEADED") == "1"

steps: list[tuple[int, str, str]] = []
_step_index = 0

BANNER_JS = """
(label) => {
  let el = document.getElementById('__e2e_step');
  if (!el) {
    el = document.createElement('div');
    el.id = '__e2e_step';
    el.style.cssText = [
      'position:fixed', 'left:24px', 'bottom:24px', 'z-index:2147483647',
      'background:#111827', 'color:#ffffff', 'font:600 14px/1.4 -apple-system,Segoe UI,Arial',
      'padding:12px 18px', 'border-radius:10px', 'box-shadow:0 10px 30px rgba(0,0,0,.35)',
      'max-width:60vw', 'pointer-events:none', 'letter-spacing:.01em'
    ].join(';');
    document.body.appendChild(el);
  }
  el.textContent = '閳?' + label;
}
"""


def step(page: Page, label: str, assertion: str = "") -> None:
    """Announce a step, then let the caller assert. Screenshot is taken by `shot`."""
    global _step_index
    _step_index += 1
    page.evaluate(BANNER_JS, label)
    steps.append((_step_index, label, assertion))
    print(f"\n[e2e {_step_index:02d}] {label}", flush=True)


def shot(page: Page, label: str) -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:60]
    page.screenshot(path=str(ARTIFACTS / f"{_step_index:02d}-{safe}.png"))


def wait_until(page: Page, predicate, timeout: float = 6.0) -> None:
    """Poll a UI condition instead of sleeping for a fixed time."""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = predicate()
        if last:
            return
        page.wait_for_timeout(100)
    raise AssertionError(f"condition was never met; last value: {last!r}")


def write_steps_md() -> None:
    lines = ["# Demo walkthrough", "", "| # | Step | Assertion |", "| --- | --- | --- |"]
    for index, label, assertion in steps:
        lines.append(f"| {index} | {label} | {assertion} |")
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    (ARTIFACTS / "steps.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def sign_in(page: Page, tenant: str, account: str) -> None:
    page.get_by_test_id("tenant-select").select_option(tenant)
    page.get_by_test_id("account-select").select_option(account)
    page.get_by_test_id("sign-in").click()
    expect(page.get_by_role("heading", name="Certificates")).to_be_visible()


def test_demo_walkthrough(base_url: str) -> None:
    ARTIFACTS.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not HEADED, slow_mo=450 if HEADED else 0)
        context = browser.new_context(
            viewport={"width": 1280, "height": 860},
            record_video_dir=str(ARTIFACTS / "video") if HEADED else None,
        )
        page = context.new_page()
        calls: list[str] = []
        page.on(
            "response",
            lambda response: calls.append(response.url.split("/api/")[-1])
            if "/api/certificates?" in response.url
            else None,
        )

        # 1 閳?login gate
        step(page, "Open the console while signed out", "redirected to /login")
        page.goto(base_url + "/")
        expect(page.get_by_test_id("sign-in")).to_be_visible()
        shot(page, "login")

        step(page, "Sign in as Acme Field Services (Sydney)", "list loads for that tenant")
        sign_in(page, "t_acme", "u_t_acme")
        expect(page.get_by_test_id("summary")).to_contain_text("Australia/Sydney")

        # 2 閳?list
        step(page, "Certificates load", "twenty rows on the first page")
        expect(page.get_by_test_id("cert-row")).to_have_count(20)
        first_row = page.get_by_test_id("cert-row").first
        learner = first_row.locator(".cell-name").inner_text()
        serial = first_row.get_by_test_id("serial").inner_text()
        expect(page.get_by_test_id("pager-summary")).to_contain_text("of ")
        shot(page, "list")


        step(page, f"Search by learner name: {learner.split()[-1]}", "every row matches the term")
        term = learner.split()[-1].lower()
        page.get_by_test_id("search-input").fill(learner.split()[-1])

        def all_rows_match() -> bool:
            names = page.get_by_test_id("cert-row").locator(".cell-name").all_inner_texts()
            return bool(names) and all(term in name.lower() for name in names)

        try:
            wait_until(page, all_rows_match)
        except AssertionError:
            raise AssertionError(
                f"rows do not all contain {term!r}: "
                f"{page.get_by_test_id('cert-row').locator('.cell-name').all_inner_texts()[:6]}"
            ) from None
        shot(page, "search-name")

        step(page, f"Search by serial fragment: {serial[-5:]}", "the serial is found")
        page.get_by_test_id("search-input").fill(serial[-5:])
        expect(page.get_by_test_id("serial").first).to_contain_text(serial[-5:])
        shot(page, "search-serial")

        step(page, "Clear the search", "the full list comes back")
        page.get_by_test_id("search-input").fill("")
        expect(page.get_by_test_id("cert-row")).to_have_count(20)
        shot(page, "cleared")

        step(page, "Page forward", "a different page of rows")
        page.get_by_role("button", name="Learner").click()
        expect(page.get_by_test_id("cert-row").first).to_be_visible()
        before = page.get_by_test_id("serial").first.inner_text()
        page.get_by_role("button", name="Next").click()
        expect(page.get_by_test_id("serial").first).not_to_have_text(before)
        shot(page, "page-two")

        # 4 閳?detail + DST
        step(page, "Open a certificate", "the tenant zone label is shown")
        page.get_by_test_id("status-filter").select_option("valid")
        expect(page.get_by_test_id("cert-row").first).to_be_visible()
        page.get_by_test_id("cert-row").first.click()
        expect(page.get_by_test_id("detail-serial")).to_be_visible()
        zone_label = page.get_by_test_id("zone-label").inner_text()
        assert ("AEDT" in zone_label or "AEST" in zone_label) and "UTC+1" in zone_label, zone_label
        shot(page, "detail")

        # 5 閳?revoke
        step(page, "Revoke it with a reason", "status becomes Revoked and the audit grows")
        page.get_by_test_id("revoke-button").click()
        page.get_by_test_id("revoke-reason").fill("Duplicate enrolment 閳?issued twice by mistake.")
        page.get_by_test_id("confirm-revoke").click()
        expect(page.get_by_test_id("detail-status")).to_contain_text("Revoked")
        expect(page.get_by_test_id("audit-entry")).to_have_count(2)
        shot(page, "revoked")

        # 6 閳?bulk issue
        step(page, "Open bulk issue", "courses and eligibility are visible")
        page.get_by_role("link", name="Bulk issue").click()
        expect(page.get_by_test_id("eligibility")).to_be_visible()
        page.get_by_test_id("issue-course").select_option("c_acm_3")
        expect(page.get_by_test_id("eligibility")).to_contain_text("eligible")
        shot(page, "eligibility")

        step(page, "Issue to every eligible learner", "per-learner outcomes are listed")
        page.get_by_test_id("issue-button").click()
        expect(page.get_by_test_id("outcome-row").first).to_be_visible(timeout=15000)
        issued_text = page.get_by_test_id("issued-count").inner_text()
        issued = int(re.search(r"\d+", issued_text).group())
        assert issued > 0, issued_text
        expect(page.get_by_test_id("issue-button")).to_be_disabled()
        shot(page, "issued")

        # 7 閳?replay
        step(page, "Replay the same request", "the replay banner appears and nothing new is issued")
        page.get_by_test_id("replay-button").click()
        expect(page.get_by_test_id("replay-banner")).to_be_visible()
        expect(page.get_by_test_id("issued-count")).to_have_text(f"Issued {issued}")
        shot(page, "replay")

        # 8 閳?export
        step(page, "Export the current filter as CSV", "the file matches the list")
        page.get_by_role("link", name="Certificates", exact=True).click()
        page.get_by_test_id("status-filter").select_option("revoked")
        # Wait for the filtered rows to settle rather than for a particular HTTP response: the
        # list may refetch more than once per interaction, and a missing response is not the
        # thing we actually care about.
        expect(page.get_by_test_id("cert-row").first).to_be_visible()
        expect(page.locator("[data-testid='cert-row'] .badge-revoked").first).to_be_visible()
        expect(page.get_by_test_id("summary")).to_have_text(re.compile(r"^\d+ certificates.*"))
        total = int(re.search(r"\d+", page.get_by_test_id("summary").inner_text()).group())
        with page.expect_download() as download_info:
            page.get_by_test_id("export-button").click()
        download = download_info.value
        path = ARTIFACTS / (download.suggested_filename or "export.csv")
        download.save_as(str(path))
        rows = list(csv.reader(io.StringIO(path.read_text(encoding="utf-8-sig"))))
        assert rows[0] == ["Learner name", "Course title", "Serial number", "Issue date"]
        assert len(rows) - 1 == total, (len(rows), total)
        shot(page, "export")

        # 9 閳?isolation
        step(page, "Sign out and sign in as Northwind (Perth)", "a different tenant's data, no crossover")
        page.get_by_test_id("sign-out").click()
        sign_in(page, "t_northwind", "u_t_northwind")
        expect(page.get_by_test_id("summary")).to_contain_text("Australia/Perth")
        expect(page.get_by_test_id("serial").first).to_contain_text("CERT-NWL-", timeout=10000)
        shot(page, "other-tenant")

        write_steps_md()
        context.close()
        browser.close()

