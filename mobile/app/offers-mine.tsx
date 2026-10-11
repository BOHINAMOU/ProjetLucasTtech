import { router } from 'expo-router';
import { View } from 'react-native';

import { post } from '@/lib/api';
import { formatDate } from '@/lib/format';
import { messageOf, useLoad } from '@/lib/hooks';
import type { Offer } from '@/lib/types';
import { Badge, Button, Card, Empty, InfoLine, List, Muted, Row, T, confirm, notice } from '@/ui';

const STATUS: Record<string, [string, 'gold' | 'green' | 'navy' | 'grey']> = {
  awaiting_payment: ['À payer', 'gold'], pending: ['En validation', 'navy'], published: ['Publiée', 'green'],
};

export default function MyOffers() {
  const loaded = useLoad<Offer[]>('employer/offers');

  const filled = (o: Offer) => confirm('Poste pourvu ?', "L'offre n'acceptera plus de candidatures.", 'Poste pourvu', async () => {
    try {
      await post(`employer/offers/${o.slug}/filled`);
      await loaded.reload();
    } catch (e) {
      notice('Action impossible', messageOf(e));
    }
  });

  return (
    <List loaded={loaded} data={loaded.data ?? []}
      render={(o) => {
        const [label, tone] = STATUS[o.status] ?? [o.status, 'grey' as const];
        return (
          <Card>
            <Row style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
              <View style={{ flex: 1 }}><T weight="700" size={16}>{o.title}</T></View>
              <Badge label={label} tone={tone} />
            </Row>
            <InfoLine icon="briefcase-outline" text={`${o.contract_label}${o.city ? ' · ' + o.city : ''}`} />
            <InfoLine icon="calendar-outline" text={o.deadline ? `Date limite : ${formatDate(o.deadline)}` : ''} />
            <Row><Muted size={13}>{o.applications ?? 0} candidature(s)</Muted>{o.featured ? <Badge label="Mise en avant" tone="gold" icon="star" /> : null}</Row>
            {o.status === 'published' ? (
              <Row>
                <Button small variant="outline" label="Poste pourvu" onPress={() => filled(o)} />
                <Button small variant="gold" icon="star" label="Mettre en avant" onPress={() => router.push('/publish/offre-mise-en-avant' as never)} />
              </Row>
            ) : null}
          </Card>
        );
      }}
      empty={<Empty icon="briefcase-outline" title="Aucune offre en cours" text="Publiez votre première offre depuis l'onglet « Publier »."
        action={<Button label="Publier une offre" onPress={() => router.push('/(employer)/publish' as never)} />} />} />
  );
}
