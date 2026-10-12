import { Ionicons } from '@expo/vector-icons';
import { Tabs, router } from 'expo-router';
import { Pressable, Text, View } from 'react-native';

import { Avatar } from '@/ui';

import { useAuth } from '@/lib/auth';
import { useLoad } from '@/lib/hooks';
import { colors } from '@/lib/theme';
import type { User } from '@/lib/types';

type IconName = keyof typeof Ionicons.glyphMap;
export interface TabDef { name: string; title: string; icon: IconName; iconOn: IconName; badge?: 'messages' | 'applications'; greeting?: boolean }

/** Titre de l'onglet d'accueil : « Accueil » puis, juste à côté, la photo et « Bonjour, prénom ». */
function Greeting({ title }: { title: string }) {
  const { user } = useAuth();
  const first = user?.first_name || user?.name || '';
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
      <Text style={{ color: colors.white, fontSize: 17, fontWeight: '700' }}>{title}</Text>
      <View style={{ width: 1, height: 22, backgroundColor: 'rgba(255,255,255,0.35)' }} />
      <Avatar uri={user?.avatar} name={user?.name || ''} size={28} />
      <Text numberOfLines={1} style={{ color: 'rgba(255,255,255,0.9)', fontSize: 13, fontWeight: '600', maxWidth: 140 }}>Bonjour, {first}</Text>
    </View>
  );
}

function Bell() {
  const { user } = useAuth();
  const me = useLoad<User>('me');
  const count = me.data?.unread_notifications ?? user?.unread_notifications ?? 0;
  return (
    <Pressable onPress={() => router.push('/notifications' as never)} hitSlop={10} style={{ marginRight: 16 }}>
      <Ionicons name="notifications-outline" size={24} color={colors.white} />
      {count > 0 ? (
        <View style={{ position: 'absolute', top: -5, right: -6, minWidth: 16, height: 16, borderRadius: 8, backgroundColor: colors.gold, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 3 }}>
          <Text style={{ color: colors.ink, fontSize: 10, fontWeight: '800' }}>{count > 9 ? '9+' : count}</Text>
        </View>
      ) : null}
    </Pressable>
  );
}

/** Barre d'onglets commune aux trois espaces ; les pastilles viennent des compteurs du compte. */
export function TabsLayout({ tabs }: { tabs: TabDef[] }) {
  const me = useLoad<User>('me');
  const counts = { messages: me.data?.unread_messages ?? 0, applications: me.data?.new_applications ?? 0 };
  return (
    <Tabs screenOptions={{
      headerStyle: { backgroundColor: colors.navy }, headerTintColor: colors.white, headerTitleStyle: { fontWeight: '700' },
      headerRight: () => <Bell />,
      tabBarActiveTintColor: colors.navy, tabBarInactiveTintColor: colors.muted,
      tabBarStyle: { backgroundColor: colors.surface, borderTopColor: colors.border },
      tabBarLabelStyle: { fontSize: 11, fontWeight: '600' },
    }}>
      {tabs.map((t) => {
        const badge = t.badge ? counts[t.badge] : 0;
        return (
          <Tabs.Screen key={t.name} name={t.name} options={{
            title: t.title,
            ...(t.greeting ? { headerTitle: () => <Greeting title={t.title} />, headerTitleAlign: 'left' as const } : {}),
            tabBarBadge: badge > 0 ? badge : undefined,
            tabBarBadgeStyle: { backgroundColor: colors.warn, color: colors.white },
            tabBarIcon: ({ focused, color, size }) => <Ionicons name={focused ? t.iconOn : t.icon} size={size} color={color} />,
          }} />
        );
      })}
    </Tabs>
  );
}
