import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';

import { post } from '@/lib/api';
import { formatDate, formatDateTime, toApiDateTime } from '@/lib/format';
import { messageOf, useLoad } from '@/lib/hooks';
import { colors } from '@/lib/theme';
import type { Application } from '@/lib/types';
import { Badge, Banner, Button, Card, DateField, H2, Input, Muted, Screen, Section, Steps, T, notice } from '@/ui';
import { AppointmentCard, applicationTone } from '@/ui/cards';

const STEPS = ['Envoyée', 'Présélection', 'Entretien', 'Accepté'];

export default function MyApplication() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const list = useLoad<Application[]>('candidate/applications');
  const a = list.data?.find((x) => String(x.id) === id) ?? null;
  const [slots, setSlots] = useState<(Date | null)[]>([null, null, null]);
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);

  const answer = async (value: 'accept' | 'decline') => {
    setBusy(true);
    try {
      await post(`candidate/applications/${id}/consent`, { answer: value });
      await list.reload();
    } catch (e) {
      notice('Action impossible', messageOf(e));
    } finally {
      setBusy(false);
    }
  };

  const sendSlots = async () => {
    const chosen = slots.filter(Boolean) as Date[];
    if (!chosen.length) return notice('Disponibilités', 'Choisissez au moins une date.');
    setBusy(true);
    try {
      await post(`candidate/applications/${id}/availability`, { slots: chosen.map(toApiDateTime), note });
      notice('Merci !', "Vos disponibilités ont été transmises. L'entreprise fixera la date de l'entretien.");
      await list.reload();
    } catch (e) {
      notice('Envoi impossible', messageOf(e));
    } finally {
      setBusy(false);
    }
  };

  const setSlot = (i: number) => (d: Date | null) => setSlots((s) => s.map((x, k) => (k === i ? d : x)));

  return (
    <Screen loaded={list}>
      {a ? (
        <>
          <T size={20} weight="800">{a.title}</T>
          <Muted>{a.company} · envoyée le {formatDate(a.created_at)}</Muted>
          <Badge label={a.status_label} tone={applicationTone(a.status)} />

          {a.consent === 'pending' ? (
            <Card style={{ borderColor: colors.gold, borderWidth: 2 }}>
              <H2>Lantante vous propose cette opportunité</H2>
              <T color={colors.ink2}>Acceptez-vous que votre dossier (CV, profil, lettre) soit transmis à {a.company} ?</T>
              <Button label="Oui, transmettre mon dossier" variant="green" icon="checkmark" onPress={() => answer('accept')} loading={busy} />
              <Button label="Non merci" variant="outline" onPress={() => answer('decline')} disabled={busy} />
            </Card>
          ) : a.consent === 'declined' ? <Banner tone="grey" icon="close-circle">Vous avez refusé cette proposition.</Banner> : (
            <Card>
              <Steps labels={STEPS} current={Math.max(a.step, 0)} failedAt={a.status === 'refused' ? Math.max(a.step, 0) : undefined} />
            </Card>
          )}

          {a.status_message ? <Banner tone={a.status === 'refused' ? 'red' : 'navy'} icon="chatbubble-ellipses">{a.status_message}</Banner> : null}
          {a.incomplete?.length ? <Banner tone="warn" icon="alert-circle">Dossier incomplet : {a.incomplete.join(', ')}. Complétez votre profil.</Banner> : null}

          {a.appointments.length ? (
            <Section title="Entretiens">
              {a.appointments.map((x) => <AppointmentCard key={x.id} appointment={x} />)}
              <Button label="Gérer mes rendez-vous" variant="outline" onPress={() => router.push('/appointments' as never)} />
            </Section>
          ) : null}

          {a.status === 'shortlisted' && !a.slots.length && !a.appointments.length ? (
            <Card>
              <H2>Vous êtes présélectionné(e) 🎉</H2>
              <T color={colors.ink2}>Proposez jusqu'à 3 créneaux pour l'entretien : l'entreprise en retiendra un.</T>
              {[0, 1, 2].map((i) => (
                <DateField key={i} label={`Disponibilité ${i + 1}${i ? ' (facultatif)' : ''}`} value={slots[i]} onChange={setSlot(i)} withTime minimumDate={new Date()} />
              ))}
              <Input label="Précision (facultatif)" value={note} onChangeText={setNote} placeholder="Plutôt le matin, en visio…" maxLength={200} />
              <Button label="Envoyer mes disponibilités" icon="send" onPress={sendSlots} loading={busy} />
            </Card>
          ) : null}
          {a.slots.length && !a.appointments.length ? (
            <Banner tone="navy" icon="time">
              Vos disponibilités ont été envoyées : {a.slots.map((s) => formatDateTime(s.start)).join(' ; ')}. L'entreprise va confirmer l'entretien.
            </Banner>
          ) : null}

          {a.offer ? <Button label="Revoir l'offre" variant="ghost" onPress={() => router.push(`/offer/${a.offer!.slug}` as never)} /> : null}
          {a.cover_letter ? <Section title="Ma lettre de motivation"><Card><T color={colors.ink2}>{a.cover_letter}</T></Card></Section> : null}
        </>
      ) : !list.loading ? <Banner tone="grey" icon="help-circle">Candidature introuvable.</Banner> : null}
    </Screen>
  );
}
