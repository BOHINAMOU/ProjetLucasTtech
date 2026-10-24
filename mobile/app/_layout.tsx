import { Stack, router, useSegments } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { useEffect } from 'react';
import { View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { AuthProvider, homeFor, useAuth } from '@/lib/auth';
import { listenToNotificationTaps } from '@/lib/push';
import { colors } from '@/lib/theme';
import { Loader } from '@/ui';

/** Redirige selon l'état de connexion et le type de compte (candidat, entreprise, particulier). */
function Gate() {
  const { user, kind, loading } = useAuth();
  const segments = useSegments();
  const first = segments[0] as string | undefined;

  useEffect(() => {
    if (loading) return;
    const inAuth = first === '(auth)';
    const spaces: Record<string, string> = { candidate: '(candidate)', employer: '(employer)', member: '(member)' };
    if (!user) {
      if (!inAuth && first !== 'telecharger') router.replace('/login');
      return;
    }
    if (kind === 'undefined') {
      if (first !== 'choose-type') router.replace('/choose-type');
      return;
    }
    const mine = spaces[kind];
    const inSpace = first === '(candidate)' || first === '(employer)' || first === '(member)';
    if (inAuth || first === 'choose-type' || first === undefined || (inSpace && first !== mine)) {
      router.replace(homeFor(kind) as never);
    }
  }, [user, kind, loading, first]);

  useEffect(() => listenToNotificationTaps(), []);

  if (loading) return <View style={{ flex: 1, backgroundColor: colors.bg }}><Loader /></View>;
  return (
    <Stack screenOptions={{
      headerStyle: { backgroundColor: colors.navy }, headerTintColor: colors.white, headerTitleStyle: { fontWeight: '700' },
      headerBackTitle: 'Retour', contentStyle: { backgroundColor: colors.bg },
    }}>
      <Stack.Screen name="(auth)" options={{ headerShown: false }} />
      <Stack.Screen name="(candidate)" options={{ headerShown: false }} />
      <Stack.Screen name="(employer)" options={{ headerShown: false }} />
      <Stack.Screen name="(member)" options={{ headerShown: false }} />
      <Stack.Screen name="telecharger" options={{ title: "Installer l'application" }} />
      <Stack.Screen name="choose-type" options={{ title: 'Votre type de compte', headerBackVisible: false }} />
      <Stack.Screen name="offer/[slug]" options={{ title: "Offre d'emploi" }} />
      <Stack.Screen name="company/[id]" options={{ title: 'Entreprise' }} />
      <Stack.Screen name="partner/[id]" options={{ title: 'Partenaire' }} />
      <Stack.Screen name="post/[id]" options={{ title: 'Actualité' }} />
      <Stack.Screen name="chat/[id]" options={{ title: 'Conversation' }} />
      <Stack.Screen name="new-message" options={{ title: 'Nouveau message' }} />
      <Stack.Screen name="notifications" options={{ title: 'Notifications' }} />
      <Stack.Screen name="appointments" options={{ title: 'Rendez-vous' }} />
      <Stack.Screen name="discover" options={{ title: 'Actualités et entreprises' }} />
      <Stack.Screen name="orders" options={{ title: 'Mes actualités' }} />
      <Stack.Screen name="order/[id]" options={{ title: 'Mon actualité' }} />
      <Stack.Screen name="publish/[code]" options={{ title: 'Publier' }} />
      <Stack.Screen name="my-application/[id]" options={{ title: 'Ma candidature' }} />
      <Stack.Screen name="application/[id]" options={{ title: 'Candidature reçue' }} />
      <Stack.Screen name="profile-edit" options={{ title: 'Mon profil' }} />
      <Stack.Screen name="company-edit" options={{ title: 'Mon entreprise' }} />
      <Stack.Screen name="documents" options={{ title: 'Mes diplômes' }} />
      <Stack.Screen name="requests" options={{ title: 'Candidatures spontanées' }} />
      <Stack.Screen name="request-edit" options={{ title: 'Candidature spontanée' }} />
      <Stack.Screen name="account" options={{ title: 'Mon compte' }} />
      <Stack.Screen name="support" options={{ title: 'Service client' }} />
      <Stack.Screen name="offers-mine" options={{ title: 'Mes offres' }} />
      <Stack.Screen name="receipt/[id]" options={{ title: 'Reçu de paiement' }} />
    </Stack>
  );
}

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <AuthProvider>
        <StatusBar style="light" />
        <Gate />
      </AuthProvider>
    </SafeAreaProvider>
  );
}
