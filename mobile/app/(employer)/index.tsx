import { router } from 'expo-router';

import { useAuth } from '@/lib/auth';
import { useLoad } from '@/lib/hooks';
import type { Dashboard, EmployerProfileData } from '@/lib/types';
import { Hero } from '@/screens/Hero';
import PartnersStrip from '@/screens/PartnersStrip';
import { Banner, Button, Menu, Screen, Tile, TileGrid } from '@/ui';

export default function EmployerHome() {
  const { user } = useAuth();
  const dash = useLoad<Dashboard>('dashboard');
  const company = useLoad<EmployerProfileData>('employer/profile');
  const d = dash.data;
  const c = company.data;
  const approved = c?.exists && c.status === 'approved';

  return (
    <Screen loaded={dash}>
      <PartnersStrip />
      <Hero name={c?.exists ? c.name : user?.name || ''} avatar={c?.exists ? c.logo : user?.avatar}
        subtitle={c?.exists ? `${c.sector_label}${c.city ? ' · ' + c.city : ''}` : 'Espace entreprise'} />

      {!c?.exists ? (
        <>
          <Banner tone="gold" icon="business">Présentez votre entreprise pour être analysée par Lantante : une fois acceptée, vous pourrez publier des offres et recevoir des candidatures.</Banner>
          <Button label="Présenter mon entreprise" icon="business-outline" onPress={() => router.push('/company-edit' as never)} />
        </>
      ) : c.status === 'pending' ? (
        <Banner tone="gold" icon="hourglass">Votre entreprise est en cours d'analyse par Lantante. Vous serez prévenu dès la décision.</Banner>
      ) : c.status === 'rejected' ? (
        <>
          <Banner tone="red" icon="close-circle">Votre entreprise n'a pas été acceptée.{c.decision_message ? `\n${c.decision_message}` : ''}</Banner>
          <Button label="Corriger et renvoyer" onPress={() => router.push('/company-edit' as never)} />
        </>
      ) : (
        <>
          {c.decision_message ? <Banner tone="green" icon="checkmark-circle">{c.decision_message}</Banner> : null}
          {c.publishing_free ? <Banner tone="navy" icon="ribbon">Partenaire Lantante : vos publications sont sans frais.</Banner> : null}
        </>
      )}

      {approved ? (
        <>
          <TileGrid>
            <Tile icon="people" tone="warn" value={d?.new_applications ?? 0} label="Nouvelles candidatures" onPress={() => router.push('/(employer)/applications' as never)} />
            <Tile icon="briefcase" value={d?.offers ?? 0} label="Offres en cours" onPress={() => router.push('/offers-mine' as never)} />
            <Tile icon="chatbubbles" tone="green" value={d?.unread_messages ?? 0} label="Messages non lus" onPress={() => router.push('/(employer)/messages' as never)} />
            <Tile icon="notifications" tone="gold" value={d?.unread_notifications ?? 0} label="Notifications" onPress={() => router.push('/notifications' as never)} />
          </TileGrid>
          <Button label="Publier une offre ou une actualité" icon="add-circle" variant="green" onPress={() => router.push('/(employer)/publish' as never)} />
        </>
      ) : null}

      <Menu items={[
        { icon: 'newspaper-outline', label: 'Actualités, entreprises et partenaires', onPress: () => router.push('/discover' as never) },
        { icon: 'calendar-outline', label: 'Rendez-vous et entretiens', onPress: () => router.push('/appointments' as never) },
      ]} />
    </Screen>
  );
}
