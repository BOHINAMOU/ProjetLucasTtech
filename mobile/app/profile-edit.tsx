import { router } from 'expo-router';
import { useEffect, useState } from 'react';

import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { toApiDate } from '@/lib/format';
import { pickDocument, pickImage, type Picked } from '@/lib/files';
import { fieldErrors, messageOf, useLoad } from '@/lib/hooks';
import type { Candidate } from '@/lib/types';
import { Banner, Button, DateField, FilePicker, Input, MultiChoice, Screen, Select, Switch2, notice } from '@/ui';

type Me = Candidate & { exists: boolean; first_name?: string; last_name?: string };

/** Création et modification du profil candidat (le CV et la lettre par défaut servent à chaque candidature). */
export default function ProfileEdit() {
  const { user, config, refresh } = useAuth();
  const loaded = useLoad<Me>('candidate/profile');
  const p = loaded.data;
  const [f, setF] = useState({
    first_name: '', last_name: '', headline: '', domain: 'autre', city: '', bio: '', experience_years: '0', education_level: '',
    phone: '', skills_text: '', cover_letter: '', internship_duration: '',
  });
  const [contracts, setContracts] = useState<string[]>([]);
  const [available, setAvailable] = useState(true);
  const [internship, setInternship] = useState(false);
  const [from, setFrom] = useState<Date | null>(null);
  const [cv, setCv] = useState<Picked | null>(null);
  const [photo, setPhoto] = useState<Picked | null>(null);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!loaded.data || ready) return;
    const d = loaded.data;
    setF({
      first_name: d.first_name ?? user?.first_name ?? '', last_name: d.last_name ?? user?.last_name ?? '',
      headline: d.headline ?? '', domain: d.domain || 'autre', city: d.city ?? user?.city ?? '', bio: d.bio ?? '',
      experience_years: String(d.experience_years ?? 0), education_level: d.education_level ?? '', phone: d.phone ?? user?.phone ?? '',
      skills_text: (d.skills ?? []).join(', '), cover_letter: d.cover_letter ?? '', internship_duration: d.internship_duration ?? '',
    });
    setContracts(d.contract_wanted ?? []);
    setAvailable(d.exists ? d.available : true);
    setInternship(!!d.seeking_internship);
    setFrom(d.available_from ? new Date(d.available_from) : null);
    setReady(true);
  }, [loaded.data, ready, user]);

  const set = (k: keyof typeof f) => (v: string) => setF((o) => ({ ...o, [k]: v }));

  const save = async () => {
    setBusy(true);
    setErrors({});
    try {
      await api(p?.exists ? 'PATCH' : 'POST', 'candidate/profile', {
        ...f, contract_wanted: contracts, available, seeking_internship: internship, available_from: from ? toApiDate(from) : '',
        ...(cv ? { cv } : {}), ...(photo ? { avatar: photo } : {}),
      });
      await refresh();
      notice('Profil enregistré');
      router.back();
    } catch (e) {
      setErrors(fieldErrors(e));
      notice('Profil incomplet', messageOf(e));
    } finally {
      setBusy(false);
    }
  };

  const cvName = cv?.name ?? (p?.has_cv ? 'CV déjà envoyé (touchez pour le remplacer)' : null);
  return (
    <Screen loaded={loaded}>
      {!p?.has_cv && !cv ? <Banner tone="warn" icon="document-attach">Le CV (PDF) est obligatoire pour postuler.</Banner> : null}
      <FilePicker label="Photo de profil" icon="camera-outline" fileName={photo?.name} onPress={async () => setPhoto((await pickImage(true)) ?? photo)} />
      <Input label="Prénom" value={f.first_name} onChangeText={set('first_name')} error={errors.first_name} />
      <Input label="Nom" value={f.last_name} onChangeText={set('last_name')} error={errors.last_name} />
      <Input label="Titre / métier recherché" value={f.headline} onChangeText={set('headline')} error={errors.headline} placeholder="Ex : Comptable junior" />
      <Select label="Domaine" value={f.domain} options={config?.domains ?? []} onChange={set('domain')} error={errors.domain} />
      <Input label="Compétences" value={f.skills_text} onChangeText={set('skills_text')} placeholder="Excel, Python, Gestion de stock" hint="Séparées par des virgules." error={errors.skills_text} />
      <Input label="Ville" value={f.city} onChangeText={set('city')} error={errors.city} />
      <Input label="Téléphone" value={f.phone} onChangeText={set('phone')} keyboardType="phone-pad" error={errors.phone} />
      <Input label="Années d'expérience" value={f.experience_years} onChangeText={set('experience_years')} keyboardType="number-pad" error={errors.experience_years} />
      <Select label="Niveau d'études" value={f.education_level} options={config?.education_levels ?? []} onChange={set('education_level')} allowEmpty="— Non précisé —" error={errors.education_level} />
      <Input label="À propos de moi" value={f.bio} onChangeText={set('bio')} multiline error={errors.bio} />
      <MultiChoice label="Types de contrat souhaités" options={config?.contracts ?? []} values={contracts} onChange={setContracts} />
      <Switch2 label="Je suis disponible" value={available} onChange={setAvailable} />
      <Switch2 label="Je cherche un stage" value={internship} onChange={setInternship} />
      {internship ? (
        <Select label="Durée de stage souhaitée" value={f.internship_duration} options={(config?.internship_durations ?? []).map((d) => ({ value: d, label: d }))}
          onChange={set('internship_duration')} allowEmpty="— Choisir —" />
      ) : null}
      <DateField label="Disponible à partir du" value={from} onChange={setFrom} />
      <FilePicker label="CV (PDF)" icon="document-attach-outline" fileName={cvName} error={errors.cv}
        onPress={async () => setCv((await pickDocument(['application/pdf'])) ?? cv)} hint="PDF uniquement. Il est envoyé avec chaque candidature." />
      <Input label="Lettre de motivation par défaut" value={f.cover_letter} onChangeText={set('cover_letter')} multiline error={errors.cover_letter}
        placeholder="Madame, Monsieur, …" hint="Proposée à chaque candidature ; vous pouvez l'adapter à chaque offre." />
      <Button label="Enregistrer" icon="save-outline" onPress={save} loading={busy} />
    </Screen>
  );
}
