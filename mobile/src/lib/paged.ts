import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';

import { get, query } from './api';
import { messageOf } from './hooks';
import type { Page } from './types';

export interface Paged<T> {
  items: T[];
  counts?: Record<string, number>;
  loading: boolean;
  refreshing: boolean;
  loadingMore: boolean;
  error: string | null;
  more: () => void;
  refresh: () => Promise<void>;
  reload: () => Promise<void>;
}

/** Liste paginée de l'API (« ?page=2 ») : charge la suite en fin de liste, se recharge quand les filtres changent. */
export function usePaged<T>(path: string, params: Record<string, string | number | undefined | null> = {}, opts: { auth?: boolean } = {}): Paged<T> {
  const [items, setItems] = useState<T[]>([]);
  const [counts, setCounts] = useState<Record<string, number> | undefined>();
  const [page, setPage] = useState(1);
  const [pages, setPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ticket = useRef(0);
  const key = path + query(params);

  const load = useCallback(async (target: number, mode: 'first' | 'refresh' | 'more') => {
    const mine = ++ticket.current;
    if (mode === 'first') setLoading(true);
    if (mode === 'more') setLoadingMore(true);
    try {
      const sep = key.includes('?') ? '&' : '?';
      const res = await get<Page<T>>(`${key}${target > 1 ? `${sep}page=${target}` : ''}`, opts);
      if (mine !== ticket.current) return;
      setItems((old) => (target > 1 ? [...old, ...res.results] : res.results));
      setCounts(res.counts);
      setPage(res.page);
      setPages(res.pages);
      setError(null);
    } catch (e) {
      if (mine === ticket.current) setError(messageOf(e));
    } finally {
      if (mine === ticket.current) {
        setLoading(false);
        setRefreshing(false);
        setLoadingMore(false);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, opts.auth]);

  // Nouveaux filtres : on repart de la première page.
  const first = useRef(true);
  useEffect(() => {
    if (first.current) { first.current = false; return; }
    setItems([]);
    load(1, 'first');
  }, [key, load]);

  // Retour sur l'écran : actualisation discrète.
  useFocusEffect(useCallback(() => {
    load(1, items.length ? 'refresh' : 'first');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load]));

  return {
    items, counts, loading, refreshing, loadingMore, error,
    more: () => { if (!loadingMore && !loading && page < pages) load(page + 1, 'more'); },
    refresh: async () => { setRefreshing(true); await load(1, 'refresh'); },
    reload: () => load(1, 'first'),
  };
}
