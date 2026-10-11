import { Link } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, View } from 'react-native';

import { useAuth } from '@/lib/auth';
import { fieldErrors, messageOf } from '@/lib/hooks';
import { space } from '@/lib/theme';
import { AuthHero } from '@/screens/AuthHero';
import { AccountTypeCards } from '@/screens/AccountTypeCards';
import { Banner, Button, Input, Muted, T } from '@/ui';



export default function Register() {
  const { register } = useAuth();
  const [type, setType] = useState('candidate');
  const [form, setForm] = useState({ first_name: '', last_name: '', email: '', phone: '', password: '' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const set = (k: keyof typeof form) => (v: string) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    setBusy(true);
    setError('');
    setErrors({});
    try {
      await register({ ...form, email: form.email.trim(), account_type: type });
    } catch (e) {
      setErrors(fieldErrors(e));
      setError(messageOf(e));
      setBusy(false);
    }
  };

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ flexGrow: 1 }}>
        <AuthHero title="Créer un compte" subtitle="Choisissez le type de compte qui vous correspond." />
        <View style={{ padding: space.xl, gap: space.lg }}>
          <AccountTypeCards value={type} onChange={setType} />
          <Muted size={12}>Le type de compte ne peut pas être changé ensuite. Une entreprise qui cherche aussi un emploi utilise une autre adresse e-mail.</Muted>
          {error ? <Banner tone="red" icon="alert-circle">{error}</Banner> : null}
          <Input label="Prénom" value={form.first_name} onChangeText={set('first_name')} error={errors.first_name} autoComplete="given-name" />
          <Input label="Nom" value={form.last_name} onChangeText={set('last_name')} error={errors.last_name} autoComplete="family-name" />
          <Input label="Adresse e-mail" value={form.email} onChangeText={set('email')} error={errors.email} autoCapitalize="none"
            keyboardType="email-address" autoComplete="email" />
          <Input label="Téléphone (facultatif)" value={form.phone} onChangeText={set('phone')} error={errors.phone} keyboardType="phone-pad" />
          <Input label="Mot de passe" value={form.password} onChangeText={set('password')} secureTextEntry autoCapitalize="none"
            error={errors.password1 || errors.password} hint="8 caractères minimum, pas uniquement des chiffres." />
          <Button label="Créer mon compte" onPress={submit} loading={busy} />
          <View style={{ alignItems: 'center', gap: 4 }}>
            <T size={14} color="#64748b">Déjà un compte ?</T>
            <Link href="/login" replace><T weight="700" color="#0d3b7a">Se connecter</T></Link>
          </View>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
