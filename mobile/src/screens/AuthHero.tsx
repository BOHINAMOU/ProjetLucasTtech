import { Image, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors, space } from '@/lib/theme';
import { T } from '@/ui';

export function AuthHero({ title, subtitle }: { title: string; subtitle: string }) {
  const insets = useSafeAreaInsets();
  return (
    <View style={{ backgroundColor: colors.navy, paddingTop: insets.top + space.xl, paddingBottom: 36, paddingHorizontal: space.xl, gap: 6,
      borderBottomLeftRadius: 28, borderBottomRightRadius: 28 }}>
      <Image source={require('../../assets/images/icon.png')} style={{ width: 84, height: 84, borderRadius: 18, backgroundColor: colors.white, marginBottom: 10 }} resizeMode="contain" />
      <T size={26} weight="800" color={colors.white}>{title}</T>
      <T size={14} color="rgba(255,255,255,0.8)">{subtitle}</T>
    </View>
  );
}
