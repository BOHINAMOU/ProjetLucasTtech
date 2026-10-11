import { router, useLocalSearchParams } from 'expo-router';
import { Linking, View } from 'react-native';

import { useAuth } from '@/lib/auth';
import { whatsappLink } from '@/lib/format';
import { useLoad } from '@/lib/hooks';
import { colors } from '@/lib/theme';
import type { Company } from '@/lib/types';
import { Badge, Button, Card, H2, InfoLine, Logo, Muted, Row, Screen, Section, T, VerifiedBadge } from '@/ui';
import { OfferCard, PostCard } from '@/ui/cards';

export default function CompanyScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { user } = useAuth();
  const loaded = useLoad<Company>(`companies/${id}`);
  const c = loaded.data;
  return (
    <Screen loaded={loaded}>
      {c ? (
        <>
          <Card>
            <Row>
              <Logo uri={c.logo} name={c.name} size={64} />
              <View style={{ flex: 1, gap: 4 }}>
                <Row gap={6}><View style={{ flexShrink: 1 }}><T size={20} weight="800">{c.name}</T></View>{c.verified ? <VerifiedBadge /> : null}</Row>
                <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
                  {c.sector_label ? <Badge label={c.sector_label} tone="grey" /> : null}
                  {c.verified ? <Badge label="Entreprise de confiance" tone="navy" icon="shield-checkmark" /> : null}
                  {c.is_partner ? <Badge label="Partenaire" tone="gold" icon="ribbon" /> : null}
                </View>
              </View>
            </Row>
            <InfoLine icon="location-outline" text={c.city} />
            <InfoLine icon="people-outline" text={c.employees_count ? `${c.employees_count} employé(s)` : ''} />
            <InfoLine icon="globe-outline" text={c.website} />
          </Card>

          {c.can_message && c.user_id !== user?.id ? (
            <Button label="Envoyer un message" icon="chatbubble-ellipses" onPress={() => router.push(`/new-message?user_id=${c.user_id}&to=${encodeURIComponent(c.name)}` as never)} />
          ) : null}
          <Row>
            {c.whatsapp ? <View style={{ flex: 1 }}><Button label="WhatsApp" icon="logo-whatsapp" variant="green" small onPress={() => Linking.openURL(whatsappLink(c.whatsapp!))} /></View> : null}
            {c.website ? <View style={{ flex: 1 }}><Button label="Site web" icon="globe-outline" variant="outline" small onPress={() => Linking.openURL(c.website!.startsWith('http') ? c.website! : `https://${c.website}`)} /></View> : null}
          </Row>

          {c.description ? <Section title="À propos"><T color={colors.ink2}>{c.description}</T></Section> : null}
          {c.products?.length ? <Section title="Produits et services">{c.products.map((p) => <Muted key={p} size={14}>• {p}</Muted>)}</Section> : null}
          {c.offers?.length ? <Section title="Offres en cours">{c.offers.map((o) => <OfferCard key={o.id} offer={o} />)}</Section> : null}
          {c.posts?.length ? <Section title="Actualités">{c.posts.map((p) => <PostCard key={p.id} post={p} />)}</Section> : null}
          {!c.offers?.length && !c.posts?.length && !c.description ? <H2>Cette entreprise n'a pas encore publié.</H2> : null}
        </>
      ) : null}
    </Screen>
  );
}
