import { Ionicons } from '@expo/vector-icons';
import { Pressable, View } from 'react-native';

import { colors, radius, space } from '@/lib/theme';
import { Muted, T } from '@/ui';

export const ACCOUNT_TYPES = [
  { value: 'candidate', icon: 'search', title: "Je cherche un emploi", text: "Consultez les offres, postulez en un clic, suivez vos candidatures et échangez avec les entreprises." },
  { value: 'employer', icon: 'business', title: "Je représente une entreprise", text: "Publiez vos offres, recevez les candidatures directement et organisez vos entretiens." },
  { value: 'member', icon: 'megaphone', title: "Je suis un particulier", text: "Publiez une actualité ou une annonce, payez les frais et c'est tout." },
] as const;

export function AccountTypeCards({ value, onChange }: { value: string; onChange: (v: string) => void }) {
  return (
    <View style={{ gap: space.md }}>
      {ACCOUNT_TYPES.map((t) => {
        const on = value === t.value;
        return (
          <Pressable key={t.value} onPress={() => onChange(t.value)}
            style={{ flexDirection: 'row', gap: space.md, padding: space.lg, borderRadius: radius.md, backgroundColor: on ? colors.blueBg : colors.surface,
              borderWidth: 2, borderColor: on ? colors.navy : colors.border }}>
            <View style={{ width: 44, height: 44, borderRadius: 14, backgroundColor: on ? colors.navy : colors.surface2, alignItems: 'center', justifyContent: 'center' }}>
              <Ionicons name={t.icon} size={22} color={on ? colors.white : colors.navy} />
            </View>
            <View style={{ flex: 1, gap: 2 }}>
              <T weight="700" size={16}>{t.title}</T>
              <Muted size={13}>{t.text}</Muted>
            </View>
            {on ? <Ionicons name="checkmark-circle" size={22} color={colors.navy} /> : null}
          </Pressable>
        );
      })}
    </View>
  );
}
