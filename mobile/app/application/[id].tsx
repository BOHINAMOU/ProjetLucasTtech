import { Ionicons } from '@expo/vector-icons';
import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Linking, Pressable, View } from 'react-native';

import { post } from '@/lib/api';
import { openPrivateFile } from '@/lib/files';
import { formatDate, formatDateTime, toApiDateTime } from '@/lib/format';
import { messageOf, useLoad } from '@/lib/hooks';
import { colors, space } from '@/lib/theme';
import type { Application } from '@/lib/types';
import { Avatar, Badge, Banner, Button, Card, DateField, H2, InfoLine, Input, Muted, Row, Screen, Section, T, confirm, notice } from '@/ui';
import { AppointmentCard, applicationTone } from '@/ui/cards';

export default function ReceivedApplication() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const loaded = useLoad<Application>(`employer/applications/${id}`);
  const a = loaded.data;
  const c = a?.candidate;
  const [message, setMessage] = useState('');
  const [when, setWhen] = useState<Date | null>(null);
  const [place, setPlace] = useState('');
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);

  const decide = (action: 'shortlist' | 'accept' | 'refuse') => {
    const texts = {
      shortlist: ['Présélectionner ce candidat ?', 'Il sera invité à proposer ses disponibilités pour un entretien.', 'Présélectionner'],
      accept: ['Accepter ce candidat ?', 'Il sera prévenu que sa candidature est acceptée.', 'Accepter'],
      refuse: ['Refuser cette candidature ?', 'Le candidat sera prévenu (avec votre message, si vous en écrivez un).', 'Refuser'],
    }[action];
    confirm(texts[0], texts[1], texts[2], async () => {
      setBusy(true);
      try {
        await post(`employer/applications/${id}/decide`, { action, message });
        setMessage('');
        await loaded.reload();
      } catch (e) {
        notice('Action impossible', messageOf(e));
      } finally {
        setBusy(false);
      }
    }, action === 'refuse');
  };

  const schedule = async () => {
    if (!when) return notice('Entretien', "Choisissez la date et l'heure.");
    setBusy(true);
    try {
      await post(`employer/applications/${id}/schedule`, { when: toApiDateTime(when), place, notes });
      notice('Entretien fixé', 'Le candidat a été prévenu et doit confirmer.');
      setWhen(null);
      await loaded.reload();
    } catch (e) {
      notice('Entretien non fixé', messageOf(e));
    } finally {
      setBusy(false);
    }
  };

  const openCv = async () => {
    if (!c?.cv_url) return;
    try {
      await openPrivateFile(c.cv_url, `CV-${c.name}.pdf`);
    } catch (e) {
      notice('Ouverture impossible', messageOf(e));
    }
  };

  const open = a && ['received', 'shortlisted', 'interview'].includes(a.status);
  return (
    <Screen loaded={loaded}>
      {a && c ? (
        <>
          <Card>
            <Row>
              <Avatar uri={c.avatar} name={c.name} size={60} />
              <View style={{ flex: 1, gap: 2 }}>
                <T size={19} weight="800">{c.name}</T>
                <Muted lines={2}>{c.headline}</Muted>
                <Badge label={a.status_label} tone={applicationTone(a.status)} />
              </View>
            </Row>
            <Muted size={13}>Pour : {a.title} · reçue le {formatDate(a.created_at)}</Muted>
            {a.incomplete?.length ? <Badge label={`Dossier incomplet : ${a.incomplete.join(', ')}`} tone="warn" icon="alert-circle" /> : null}
          </Card>

          <Card>
            <H2>Coordonnées</H2>
            <InfoLine icon="mail-outline" text={c.email} />
            <InfoLine icon="call-outline" text={c.phone} />
            <InfoLine icon="location-outline" text={c.city} />
            <Row>
              {c.phone ? <View style={{ flex: 1 }}><Button small variant="outline" icon="call" label="Appeler" onPress={() => Linking.openURL(`tel:${c.phone}`)} /></View> : null}
              {c.user_id ? <View style={{ flex: 1 }}><Button small icon="chatbubble-ellipses" label="Écrire"
                onPress={() => router.push(`/new-message?user_id=${c.user_id}&to=${encodeURIComponent(c.name)}` as never)} /></View> : null}
            </Row>
          </Card>

          {c.has_cv ? <Button label="Ouvrir le CV" icon="document-text" variant="outline" onPress={openCv} /> : null}
          {c.documents?.length ? (
            <Section title="Diplômes et documents">
              {c.documents.map((d) => (
                <Pressable key={d.id} onPress={() => openPrivateFile(d.url, d.title).catch((e) => notice('Ouverture impossible', messageOf(e)))}>
                  <Row gap={8}><Ionicons name="document-attach" size={20} color={colors.navy} /><T color={colors.navy} weight="600">{d.title}</T></Row>
                </Pressable>
              ))}
            </Section>
          ) : null}

          <Section title="Profil">
            <Card>
              <InfoLine icon="briefcase-outline" text={`${c.experience_years} an(s) d'expérience`} />
              <InfoLine icon="school-outline" text={c.education_level} />
              {c.skills.length ? <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>{c.skills.map((s) => <Badge key={s} label={s} tone="grey" />)}</View> : null}
              {c.bio ? <T size={14} color={colors.ink2}>{c.bio}</T> : null}
              {a.internship_duration ? <InfoLine icon="time-outline" text={`Stage souhaité : ${a.internship_duration}`} /> : null}
              {a.available_from ? <InfoLine icon="calendar-outline" text={`Disponible dès le ${formatDate(a.available_from)}`} /> : null}
            </Card>
          </Section>

          {a.cover_letter ? <Section title="Lettre de motivation"><Card><T color={colors.ink2}>{a.cover_letter}</T></Card></Section> : null}
          {a.status_message ? <Banner icon="chatbubble-ellipses">Votre message : {a.status_message}</Banner> : null}

          {a.slots.length ? (
            <Section title="Disponibilités proposées">
              {a.slots.map((s) => (
                <Pressable key={s.start} onPress={() => setWhen(new Date(s.start))}>
                  <Row gap={8}><Ionicons name="calendar" size={18} color={colors.green} /><T weight="600">{formatDateTime(s.start)}</T><Muted size={12}>(toucher pour choisir)</Muted></Row>
                </Pressable>
              ))}
              {a.slots[0].note ? <Muted size={13}>{a.slots[0].note}</Muted> : null}
            </Section>
          ) : null}

          {a.appointments.length ? <Section title="Entretiens">{a.appointments.map((x) => <AppointmentCard key={x.id} appointment={x} />)}</Section> : null}

          {open ? (
            <Card>
              <H2>Décision</H2>
              <Input label="Message au candidat (facultatif)" value={message} onChangeText={setMessage} multiline placeholder="Un mot pour le candidat, le motif d'un refus…" />
              {a.status === 'received' ? <Button label="Présélectionner" icon="star" onPress={() => decide('shortlist')} disabled={busy} /> : null}
              <Button label="Accepter" icon="checkmark-circle" variant="green" onPress={() => decide('accept')} disabled={busy} />
              <Button label="Refuser" icon="close-circle" variant="outline" onPress={() => decide('refuse')} disabled={busy} />
            </Card>
          ) : null}

          {a.status === 'shortlisted' || a.status === 'interview' ? (
            <Card>
              <H2>Fixer un entretien</H2>
              <DateField label="Date et heure" value={when} onChange={setWhen} withTime minimumDate={new Date()} />
              <Input label="Lieu ou lien visio" value={place} onChangeText={setPlace} placeholder="Bureau de Lomé, Google Meet…" />
              <Input label="Précisions (facultatif)" value={notes} onChangeText={setNotes} multiline />
              <Button label="Proposer cet entretien" icon="calendar" onPress={schedule} loading={busy} />
            </Card>
          ) : null}
        </>
      ) : null}
    </Screen>
  );
}
