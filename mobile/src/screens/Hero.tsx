import { View } from 'react-native';

import { colors, radius, space } from '@/lib/theme';
import { Avatar, Muted, T } from '@/ui';

/** Bandeau d'accueil : photo ou initiales, nom, sous-titre, contenu libre en dessous. */
export function Hero({ name, avatar, subtitle, children }: { name: string; avatar?: string | null; subtitle?: string; children?: React.ReactNode }) {
  return (
    <View style={{ backgroundColor: colors.navy, borderRadius: radius.lg, padding: space.lg, gap: space.md }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.md }}>
        <Avatar uri={avatar} name={name} size={56} />
        <View style={{ flex: 1 }}>
          <Muted size={13} style={{ color: 'rgba(255,255,255,0.75)' }}>Bonjour,</Muted>
          <T size={20} weight="800" color={colors.white} lines={1}>{name}</T>
          {subtitle ? <T size={13} color="rgba(255,255,255,0.8)" lines={2}>{subtitle}</T> : null}
        </View>
      </View>
      {children}
    </View>
  );
}
