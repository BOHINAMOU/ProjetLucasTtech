import { Ionicons } from '@expo/vector-icons';
import { View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors, space } from '@/lib/theme';
import { T } from '@/ui';

export function AuthHero({ title, subtitle }: { title: string; subtitle: string }) {
  const insets = useSafeAreaInsets();
  return (
    <View style={{ backgroundColor: colors.navy, paddingTop: insets.top + space.xl, paddingBottom: 36, paddingHorizontal: space.xl, gap: 6,
      borderBottomLeftRadius: 28, borderBottomRightRadius: 28 }}>
      <View style={{ width: 52, height: 52, borderRadius: 16, backgroundColor: colors.gold, alignItems: 'center', justifyContent: 'center', marginBottom: 10 }}>
        <Ionicons name="briefcase" size={26} color={colors.navy} />
      </View>
      <T size={26} weight="800" color={colors.white}>{title}</T>
      <T size={14} color="rgba(255,255,255,0.8)">{subtitle}</T>
    </View>
  );
}
