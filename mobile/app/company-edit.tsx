import { router } from 'expo-router';
import { useEffect, useState } from 'react';

import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { pickDocument, pickImage, type Picked } from '@/lib/files';
import { fieldErrors, messageOf, useLoad } from '@/lib/hooks';
import type { EmployerProfileData } from '@/lib/types';
import { Banner, Button, FilePicker, Input, Screen, Select, notice } from '@/ui';

/** Fiche entreprise : envoyée à Lantante pour analyse (logo et document officiel obligatoires). */
export default function CompanyEdit() {
  const { config, refresh } = useAuth();
  const loaded = useLoad<EmployerProfileData>('employer/profile');
  const c = loaded.data;
  const [f, setF] = useState({ company_name: '', sector: 'autre', city: '', employees_count: '', description: '', products: '', website: '', whatsapp: '', contact_email: '' });
  const [logo, setLogo] = useState<Picked | null>(null);
  const [doc, setDoc] = useState<Picked | null>(null);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!c || ready) return;
    if (c.exists) {
      setF({ company_name: c.name, sector: c.sector || 'autre', city: c.city, employees_count: String(c.employees_count ?? ''),
        description: c.description ?? '', products: (c.products ?? []).join('\n'), website: c.website ?? '', whatsapp: c.whatsapp ?? '',
        contact_email: c.contact_email ?? '' });
    }
    setReady(true);
  }, [c, ready]);

  const set = (k: keyof typeof f) => (v: string) => setF((o) => ({ ...o, [k]: v }));

  const save = async () => {
    setBusy(true);
    setErrors({});
    try {
      await api(c?.exists ? 'PATCH' : 'POST', 'employer/profile', { ...f, ...(logo ? { logo } : {}), ...(doc ? { document: doc } : {}) });
      await refresh();
      notice(c?.exists ? 'Fiche enregistrée' : 'Entreprise envoyée', c?.exists ? undefined : 'Lantante analyse votre entreprise. Vous serez prévenu de la décision.');
      router.back();
    } catch (e) {
      setErrors(fieldErrors(e));
      notice('Fiche incomplète', messageOf(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen loaded={loaded}>
      {!c?.exists ? <Banner icon="information-circle">Lantante vérifie chaque entreprise avant publication. Joignez un document officiel (registre de commerce, attestation…).</Banner> : null}
      <Input label="Nom de l'entreprise" value={f.company_name} onChangeText={set('company_name')} error={errors.company_name} />
      <FilePicker label="Logo" icon="image-outline" fileName={logo?.name ?? (c?.logo ? 'Logo déjà envoyé (toucher pour changer)' : null)} error={errors.logo}
        onPress={async () => setLogo((await pickImage(true)) ?? logo)} />
      <Select label="Secteur d'activité" value={f.sector} options={config?.domains ?? []} onChange={set('sector')} error={errors.sector} />
      <Input label="Ville" value={f.city} onChangeText={set('city')} error={errors.city} />
      <Input label="Nombre d'employés" value={f.employees_count} onChangeText={set('employees_count')} keyboardType="number-pad" error={errors.employees_count} />
      <Input label="Présentation" value={f.description} onChangeText={set('description')} multiline error={errors.description} />
      <Input label="Produits et services" value={f.products} onChangeText={set('products')} multiline error={errors.products} hint="Un par ligne." />
      <Input label="Site web" value={f.website} onChangeText={set('website')} autoCapitalize="none" keyboardType="url" error={errors.website} />
      <Input label="WhatsApp" value={f.whatsapp} onChangeText={set('whatsapp')} keyboardType="phone-pad" error={errors.whatsapp} />
      <Input label="E-mail de contact" value={f.contact_email} onChangeText={set('contact_email')} autoCapitalize="none" keyboardType="email-address" error={errors.contact_email} />
      <FilePicker label="Document officiel (PDF, Word, Excel)" icon="document-attach-outline" error={errors.document}
        fileName={doc?.name ?? (c?.has_document ? 'Document déjà envoyé (toucher pour changer)' : null)}
        onPress={async () => setDoc((await pickDocument(['application/pdf', 'application/msword',
          'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'application/vnd.ms-excel',
          'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'])) ?? doc)} />
      <Button label={c?.exists ? 'Enregistrer' : 'Envoyer pour analyse'} icon="send" onPress={save} loading={busy} />
    </Screen>
  );
}
