import { useState } from 'react';
import { View } from 'react-native';

import { post } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { messageOf, useLoad } from '@/lib/hooks';
import type { Appointment } from '@/lib/types';
import { Button, Empty, List, Row, notice } from '@/ui';
import { AppointmentCard } from '@/ui/cards';

export default function Appointments() {
  const { kind } = useAuth();
  const loaded = useLoad<Appointment[]>('appointments');
  const [busy, setBusy] = useState<number | null>(null);

  const respond = async (id: number, action: 'confirm' | 'decline') => {
    setBusy(id);
    try {
      await post(`appointments/${id}/respond`, { action });
      await loaded.reload();
    } catch (e) {
      notice('Action impossible', messageOf(e));
    } finally {
      setBusy(null);
    }
  };

  return (
    <List loaded={loaded} data={loaded.data ?? []}
      render={(a) => (
        <AppointmentCard appointment={a} footer={kind === 'candidate' && a.status === 'proposed' ? (
          <Row>
            <View style={{ flex: 1 }}><Button label="Confirmer" variant="green" small onPress={() => respond(a.id, 'confirm')} loading={busy === a.id} /></View>
            <View style={{ flex: 1 }}><Button label="Décliner" variant="outline" small onPress={() => respond(a.id, 'decline')} disabled={busy === a.id} /></View>
          </Row>
        ) : null} />
      )}
      empty={<Empty icon="calendar-outline" title="Aucun rendez-vous" text="Vos entretiens apparaîtront ici dès qu'ils seront fixés." />} />
  );
}
