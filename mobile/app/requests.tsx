import { router } from 'expo-router';
import { View } from 'react-native';

import { api } from '@/lib/api';
import { formatDate } from '@/lib/format';
import { messageOf, useLoad } from '@/lib/hooks';
import type { SpontaneousRequest } from '@/lib/types';
import { Badge, Banner, Button, Card, Empty, InfoLine, List, Muted, Row, T, confirm, notice } from '@/ui';

export default function Requests() {
  const loaded = useLoad<SpontaneousRequest[]>('candidate/requests');

  const withdraw = (r: SpontaneousRequest) => confirm('Retirer cette demande ?', 'Lantante ne la proposera plus aux entreprises.', 'Retirer', async () => {
    try {
      await api('DELETE', `candidate/requests/${r.id}`);
      await loaded.reload();
    } catch (e) {
      notice('Action impossible', messageOf(e));
    }
  }, true);

  const header = (
    <>
      <Banner icon="information-circle">Vous ne trouvez pas d'offre ? Faites-vous connaître : Lantante garde votre demande et vous propose des opportunités. Votre dossier n'est transmis qu'avec votre accord.</Banner>
      <Button label="Nouvelle candidature spontanée" icon="add" onPress={() => router.push('/request-edit' as never)} />
    </>
  );

  return (
    <List loaded={loaded} data={loaded.data ?? []} header={header}
      render={(r) => (
        <Card>
          <Row style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <View style={{ flex: 1 }}><T weight="700">{r.request_type_label} · {r.domain_label}</T></View>
            <Badge label={r.withdrawn ? 'Retirée' : r.status_label} tone={r.withdrawn ? 'grey' : r.is_open ? 'gold' : 'grey'} />
          </Row>
          <InfoLine icon="location-outline" text={r.city} />
          <InfoLine icon="time-outline" text={r.duration} />
          <InfoLine icon="calendar-outline" text={r.available_from ? `Disponible dès le ${formatDate(r.available_from)}` : ''} />
          <Muted size={12}>Envoyée le {formatDate(r.created_at)}</Muted>
          {r.status_message ? <Banner tone="navy" icon="chatbubble-ellipses">{r.status_message}</Banner> : null}
          <Row>
            {r.can_edit ? <Button label="Modifier" small variant="outline" onPress={() => router.push(`/request-edit?id=${r.id}` as never)} /> : null}
            {r.is_open ? <Button label="Retirer" small variant="ghost" onPress={() => withdraw(r)} /> : null}
          </Row>
        </Card>
      )}
      empty={<Empty icon="rocket-outline" title="Aucune candidature spontanée" />} />
  );
}
