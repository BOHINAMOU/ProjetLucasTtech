import { router } from 'expo-router';

import { useLoad } from '@/lib/hooks';
import type { Order } from '@/lib/types';
import { Button, Empty, List } from '@/ui';
import { OrderCard } from '@/ui/cards';

export default function Orders() {
  const loaded = useLoad<Order[]>('orders');
  return (
    <List loaded={loaded} data={loaded.data ?? []} render={(o) => <OrderCard order={o} />}
      empty={<Empty icon="receipt-outline" title="Aucune publication" text="Vos publications payées ou en attente apparaîtront ici."
        action={<Button label="Publier" onPress={() => router.back()} />} />} />
  );
}
