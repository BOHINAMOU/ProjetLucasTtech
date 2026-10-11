import { router, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';

import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { toApiDate } from '@/lib/format';
import { fieldErrors, messageOf, useLoad } from '@/lib/hooks';
import type { Candidate, SpontaneousRequest } from '@/lib/types';
import { Banner, Button, DateField, Input, Screen, Select, notice } from '@/ui';

type Me = Candidate & { exists: boolean };

export default function RequestEdit() {
  const { id } = useLocalSearchParams<{ id?: string }>();
  const { config } = useAuth();
  const list = useLoad<SpontaneousRequest[]>('candidate/requests');
  const profile = useLoad<Me>('candidate/profile');
  const existing = id ? list.data?.find((r) => String(r.id) === id) : undefined;

  const [f, setF] = useState({ request_type: 'job', domain: 'autre', skills_text: '', city: '', duration: '', message: '' });
  const [from, setFrom] = useState<Date | null>(null);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (ready || (id && !existing) || (!id && !profile.data)) return;
    if (existing) {
      setF({ request_type: existing.request_type, domain: existing.domain, skills_text: existing.skills.join(', '), city: existing.city,
        duration: existing.duration, message: existing.message });
      setFrom(existing.available_from ? new Date(existing.available_from) : null);
    } else if (profile.data?.exists) {
      const p = profile.data;
      setF((o) => ({ ...o, domain: p.domain || 'autre', skills_text: p.skills.join(', '), city: p.city }));
      setFrom(p.available_from ? new Date(p.available_from) : null);
    }
    setReady(true);
  }, [existing, profile.data, id, ready]);

  const set = (k: keyof typeof f) => (v: string) => setF((o) => ({ ...o, [k]: v }));

  const save = async () => {
    setBusy(true);
    setErrors({});
    try {
      await api(id ? 'PATCH' : 'POST', id ? `candidate/requests/${id}` : 'candidate/requests', { ...f, available_from: from ? toApiDate(from) : '' });
      notice(id ? 'Demande modifiée' : 'Demande envoyée', "Lantante la garde et vous proposera des opportunités. Votre dossier n'est transmis qu'avec votre accord.");
      router.back();
    } catch (e) {
      setErrors(fieldErrors(e));
      notice('Envoi impossible', messageOf(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen loaded={id ? list : profile}>
      {!profile.data?.exists && !id ? <Banner tone="warn" icon="alert-circle">Créez d'abord votre profil candidat.</Banner> : null}
      <Select label="Type de demande" value={f.request_type} options={config?.request_types ?? []} onChange={set('request_type')} error={errors.request_type} />
      <Select label="Domaine" value={f.domain} options={config?.domains ?? []} onChange={set('domain')} error={errors.domain} />
      <Input label="Compétences" value={f.skills_text} onChangeText={set('skills_text')} hint="Séparées par des virgules." error={errors.skills_text} />
      <Input label="Ville souhaitée" value={f.city} onChangeText={set('city')} error={errors.city} />
      <Select label="Durée souhaitée (stage, alternance)" value={f.duration} options={(config?.internship_durations ?? []).map((d) => ({ value: d, label: d }))}
        onChange={set('duration')} allowEmpty="— Sans objet —" />
      <DateField label="Disponible à partir du" value={from} onChange={setFrom} error={errors.available_from} />
      <Input label="Message" value={f.message} onChangeText={set('message')} multiline error={errors.message}
        placeholder="Décrivez ce que vous recherchez, votre parcours, vos atouts…" />
      <Button label={id ? 'Enregistrer' : 'Envoyer ma demande'} icon="send" onPress={save} loading={busy} />
    </Screen>
  );
}
