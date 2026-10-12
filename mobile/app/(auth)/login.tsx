import { Link } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Linking, Platform, ScrollView, View } from 'react-native';

import { SITE_URL } from '@/lib/api';
import { useAuth } from '@/lib/auth';
import { messageOf } from '@/lib/hooks';
import { radius, space } from '@/lib/theme';
import { AuthHero } from '@/screens/AuthHero';
import InstallApp from '@/screens/InstallApp';
import { Banner, Button, Input, Muted, T } from '@/ui';

export default function Login() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const submit = async () => {
    if (!email.trim() || !password) return setError('Saisissez votre adresse e-mail et votre mot de passe.');
    setBusy(true);
    setError('');
    try {
      await login(email.trim(), password);
    } catch (e) {
      setError(messageOf(e));
      setBusy(false);
    }
  };

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ flexGrow: 1 }}>
        <AuthHero title="Lantante Technologie Job" subtitle="Offres d'emploi, stages et recrutement au Togo et en Afrique." />
        <View style={{ padding: space.xl, gap: space.lg }}>
          <InstallApp />
          <T size={20} weight="800">Connexion</T>
          {error ? <Banner tone="red" icon="alert-circle">{error}</Banner> : null}
          <Input label="Adresse e-mail" value={email} onChangeText={setEmail} autoCapitalize="none" autoComplete="email"
            keyboardType="email-address" placeholder="vous@exemple.com" />
          <Input label="Mot de passe" value={password} onChangeText={setPassword} secureTextEntry autoCapitalize="none"
            autoComplete="password" placeholder="••••••••" onSubmitEditing={submit} />
          <Button label="Se connecter" onPress={submit} loading={busy} />
          <Button label="Mot de passe oublié ?" variant="ghost" small onPress={() => Linking.openURL(`${SITE_URL}/users/mot-de-passe/oublie/`)} />
          <View style={{ alignItems: 'center', gap: 4, marginTop: space.sm }}>
            <Muted size={14}>Pas encore de compte ?</Muted>
            <Link href="/register" asChild>
              <Button label="Créer un compte" variant="outline" onPress={() => {}} style={{ alignSelf: 'stretch', borderRadius: radius.md }} />
            </Link>
          </View>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
