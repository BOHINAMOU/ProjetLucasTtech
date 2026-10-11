import { useState } from 'react';

import { useAuth } from '@/lib/auth';
import { messageOf } from '@/lib/hooks';
import { AccountTypeCards } from '@/screens/AccountTypeCards';
import { Banner, Button, Muted, Screen, T } from '@/ui';

export default function ChooseType() {
  const { chooseType, logout } = useAuth();
  const [type, setType] = useState('candidate');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const submit = async () => {
    setBusy(true);
    try {
      await chooseType(type);
    } catch (e) {
      setError(messageOf(e));
      setBusy(false);
    }
  };

  return (
    <Screen>
      <T size={20} weight="800">Bienvenue !</T>
      <Muted size={14}>Choisissez votre type de compte. Ce choix est définitif.</Muted>
      {error ? <Banner tone="red" icon="alert-circle">{error}</Banner> : null}
      <AccountTypeCards value={type} onChange={setType} />
      <Button label="Continuer" onPress={submit} loading={busy} />
      <Button label="Se déconnecter" variant="ghost" onPress={logout} />
    </Screen>
  );
}
