import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Image, View } from 'react-native';

import { post } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { formatDate, toApiDate } from '@/lib/format';
import { fieldErrors, messageOf, useLoad } from '@/lib/hooks';
import { colors, space } from '@/lib/theme';
import type { Candidate, OfferDetail } from '@/lib/types';
import { Badge, Banner, Button, Card, DateField, H2, InfoLine, Input, Logo, Muted, Row, Screen, Section, Select, T, VerifiedBadge, notice } from '@/ui';

type Me = Candidate & { exists: boolean };

export default function OfferScreen() {
  const { slug } = useLocalSearchParams<{ slug: string }>();
  const { kind, config } = useAuth();
  const offer = useLoad<OfferDetail>(`offers/${slug}`);
  const profile = useLoad<Me>(kind === 'candidate' ? 'candidate/profile' : null);
  const o = offer.data;
  const p = profile.data;

  const [letter, setLetter] = useState('');
  const [duration, setDuration] = useState('');
  const [from, setFrom] = useState<Date | null>(null);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [sent, setSent] = useState(false);

  useEffect(() => {
    if (p?.exists) {
      setLetter((old) => old || p.cover_letter || '');
      setDuration((old) => old || p.internship_duration || o?.duration || '');
      if (p.available_from) setFrom((old) => old || new Date(p.available_from as string));
    }
  }, [p, o?.duration]);

  const isInternship = o?.contract === 'stage';

  const apply = async () => {
    setBusy(true);
    setErrors({});
    try {
      await post(`offers/${slug}/apply`, {
        text: letter, ...(isInternship ? { internship_duration: duration, available_from: from ? toApiDate(from) : '' } : {}),
      });
      setSent(true);
      notice('Candidature envoyée', "Votre dossier (CV, profil, lettre) a été transmis directement à l'entreprise.");
      offer.reload();
    } catch (e) {
      setErrors(fieldErrors(e));
      const code = (e as { code?: string }).code;
      if (code === 'no_cv' || code === 'no_profile') {
        notice(code === 'no_cv' ? 'CV manquant' : 'Profil à créer', messageOf(e));
        router.push('/profile-edit' as never);
      } else if (!Object.keys(fieldErrors(e)).length) {
        notice('Candidature impossible', messageOf(e));
      }
    } finally {
      setBusy(false);
    }
  };

  const company = o?.company;
  return (
    <Screen loaded={offer}>
      {o ? (
        <>
          {o.cover_image ? <Image source={{ uri: o.cover_image }} style={{ height: 170, borderRadius: 16, backgroundColor: colors.surface2 }} /> : null}
          <T size={22} weight="800">{o.title}</T>
          <Row>
            <Logo uri={company?.logo ?? o.company_logo} name={company?.name ?? ''} size={44} />
            <View style={{ flex: 1 }}>
              <Row gap={6}><T weight="700" lines={1}>{company?.name ?? 'Lantante Technologie'}</T>{company?.verified ? <VerifiedBadge /> : null}</Row>
              {company ? <T size={13} weight="600" color={colors.navy} onPress={() => router.push(`/company/${company.id}` as never)}>Voir l'entreprise</T> : null}
            </View>
          </Row>
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
            {o.featured ? <Badge label="À la une" tone="gold" icon="star" /> : null}
            <Badge label={o.contract_label} tone="navy" />
            {o.domain_label ? <Badge label={o.domain_label} tone="grey" /> : null}
            {o.duration ? <Badge label={o.duration} tone="grey" icon="time-outline" /> : null}
          </View>
          <Card>
            <InfoLine icon="location-outline" text={o.city} />
            <InfoLine icon="cash-outline" text={o.salary} />
            {o.deadline ? <InfoLine icon="calendar-outline" text={`Date limite : ${formatDate(o.deadline)}`} /> : null}
          </Card>
          <Section title="Description"><T color={colors.ink2}>{o.description}</T></Section>
          {o.requirements ? <Section title="Profil recherché"><T color={colors.ink2}>{o.requirements}</T></Section> : null}
          {o.skills?.length ? (
            <Section title="Compétences">
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>{o.skills.map((s) => <Badge key={s} label={s} tone="grey" />)}</View>
            </Section>
          ) : null}

          {kind === 'candidate' ? (
            o.applied || sent ? (
              <Banner tone="green" icon="checkmark-circle">Vous avez déjà postulé à cette offre. Suivez-la dans l'onglet « Candidatures ».</Banner>
            ) : o.can_apply ? (
              <Card>
                <H2>Postuler</H2>
                <Muted size={13}>Votre CV, votre profil et votre lettre sont envoyés directement à l'entreprise.</Muted>
                {!p?.exists || !p.has_cv ? (
                  <Banner tone="warn" icon="document-attach">Pour postuler, ajoutez d'abord votre CV (PDF) à votre profil.</Banner>
                ) : null}
                {isInternship ? (
                  <>
                    <Select label="Durée de stage souhaitée" value={duration} error={errors.internship_duration}
                      options={(config?.internship_durations ?? []).map((d) => ({ value: d, label: d }))} onChange={setDuration} />
                    <DateField label="Disponible à partir du" value={from} onChange={setFrom} error={errors.available_from} />
                  </>
                ) : null}
                <Input label={o.requires_cover_letter ? "Lettre de motivation (demandée)" : 'Lettre de motivation (facultative)'} multiline
                  value={letter} onChangeText={setLetter} error={errors.text} placeholder="Pourquoi ce poste vous intéresse…"
                  hint={o.requires_cover_letter ? '80 caractères minimum.' : 'Adaptez votre lettre par défaut à cette offre.'} />
                <Button label="Envoyer ma candidature" icon="paper-plane" variant="green" onPress={apply} loading={busy} />
              </Card>
            ) : (
              <Banner tone="grey" icon="lock-closed">Cette offre n'accepte plus de candidatures.</Banner>
            )
          ) : null}
        </>
      ) : null}
    </Screen>
  );
}
