import { router } from 'expo-router';
import { Platform } from 'react-native';

import { useAuth } from '@/lib/auth';
import { useLoad } from '@/lib/hooks';
import type { User } from '@/lib/types';
import { Button, Menu, Screen } from '@/ui';

export default function EmployerMore() {
  const { logout } = useAuth();
  const me = useLoad<User>('me');
  return (
    <Screen>
      <Menu items={[
        { icon: 'business-outline', label: 'Mon entreprise', onPress: () => router.push('/company-edit' as never) },
        { icon: 'briefcase-outline', label: 'Mes offres', onPress: () => router.push('/offers-mine' as never) },
        { icon: 'receipt-outline', label: 'Mes actualités et paiements', onPress: () => router.push('/orders' as never) },
        { icon: 'calendar-outline', label: 'Rendez-vous et entretiens', onPress: () => router.push('/appointments' as never) },
        { icon: 'newspaper-outline', label: 'Actualités, entreprises et partenaires', onPress: () => router.push('/discover' as never) },
        { icon: 'notifications-outline', label: 'Notifications', badge: me.data?.unread_notifications, onPress: () => router.push('/notifications' as never) },
        ...(Platform.OS === 'web' ? [{ icon: 'download-outline' as const, label: "Installer l'application", onPress: () => router.push('/telecharger' as never) }] : []),
        { icon: 'headset-outline', label: 'Service client', onPress: () => router.push('/support' as never) },
        { icon: 'settings-outline', label: 'Mon compte', onPress: () => router.push('/account' as never) },
      ]} />
      <Button label="Se déconnecter" variant="ghost" icon="log-out-outline" onPress={logout} />
    </Screen>
  );
}
