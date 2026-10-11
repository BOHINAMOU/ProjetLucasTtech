const MONTHS = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];

export function parseDate(value?: string | null): Date | null {
  if (!value) return null;
  const d = new Date(value);
  return isNaN(d.getTime()) ? null : d;
}

export function formatDate(value?: string | null): string {
  const d = parseDate(value);
  return d ? `${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}` : '';
}

const pad = (n: number) => String(n).padStart(2, '0');

export function formatTime(value?: string | null): string {
  const d = parseDate(value);
  return d ? `${pad(d.getHours())}h${pad(d.getMinutes())}` : '';
}

export function formatDateTime(value?: string | null): string {
  const d = parseDate(value);
  return d ? `${formatDate(value)} à ${formatTime(value)}` : '';
}

/** « il y a 5 min », « hier », sinon la date. */
export function timeAgo(value?: string | null): string {
  const d = parseDate(value);
  if (!d) return '';
  const minutes = Math.floor((Date.now() - d.getTime()) / 60000);
  if (minutes < 1) return "à l'instant";
  if (minutes < 60) return `il y a ${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `il y a ${hours} h`;
  const days = Math.floor(hours / 24);
  if (days === 1) return 'hier';
  if (days < 7) return `il y a ${days} j`;
  return formatDate(value);
}

export function initials(name: string): string {
  const parts = (name || '?').trim().split(/\s+/).slice(0, 2);
  return parts.map((p) => p.charAt(0).toUpperCase()).join('') || '?';
}

/** Date au format AAAA-MM-JJ attendu par l'API. */
export function toApiDate(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** Date et heure locales « AAAA-MM-JJ HH:MM » acceptées par l'API. */
export function toApiDateTime(d: Date): string {
  return `${toApiDate(d)}T${pad(d.getHours())}:${pad(d.getMinutes())}:00`;
}

export function whatsappLink(number: string): string {
  return `https://wa.me/${number.replace(/\D/g, '')}`;
}
