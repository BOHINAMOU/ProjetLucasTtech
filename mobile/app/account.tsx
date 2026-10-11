import { useEffect, useState } from 'react';
import { Linking } from 'react-native';

import { api, SITE_URL } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { pickImage, type Picked } from '@/lib/files';
import { fieldErrors, messageOf } from '@/lib/hooks';
import { Avatar, Banner, Button, FilePicker, H2, Input, Muted, Row, Screen, Card, notice, confirm } from '@/ui';

const TYPE_LABELS: Record<string, string> = { candidate: "Compte candidat (je cherche un emploi)", employer: 'Compte entreprise', member: 'Compte particulier' };

export default function Account() {
  const { user, refresh, logout } = useAuth();
  const [f, setF] = useState({ first_name: '', last_name: '', phone: '', city: '', country: '' });
  const [photo, setPhoto] = useState<Picked | null>(null);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (user) setF({ first_name: user.first_name, last_name: user.last_name, phone: user.phone, city: user.city, country: user.country });
  }, [user]);
  const set = (k: keyof typeof f) => (v: string) => setF((o) => ({ ...o, [k]: v }));

  const save = async () => {
    setBusy(true);
    setErrors({});
    try {
      await api('PATCH', 'me', { ...f, ...(photo ? { avatar: photo } : {}) });
      await refresh();
      setPhoto(null);
      notice('Compte mis à jour');
    } catch (e) {
      setErrors(fieldErrors(e));
      notice('Enregistrement impossible', messageOf(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen>
      <Row>
        <Avatar uri={user?.avatar} name={user?.name || ''} size={64} />
        <Muted size={14}>{user?.email}{'\n'}{TYPE_LABELS[user?.account_type || ''] ?? ''}</Muted>
      </Row>
      <Card>
        <H2>Mes informations</H2>
        <Input label="Prénom" value={f.first_name} onChangeText={set('first_name')} error={errors.first_name} />
        <Input label="Nom" value={f.last_name} onChangeText={set('last_name')} error={errors.last_name} />
        <Input label="Téléphone" value={f.phone} onChangeText={set('phone')} keyboardType="phone-pad" error={errors.phone} />
        <Input label="Ville" value={f.city} onChangeText={set('city')} error={errors.city} />
        <Input label="Pays" value={f.country} onChangeText={set('country')} error={errors.country} />
        <FilePicker label="Photo" icon="camera-outline" fileName={photo?.name} onPress={async () => setPhoto((await pickImage(true)) ?? photo)} />
        <Button label="Enregistrer" onPress={save} loading={busy} />
      </Card>
      <Banner icon="information-circle">Le type de compte ne peut pas être changé. Pour changer de mot de passe ou supprimer votre compte, rendez-vous sur le site.</Banner>
      <Button label="Gérer mon compte sur le site" variant="outline" icon="open-outline" onPress={() => Linking.openURL(`${SITE_URL}/users/profil/`)} />
      <Button label="Se déconnecter" variant="ghost" icon="log-out-outline"
        onPress={() => confirm('Se déconnecter ?', 'Vous devrez saisir à nouveau vos identifiants.', 'Se déconnecter', logout)} />
    </Screen>
  );
}
