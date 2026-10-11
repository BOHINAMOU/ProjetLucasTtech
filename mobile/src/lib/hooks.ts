import { useFocusEffect } from 'expo-router';
import { useCallback, useRef, useState } from 'react';

import { ApiError, get } from './api';

export interface Loaded<T> {
  data: T | null;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  reload: () => Promise<void>;
  refresh: () => Promise<void>;
  setData: (value: T | null | ((old: T | null) => T | null)) => void;
}

/** Charge une adresse de l'API à chaque fois que l'écran redevient visible ; gère chargement, erreur et « tirer pour actualiser ». */
export function useLoad<T>(path: string | null, opts: { auth?: boolean } = {}): Loaded<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const latest = useRef(0);

  const run = useCallback(async (silent: boolean) => {
    if (!path) {
      setLoading(false);
      return;
    }
    const ticket = ++latest.current;
    if (!silent) setLoading(true);
    try {
      const result = await get<T>(path, opts);
      if (ticket === latest.current) {
        setData(result);
        setError(null);
      }
    } catch (e) {
      if (ticket === latest.current) setError(e instanceof ApiError ? e.readable : 'Chargement impossible.');
    } finally {
      if (ticket === latest.current) {
        setLoading(false);
        setRefreshing(false);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, opts.auth]);

  useFocusEffect(useCallback(() => {
    run(data !== null); // déjà des données : on actualise sans masquer l'écran
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run]));

  return {
    data, loading, refreshing, error, setData,
    reload: () => run(false),
    refresh: async () => {
      setRefreshing(true);
      await run(true);
    },
  };
}

/** Message lisible pour une erreur d'API ou inattendue. */
export function messageOf(e: unknown): string {
  if (e instanceof ApiError) return e.readable;
  return 'Une erreur est survenue. Réessayez.';
}

/** Erreurs par champ renvoyées par l'API (ou vide). */
export function fieldErrors(e: unknown): Record<string, string> {
  const out: Record<string, string> = {};
  if (e instanceof ApiError && e.errors) {
    for (const [key, list] of Object.entries(e.errors)) out[key] = list[0];
  }
  return out;
}
