import { useLocalSearchParams } from 'expo-router';
import { Share, View } from 'react-native';

import { formatDateTime } from '@/lib/format';
import { useLoad } from '@/lib/hooks';
import { colors, space } from '@/lib/theme';
import { Button, Card, Muted, Row, Screen, T } from '@/ui';

interface Receipt {
  receipt_number: string; paid_at: string; owner: string; service: string; title: string; reference: string;
  payment_method: string; payment_reference: string; amount: number; amount_label: string;
}

export default function ReceiptScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const loaded = useLoad<Receipt>(`orders/${id}/receipt`);
  const r = loaded.data;

  const line = (label: string, value: string) => (
    <Row style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
      <Muted size={13}>{label}</Muted>
      <View style={{ flex: 1, alignItems: 'flex-end' }}><T size={14} weight="600" style={{ textAlign: 'right' }}>{value}</T></View>
    </Row>
  );

  const share = () => r && Share.share({
    message: `Reçu Lantante Technologie n° ${r.receipt_number}\n${r.service} — ${r.title}\nMontant : ${r.amount_label}\nPayé le ${formatDateTime(r.paid_at)} (${r.payment_method})`,
  });

  return (
    <Screen loaded={loaded}>
      {r ? (
        <>
          <Card style={{ gap: space.md, borderTopWidth: 4, borderTopColor: colors.gold }}>
            <T size={18} weight="800">Reçu de paiement</T>
            <Muted>N° {r.receipt_number}</Muted>
            {line('Client', r.owner)}
            {line('Service', r.service)}
            {r.title ? line('Actualité', r.title) : null}
            {line('Référence', r.reference)}
            {line('Moyen de paiement', r.payment_method)}
            {line('Transaction', r.payment_reference)}
            {line('Date', formatDateTime(r.paid_at))}
            <View style={{ height: 1, backgroundColor: colors.border }} />
            <Row style={{ justifyContent: 'space-between' }}>
              <T weight="700">Total payé</T><T size={20} weight="800" color={colors.green}>{r.amount_label}</T>
            </Row>
          </Card>
          <Button label="Partager le reçu" icon="share-outline" variant="outline" onPress={share} />
        </>
      ) : null}
    </Screen>
  );
}
