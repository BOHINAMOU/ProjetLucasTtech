import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { View } from 'react-native';

import { useLoad } from '@/lib/hooks';
import { colors } from '@/lib/theme';
import type { Plan } from '@/lib/types';
import { Badge, Banner, Button, Card, H2, Muted, Row, Screen, T } from '@/ui';

export const PLAN_ICONS: Record<string, keyof typeof Ionicons.glyphMap> = {
  news: 'newspaper', news_boost: 'rocket', job: 'briefcase', job_boost: 'star', ad: 'megaphone', recruit: 'people',
};

/** Choix du service à publier : les prix sont affichés ici, au moment du choix. */
export default function PublishHub() {
  const loaded = useLoad<{ exempt: boolean; plans: Plan[] }>('publish/plans');
  const notApproved = loaded.error && !loaded.data;
  return (
    <Screen loaded={notApproved ? undefined : loaded}>
      {notApproved ? (
        <Banner tone="gold" icon="hourglass">{loaded.error}</Banner>
      ) : loaded.data ? (
        <>
          <H2>Que voulez-vous publier ?</H2>
          {loaded.data.exempt ? <Banner tone="navy" icon="ribbon">Partenaire Lantante : vos publications sont sans frais (validation toujours effectuée).</Banner> : (
            <Muted size={13}>Le paiement se fait avant la validation. Si Lantante refuse la publication, vous êtes remboursé.</Muted>
          )}
          {loaded.data.plans.map((p) => (
            <Card key={p.code} onPress={() => router.push(`/publish/${p.code}` as never)}>
              <Row style={{ alignItems: 'flex-start' }}>
                <View style={{ width: 44, height: 44, borderRadius: 14, backgroundColor: colors.blueBg, alignItems: 'center', justifyContent: 'center' }}>
                  <Ionicons name={PLAN_ICONS[p.kind] ?? 'cube'} size={22} color={colors.navy} />
                </View>
                <View style={{ flex: 1, gap: 4 }}>
                  <T weight="700" size={16}>{p.name}</T>
                  <Muted size={13}>{p.advantages.length > 1 ? p.advantages.map((l) => `✓ ${l}`).join('\n') : p.description}</Muted>
                  <Row>
                    <Badge label={loaded.data!.exempt ? 'Sans frais' : p.price_label} tone={loaded.data!.exempt ? 'green' : 'gold'} />
                    {p.duration_days ? <Muted size={12}>{p.duration_days} jours</Muted> : null}
                  </Row>
                </View>
              </Row>
            </Card>
          ))}
          <Button label="Mes publications" variant="outline" icon="receipt-outline" onPress={() => router.push('/orders' as never)} />
        </>
      ) : null}
    </Screen>
  );
}
