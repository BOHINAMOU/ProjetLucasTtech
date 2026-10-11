import { router } from 'expo-router';

import { useLoad } from '@/lib/hooks';
import type { Application } from '@/lib/types';
import { Banner, Button, Empty, List } from '@/ui';
import { ApplicationCard } from '@/ui/cards';

export default function CandidateApplications() {
  const loaded = useLoad<Application[]>('candidate/applications');
  const items = loaded.data ?? [];
  const pending = items.filter((a) => a.consent === 'pending').length;
  const header = (
    <>
      {pending ? <Banner tone="gold" icon="hand-right">
        {pending === 1 ? "Lantante vous propose une opportunité : ouvrez-la pour accepter ou refuser le partage de votre dossier." : `Lantante vous propose ${pending} opportunités : ouvrez-les pour répondre.`}
      </Banner> : null}
      <Button label="Candidatures spontanées" icon="rocket-outline" variant="outline" onPress={() => router.push('/requests' as never)} />
    </>
  );
  return (
    <List loaded={loaded} data={items} header={header}
      render={(a) => <ApplicationCard application={a} onPress={() => router.push(`/my-application/${a.id}` as never)} />}
      empty={<Empty icon="paper-plane-outline" title="Aucune candidature" text="Postulez à une offre depuis l'onglet Offres : elle est envoyée directement à l'entreprise."
        action={<Button label="Voir les offres" onPress={() => router.push('/(candidate)' as never)} />} />} />
  );
}
