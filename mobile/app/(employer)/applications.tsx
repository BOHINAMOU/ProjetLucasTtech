import { router } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { usePaged } from '@/lib/paged';
import { space } from '@/lib/theme';
import type { Application } from '@/lib/types';
import { Chips, Empty } from '@/ui';
import { ApplicationCard } from '@/ui/cards';
import { PagedList } from '@/ui/PagedList';

const TABS = [
  { value: 'new', label: 'Nouvelles' },
  { value: 'progress', label: 'En cours' },
  { value: 'hired', label: 'Acceptées' },
  { value: 'refused', label: 'Refusées' },
  { value: 'all', label: 'Toutes' },
];

export default function EmployerApplications() {
  const [tab, setTab] = useState('new');
  const paged = usePaged<Application>('employer/applications', { tab });
  const labelled = TABS.map((t) => ({ ...t, label: paged.counts ? `${t.label} (${paged.counts[t.value] ?? 0})` : t.label }));
  const header = <View style={{ paddingTop: space.lg }}><Chips options={labelled} value={tab} onChange={setTab} /></View>;
  return (
    <PagedList paged={paged} header={header}
      render={(a) => <ApplicationCard employer application={a} onPress={() => router.push(`/application/${a.id}` as never)} />}
      empty={<Empty icon="people-outline" title="Aucune candidature ici" text="Les candidatures reçues sur vos offres apparaissent dans cet onglet." />} />
  );
}
