import { router } from 'expo-router';

import { useAuth } from '@/lib/auth';
import { useLoad } from '@/lib/hooks';
import type { Dashboard, Order } from '@/lib/types';
import HighlightsBanner from '@/screens/HighlightsBanner';
import InstallApp from '@/screens/InstallApp';
import { Banner, Button, Empty, Screen, Section, Tile, TileGrid } from '@/ui';
import { OrderCard } from '@/ui/cards';

/** Accueil du particulier : publier une actualité ou une annonce, suivre ses paiements. */
export default function MemberHome() {
  const { user } = useAuth();
  const dash = useLoad<Dashboard>('dashboard');
  const orders = useLoad<Order[]>('orders');
  const list = orders.data ?? [];
  const waiting = list.filter((o) => o.can_pay).length;
  return (
    <Screen loaded={dash}>
      <InstallApp dismissible />
      <HighlightsBanner />
      <Button label="Publier maintenant" icon="add-circle" variant="green" onPress={() => router.push('/(member)/publish' as never)} />
      {waiting ? <Banner tone="gold" icon="card">{waiting === 1 ? 'Une actualité attend votre paiement.' : `${waiting} actualités attendent votre paiement.`}</Banner> : null}
      <TileGrid>
        <Tile icon="document-text" value={list.length} label="Actualités" onPress={() => router.push('/orders' as never)} />
        <Tile icon="checkmark-circle" tone="green" value={list.filter((o) => o.status === 'published').length} label="En ligne" onPress={() => router.push('/orders' as never)} />
        <Tile icon="chatbubbles" tone="gold" value={dash.data?.unread_messages ?? 0} label="Messages non lus" onPress={() => router.push('/(member)/messages' as never)} />
        <Tile icon="notifications" tone="warn" value={dash.data?.unread_notifications ?? 0} label="Notifications" onPress={() => router.push('/notifications' as never)} />
      </TileGrid>
      <Section title="Dernières actualités">
        {list.length ? list.slice(0, 5).map((o) => <OrderCard key={o.id} order={o} />) : (
          <Empty icon="megaphone-outline" title="Pas encore d'actualité" text="Choisissez un service, payez les frais, c'est publié après validation." />
        )}
      </Section>
    </Screen>
  );
}
