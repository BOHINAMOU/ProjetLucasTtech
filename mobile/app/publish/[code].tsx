import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';

import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { toApiDate } from '@/lib/format';
import { pickImage, type Picked } from '@/lib/files';
import { fieldErrors, messageOf, useLoad } from '@/lib/hooks';
import type { Offer, Order, Plan } from '@/lib/types';
import { Badge, Banner, Button, Card, DateField, FilePicker, H2, Input, Muted, Row, Screen, Select, Switch2, notice } from '@/ui';

const POST_KINDS = [{ value: 'news', label: 'Actualité' }, { value: 'product', label: 'Nouveau produit / service' }];
const URGENCY = [{ value: 'normal', label: 'Normale' }, { value: 'urgent', label: 'Urgente' }];

/** Formulaire d'actualité : le contenu dépend du service choisi (actualité, offre, publicité, mise en avant, accompagnement). */
export default function Publish() {
  const { code } = useLocalSearchParams<{ code: string }>();
  const { config, kind } = useAuth();
  const plans = useLoad<{ exempt: boolean; plans: Plan[] }>('publish/plans');
  const plan = plans.data?.plans.find((p) => p.code === code);
  const isBoost = plan?.kind === 'job_boost';
  const myOffers = useLoad<Offer[]>(isBoost ? 'employer/offers' : null);

  const [f, setF] = useState({
    title: '', text: '', post_kind: 'news', link_url: '', domain: 'autre', contract: 'cdi', city: '', description: '', requirements: '',
    salary: '', duration: '', skills_text: '', positions: '1', urgency: 'normal', offer: '',
  });
  const [deadline, setDeadline] = useState<Date | null>(null);
  const [needsLetter, setNeedsLetter] = useState(false);
  const [image, setImage] = useState<Picked | null>(null);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const set = (k: keyof typeof f) => (v: string) => setF((o) => ({ ...o, [k]: v }));

  const submit = async () => {
    if (!plan) return;
    setBusy(true);
    setErrors({});
    try {
      let body: Record<string, unknown> = { plan: plan.code };
      if (plan.kind === 'job') {
        body = { ...body, title: f.title, domain: f.domain, contract: f.contract, city: f.city, description: f.description, requirements: f.requirements,
          salary: f.salary, duration: f.duration, skills_text: f.skills_text, deadline: deadline ? toApiDate(deadline) : '',
          requires_cover_letter: needsLetter, ...(image ? { cover_image: image } : {}) };
      } else if (plan.kind === 'recruit') {
        body = { ...body, title: f.title, domain: f.domain, contract: f.contract, city: f.city, description: f.description,
          skills_text: f.skills_text, positions: f.positions, urgency: f.urgency };
      } else if (plan.kind === 'job_boost') {
        body = { ...body, offer: f.offer };
      } else {
        body = { ...body, title: f.title, text: f.text, post_kind: f.post_kind, ...(plan.kind === 'ad' ? { link_url: f.link_url } : {}),
          ...(image ? { image } : {}) };
      }
      const order = await api<Order>('POST', 'orders', body);
      router.replace(`/order/${order.id}` as never);
    } catch (e) {
      setErrors(fieldErrors(e));
      notice('Actualité incomplète', messageOf(e));
      setBusy(false);
    }
  };

  const k = plan?.kind;
  const exempt = plans.data?.exempt;
  return (
    <Screen loaded={plans}>
      {plan ? (
        <>
          <Card>
            <H2>{plan.name}</H2>
            <Muted size={13}>{plan.description}</Muted>
            <Row><Badge label={exempt ? 'Sans frais' : plan.price_label} tone={exempt ? 'green' : 'gold'} />{plan.duration_days ? <Muted size={12}>{plan.duration_days} jours</Muted> : null}</Row>
          </Card>

          {k === 'news' || k === 'news_boost' || k === 'ad' ? (
            <>
              {k !== 'ad' && kind !== 'member' ? <Select label="Type d'actualité" value={f.post_kind} options={POST_KINDS} onChange={set('post_kind')} /> : null}
              <Input label="Titre (facultatif)" value={f.title} onChangeText={set('title')} error={errors.title} />
              <Input label={k === 'ad' ? 'Texte de la publicité' : "Texte de l'actualité"} value={f.text} onChangeText={set('text')} multiline error={errors.text} />
              <FilePicker label={k === 'ad' ? 'Visuel de la publicité' : 'Image (facultative)'} icon="image-outline" fileName={image?.name} error={errors.image}
                onPress={async () => setImage((await pickImage()) ?? image)} />
              {k === 'ad' ? <Input label="Lien (site, page Facebook, WhatsApp…)" value={f.link_url} onChangeText={set('link_url')} autoCapitalize="none" keyboardType="url" error={errors.link_url} /> : null}
            </>
          ) : null}

          {k === 'job' || k === 'recruit' ? (
            <>
              <Input label={k === 'job' ? "Intitulé du poste" : 'Poste recherché'} value={f.title} onChangeText={set('title')} error={errors.title} />
              {k === 'job' ? <FilePicker label="Photo de couverture" icon="image-outline" fileName={image?.name} error={errors.cover_image}
                onPress={async () => setImage((await pickImage()) ?? image)} /> : null}
              <Select label="Domaine" value={f.domain} options={config?.domains ?? []} onChange={set('domain')} error={errors.domain} />
              <Select label="Type de contrat" value={f.contract} options={config?.contracts ?? []} onChange={set('contract')} error={errors.contract} />
              <Input label="Ville" value={f.city} onChangeText={set('city')} error={errors.city} />
              <Input label="Description" value={f.description} onChangeText={set('description')} multiline error={errors.description} />
              {k === 'job' ? (
                <>
                  <Input label="Profil recherché" value={f.requirements} onChangeText={set('requirements')} multiline error={errors.requirements} />
                  <Input label="Rémunération (facultatif)" value={f.salary} onChangeText={set('salary')} error={errors.salary} />
                  <Select label="Durée (stage, CDD…)" value={f.duration} options={(config?.internship_durations ?? []).map((d) => ({ value: d, label: d }))}
                    onChange={set('duration')} allowEmpty="— Aucune —" />
                  <DateField label="Date limite de candidature" value={deadline} onChange={setDeadline} minimumDate={new Date()} error={errors.deadline} />
                  <Switch2 label="Exiger une lettre de motivation" value={needsLetter} onChange={setNeedsLetter} />
                </>
              ) : (
                <>
                  <Input label="Nombre de postes" value={f.positions} onChangeText={set('positions')} keyboardType="number-pad" error={errors.positions} />
                  <Select label="Urgence" value={f.urgency} options={URGENCY} onChange={set('urgency')} />
                </>
              )}
              <Input label="Compétences" value={f.skills_text} onChangeText={set('skills_text')} hint="Séparées par des virgules." error={errors.skills_text} />
            </>
          ) : null}

          {k === 'job_boost' ? (
            myOffers.data && !myOffers.data.some((o) => o.status === 'published') ? (
              <Banner tone="gold" icon="information-circle">Vous n'avez pas encore d'offre publiée à mettre en avant.</Banner>
            ) : (
              <Select label="Offre à mettre en avant" value={f.offer} error={errors.offer}
                options={(myOffers.data ?? []).filter((o) => o.status === 'published').map((o) => ({ value: String(o.id), label: o.title }))} onChange={set('offer')} />
            )
          ) : null}

          {plan.quote_only ? <Banner icon="information-circle">Ce service est sur devis : Lantante vous contactera après votre demande.</Banner> : null}
          <Button label={exempt ? 'Envoyer pour validation' : plan.quote_only ? 'Demander un devis' : 'Continuer vers le paiement'} icon="arrow-forward" onPress={submit} loading={busy} />
        </>
      ) : !plans.loading ? <Banner tone="grey" icon="help-circle">Service introuvable.</Banner> : null}
    </Screen>
  );
}
