import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

export const BASE_URL = process.env.EXPO_PUBLIC_API_URL || 'https://lantantetechnologie.com/api/v1/';
export const SITE_URL = BASE_URL.replace(/\/api\/v1\/?$/, '');
const TOKEN_KEY = 'lantante_token';

// Sur le web (aperçu), SecureStore n'existe pas : on se rabat sur localStorage.
async function readToken(): Promise<string | null> {
  try {
    if (Platform.OS === 'web') return globalThis.localStorage?.getItem(TOKEN_KEY) ?? null;
    return await SecureStore.getItemAsync(TOKEN_KEY);
  } catch {
    return null;
  }
}

export async function saveToken(token: string | null) {
  try {
    if (Platform.OS === 'web') {
      if (token) globalThis.localStorage?.setItem(TOKEN_KEY, token);
      else globalThis.localStorage?.removeItem(TOKEN_KEY);
      return;
    }
    if (token) await SecureStore.setItemAsync(TOKEN_KEY, token);
    else await SecureStore.deleteItemAsync(TOKEN_KEY);
  } catch {
    /* sans conséquence : l'utilisateur devra se reconnecter */
  }
}

export const getToken = readToken;

export class ApiError extends Error {
  status: number;
  code?: string;
  errors?: Record<string, string[]>;
  constructor(status: number, detail: string, code?: string, errors?: Record<string, string[]>) {
    super(detail);
    this.status = status;
    this.code = code;
    this.errors = errors;
  }
  /** Message de la première erreur de champ, sinon le message général. */
  get readable(): string {
    if (this.errors) {
      const first = Object.values(this.errors)[0];
      if (first && first[0]) return first[0];
    }
    return this.message;
  }
}

let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: (() => void) | null) {
  onUnauthorized = fn;
}

export interface FilePart { uri: string; name: string; type: string }
export type Body = Record<string, unknown> | FormData;

function toFormData(data: Record<string, unknown>): FormData {
  const form = new FormData();
  Object.entries(data).forEach(([key, value]) => {
    if (value === undefined || value === null) return;
    if (Array.isArray(value)) {
      value.forEach((v) => form.append(key, String(v)));
    } else if (typeof value === 'object' && 'uri' in (value as object)) {
      // Fichier choisi sur le téléphone : React Native accepte cet objet dans FormData.
      form.append(key, value as unknown as Blob);
    } else if (typeof value === 'boolean') {
      form.append(key, value ? 'true' : 'false');
    } else {
      form.append(key, String(value));
    }
  });
  return form;
}

function hasFile(data: Record<string, unknown>) {
  return Object.values(data).some((v) => v && typeof v === 'object' && !Array.isArray(v) && 'uri' in (v as object));
}

export async function api<T = any>(
  method: 'GET' | 'POST' | 'PATCH' | 'DELETE',
  path: string,
  body?: Record<string, unknown>,
  opts: { auth?: boolean } = {},
): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  const token = opts.auth === false ? null : await readToken();
  if (token) headers.Authorization = `Token ${token}`;
  let payload: BodyInit | undefined;
  if (body && method !== 'GET') {
    if (hasFile(body)) {
      payload = toFormData(body);
    } else {
      headers['Content-Type'] = 'application/json';
      payload = JSON.stringify(body);
    }
  }
  let response: Response;
  try {
    response = await fetch(BASE_URL + path.replace(/^\//, ''), { method, headers, body: payload });
  } catch {
    throw new ApiError(0, "Impossible de joindre le serveur. Vérifiez votre connexion Internet.", 'network');
  }
  if (response.status === 204) return undefined as T;
  let data: any = null;
  try {
    data = await response.json();
  } catch {
    /* réponse vide ou non JSON */
  }
  if (!response.ok) {
    if (response.status === 401 && token && onUnauthorized) onUnauthorized();
    const detail = data?.detail || (response.status === 429
      ? 'Trop d\'essais. Réessayez dans une minute.'
      : 'Une erreur est survenue. Réessayez.');
    throw new ApiError(response.status, detail, data?.code, data?.errors);
  }
  return data as T;
}

export const get = <T = any>(path: string, opts?: { auth?: boolean }) => api<T>('GET', path, undefined, opts);
export const post = <T = any>(path: string, body?: Record<string, unknown>, opts?: { auth?: boolean }) => api<T>('POST', path, body, opts);
export const patch = <T = any>(path: string, body?: Record<string, unknown>) => api<T>('PATCH', path, body);
export const del = <T = any>(path: string) => api<T>('DELETE', path);

/** Construit « ?a=1&b=2 » en ignorant les valeurs vides. */
export function query(params: Record<string, string | number | undefined | null>) {
  const parts = Object.entries(params)
    .filter(([, v]) => v !== undefined && v !== null && v !== '')
    .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`);
  return parts.length ? `?${parts.join('&')}` : '';
}

/** Télécharge un fichier privé (CV, document) avec le jeton, pour l'ouvrir ensuite. */
export async function authHeaders(): Promise<Record<string, string>> {
  const token = await readToken();
  return token ? { Authorization: `Token ${token}` } : {};
}
