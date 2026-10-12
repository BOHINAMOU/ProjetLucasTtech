import { router } from 'expo-router';

import { useAuth } from '@/lib/auth';
import { useLoad } from '@/lib/hooks';
import type { Dashboard, Order } from '@/lib/types';
import { Hero } from '@/screens/Hero';
import PartnersStrip from '@/screens/PartnersStrip';
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
      <PartnersStrip />
      <Hero name={user?.name || ''} avatar={user?.avatar} subtitle="Publiez une actualité ou une annonce en quelques minutes." />
      <Button label="Publier maintenant" icon="add-circle" variant="green" onPress={() => router.push('/(member)/publish' as never)} />
      {waiting ? <Banner tone="gold" icon="card">{waiting === 1 ? 'Une publication attend votre paiement.' : `${waiting} publications attendent votre paiement.`}</Banner> : null}
      <TileGrid>
        <Tile icon="document-text" value={list.length} label="Publications" onPress={() => router.push('/orders' as never)} />
        <Tile icon="checkmark-circle" tone="green" value={list.filter((o) => o.status === 'published').length} label="En ligne" onPress={() => router.push('/orders' as never)} />
        <Tile icon="chatbubbles" tone="gold" value={dash.data?.unread_messages ?? 0} label="Messages non lus" onPress={() => router.push('/(member)/messages' as never)} />
        <Tile icon="notifications" tone="warn" value={dash.data?.unread_notifications ?? 0} label="Notifications" onPress={() => router.push('/notifications' as never)} />
      </TileGrid>
      <Section title="Dernières publications">
        {list.length ? list.slice(0, 5).map((o) => <OrderCard key={o.id} order={o} />) : (
          <Empty icon="megaphone-outline" title="Pas encore de publication" text="Choisissez un service, payez les frais, c'est publié après validation." />
        )}
      </Section>
    </Screen>
  );
}
