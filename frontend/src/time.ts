// Display formatting only — the server owns sorting and export dates.
// Every value is rendered in the tenant's IANA zone; never a stored offset.

export function formatDateTime(iso: string, timeZone: string): string {
  return new Intl.DateTimeFormat('en-AU', {
    timeZone,
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  }).format(new Date(iso));
}

export function utcDateTime(iso: string): string {
  return `${new Intl.DateTimeFormat('en-AU', {
    timeZone: 'UTC',
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  }).format(new Date(iso))} UTC`;
}

export function zoneOffsetLabel(iso: string, timeZone: string): string {
  const at = new Date(iso);
  const abbr = new Intl.DateTimeFormat('en-AU', { timeZone, timeZoneName: 'short' })
    .formatToParts(at)
    .find((part) => part.type === 'timeZoneName')?.value;
  const offset = new Intl.DateTimeFormat('en-AU', { timeZone, timeZoneName: 'shortOffset' })
    .formatToParts(at)
    .find((part) => part.type === 'timeZoneName')?.value;
  return [abbr, offset?.replace('GMT', 'UTC')].filter(Boolean).join(' · ');
}
