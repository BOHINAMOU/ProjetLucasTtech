import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Image, Linking } from 'react-native';

import { api, post, SITE_URL } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { formatDate } from '@/lib/format';
import { pickImage, type Picked } from '@/lib/files';
import { fieldErrors, messageOf, useLoad } from '@/lib/hooks';
import { whatsappLink } from '@/lib/format';
import { colors } from '@/lib/theme';
import type { Order } from '@/lib/types';
import { Badge, Banner, Button, Card, FilePicker, H2, InfoLine, Input, Muted, Screen, Select, Steps, T, confirm, notice } from '@/ui';
import { orderTone } from '@/ui/cards';

const STEPS = ['Soumise', 'Paiement', 'Validation', 'Publiée'];
const METHODS = [{ value: 'flooz', label: 'Flooz' }, { value: 'tmoney', label: 'T-Money' }];

export default function OrderScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { config } = useAuth();
  const loaded = useLoad<Order>(`orders/${id}`);
  const o = loaded.data;

  const [method, setMethod] = useState('flooz');
  const [phone, setPhone] = useState('');
  const [reference, setReference] = useState('');
  const [text, setText] = useState('');
  const [title, setTitle] = useState('');
  const [image, setImage] = useState<Picked | null>(null);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => { if (o) { setText(o.text); setTitle(o.title); } }, [o?.id, o?.text, o?.title]);

  const pay = async () => {
    setBusy(true);
    setErrors({});
    try {
      await post(`orders/${id}/pay`, { payment_method: method, payer_phone: phone, payment_reference: reference });
      notice('Paiement signalé', 'Lantante vérifie votre paiement puis valide la publication. Vous serez prévenu.');
      await loaded.reload();
    } catch (e) {
      setErrors(fieldErrors(e));
      notice('Paiement non enregistré', messageOf(e));
    } finally {
      setBusy(false);
    }
  };

  const cancel = () => confirm('Annuler cette publication ?', "Elle ne sera pas publiée et aucun paiement n'est dû.", 'Annuler la publication', async () => {
    try {
      await post(`orders/${id}/cancel`);
      await loaded.reload();
    } catch (e) {
      notice('Action impossible', messageOf(e));
    }
  }, true);

  const resubmit = async () => {
    setBusy(true);
    setErrors({});
    try {
      await api('PATCH', `orders/${id}`, { title, text, ...(image ? { image } : {}) });
      notice('Publication corrigée', 'Elle est renvoyée à Lantante pour validation.');
      setImage(null);
      await loaded.reload();
    } catch (e) {
      setErrors(fieldErrors(e));
      notice('Correction impossible', messageOf(e));
    } finally {
      setBusy(false);
    }
  };

  const pay_cfg = config?.payment;
  const textual = o && ['news', 'news_boost', 'ad'].includes(o.plan.kind);
  const failed = o && ['refused', 'refunded', 'cancelled'].includes(o.status);

  return (
    <Screen loaded={loaded}>
      {o ? (
        <>
          <Card>
            <T size={18} weight="800">{o.title || o.plan.name}</T>
            <Muted>{o.plan.name} · Réf. {o.reference}</Muted>
            <Badge label={o.status_label} tone={orderTone(o.status)} />
            <Steps labels={STEPS} current={Math.max(o.step, 0)} failedAt={failed ? Math.max(o.step, 0) : undefined} />
            <InfoLine icon="cash-outline" text={`Montant : ${o.amount_label}`} />
            <InfoLine icon="calendar-outline" text={`Créée le ${formatDate(o.created_at)}`} />
            {o.visible_until ? <InfoLine icon="eye-outline" text={`Visible jusqu'au ${formatDate(o.visible_until)}`} /> : null}
          </Card>
          {o.image ? <Image source={{ uri: o.image }} style={{ height: 160, borderRadius: 14, backgroundColor: colors.surface2 }} /> : null}
          {o.text ? <Card><T color={colors.ink2}>{o.text}</T></Card> : null}

          {o.review_message ? <Banner tone={o.status === 'refused' ? 'red' : 'gold'} icon="chatbubble-ellipses">{o.review_message}</Banner> : null}
          {o.status === 'quote' ? <Banner icon="time">Lantante prépare votre devis et vous contactera.</Banner> : null}
          {o.status === 'payment_declared' ? <Banner tone="gold" icon="hourglass">Paiement signalé : Lantante le vérifie.</Banner> : null}
          {o.status === 'in_review' ? <Banner icon="shield-checkmark">Paiement reçu. Lantante valide votre publication.</Banner> : null}
          {o.status === 'published' ? <Banner tone="green" icon="checkmark-circle">Votre publication est en ligne.</Banner> : null}
          {o.status === 'refunded' ? <Banner tone="grey" icon="return-down-back">Cette publication a été refusée et vous avez été remboursé.</Banner> : null}

          {o.can_pay ? (
            <Card>
              <H2>Payer {o.amount_label}</H2>
              <Muted size={13}>
                Envoyez le montant par Flooz ou T-Money, puis indiquez ci-dessous le numéro utilisé et la référence de la transaction.
              </Muted>
              {pay_cfg?.flooz ? <InfoLine icon="call-outline" text={`Flooz : ${pay_cfg.flooz}`} /> : null}
              {pay_cfg?.tmoney ? <InfoLine icon="call-outline" text={`T-Money : ${pay_cfg.tmoney}`} /> : null}
              {!pay_cfg?.flooz && !pay_cfg?.tmoney ? (
                <Button small variant="green" icon="logo-whatsapp" label="Demander les numéros de paiement sur WhatsApp"
                  onPress={() => Linking.openURL(`${whatsappLink(pay_cfg?.whatsapp || '')}?text=${encodeURIComponent(`Bonjour, je souhaite payer ma publication ${o.reference}.`)}`)} />
              ) : null}
              <Select label="Moyen de paiement" value={method} options={METHODS} onChange={setMethod} error={errors.payment_method} />
              <Input label="Numéro avec lequel vous avez payé" value={phone} onChangeText={setPhone} keyboardType="phone-pad" error={errors.payer_phone} />
              <Input label="Référence de la transaction" value={reference} onChangeText={setReference} error={errors.payment_reference} />
              <Button label="J'ai payé" icon="checkmark" variant="green" onPress={pay} loading={busy} disabled={!phone.trim() || !reference.trim()} />
            </Card>
          ) : null}

          {o.can_edit && o.status === 'changes_requested' ? (
            textual ? (
              <Card>
                <H2>Corriger la publication</H2>
                <Input label="Titre" value={title} onChangeText={setTitle} error={errors.title} />
                <Input label="Texte" value={text} onChangeText={setText} multiline error={errors.text} />
                <FilePicker label="Nouvelle image (facultative)" icon="image-outline" fileName={image?.name} onPress={async () => setImage((await pickImage()) ?? image)} />
                <Button label="Renvoyer pour validation" icon="send" onPress={resubmit} loading={busy} />
              </Card>
            ) : (
              <Button label="Corriger sur le site" variant="outline" icon="open-outline" onPress={() => Linking.openURL(`${SITE_URL}/emploi/mes-commandes/`)} />
            )
          ) : null}

          {o.paid_at ? <Button label="Voir le reçu" icon="receipt-outline" variant="outline" onPress={() => router.push(`/receipt/${o.id}` as never)} /> : null}
          {['awaiting_payment', 'quote'].includes(o.status) ? <Button label="Annuler cette publication" variant="ghost" onPress={cancel} /> : null}
        </>
      ) : null}
    </Screen>
  );
}
