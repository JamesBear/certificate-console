"""Notification dispatch.

Deliberately inert: the product has no email provider yet, so the stub records that delivery
*succeeded* rather than pretending to send. A learner with no address cannot be delivered to and is
recorded as skipped. Dispatch always happens after the issuance transaction commits (plan D8), never
inside it.
"""

from __future__ import annotations


class StubNotifier:
    def deliver(self, *, email: str | None) -> str:
        return "sent" if email else "skipped"


notifier = StubNotifier()
