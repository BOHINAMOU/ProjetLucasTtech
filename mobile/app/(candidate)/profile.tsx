import { router } from 'expo-router';
import { View } from 'react-native';

import { useAuth } from '@/lib/auth';
import { useLoad } from '@/lib/hooks';
import { colors, radius, space } from '@/lib/theme';
import type { Candidate, User } from '@/lib/types';
import { Avatar, Badge, Banner, Button, Muted, Menu, Progress, Screen, T } from '@/ui';

type Me = Candidate & { exists: boolean; completion?: number };

export default function CandidateProfileTab() {
  const { user, logout } = useAuth();
  const profile = useLoad<Me>('candidate/profile');
  const me = useLoad<User>('me');
  const p = profile.data;
  const counts = me.data;

  return (
    <Screen loaded={profile}>
      <View style={{ backgroundColor: colors.navy, borderRadius: radius.lg, padding: space.lg, gap: space.md }}>
        <View style={{ flexDirection: 'row', gap: space.md, alignItems: 'center' }}>
          <Avatar uri={user?.avatar} name={user?.name || ''} size={60} />
          <View style={{ flex: 1 }}>
            <T size={18} weight="800" color={colors.white} lines={1}>{user?.name}</T>
            <T size={13} color="rgba(255,255,255,0.8)" lines={1}>{p?.exists ? p.headline : user?.email}</T>
          </View>
        </View>
        {p?.exists ? (
          <View style={{ gap: 6 }}>
            <T size={12} color="rgba(255,255,255,0.85)">Profil complété à {p.completion ?? 0} %</T>
            <Progress percent={p.completion ?? 0} />
          </View>
        ) : null}
      </View>

      {!p?.exists ? (
        <Banner tone="gold" icon="alert-circle">Complétez votre profil (métier, compétences, CV) pour pouvoir postuler.</Banner>
      ) : !p.has_cv ? (
        <Banner tone="warn" icon="document-attach">Ajoutez votre CV (PDF) : il est envoyé avec chaque candidature.</Banner>
      ) : null}
      {p?.exists && !p.cover_letter ? <Muted size={13}>Astuce : enregistrez une lettre de motivation par défaut, elle sera proposée à chaque candidature.</Muted> : null}
      <Button label={p?.exists ? 'Modifier mon profil' : 'Créer mon profil'} icon="create-outline" onPress={() => router.push('/profile-edit' as never)} />
      {p?.exists ? <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap' }}>
        {p.has_cv ? <Badge label="CV ajouté" tone="green" icon="checkmark" /> : null}
        {p.documents?.length ? <Badge label={`${p.documents.length} diplôme(s)`} tone="navy" /> : null}
        {p.available ? <Badge label="Disponible" tone="green" /> : <Badge label="Non disponible" tone="grey" />}
      </View> : null}

      <Menu items={[
        { icon: 'school-outline', label: 'Mes diplômes et documents', onPress: () => router.push('/documents' as never) },
        { icon: 'rocket-outline', label: 'Candidatures spontanées', onPress: () => router.push('/requests' as never) },
        { icon: 'calendar-outline', label: 'Mes rendez-vous', onPress: () => router.push('/appointments' as never) },
        { icon: 'notifications-outline', label: 'Notifications', badge: counts?.unread_notifications, onPress: () => router.push('/notifications' as never) },
        { icon: 'business-outline', label: 'Entreprises et partenaires', onPress: () => router.push('/discover' as never) },
        { icon: 'headset-outline', label: 'Service client', onPress: () => router.push('/support' as never) },
        { icon: 'settings-outline', label: 'Mon compte', onPress: () => router.push('/account' as never) },
      ]} />
      <Button label="Se déconnecter" variant="ghost" icon="log-out-outline" onPress={logout} />
    </Screen>
  );
}
