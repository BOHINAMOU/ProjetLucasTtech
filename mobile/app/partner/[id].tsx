import { router, useLocalSearchParams } from 'expo-router';
import { Linking, View } from 'react-native';

import { whatsappLink } from '@/lib/format';
import { useLoad } from '@/lib/hooks';
import { colors } from '@/lib/theme';
import type { Partner } from '@/lib/types';
import { Badge, Button, Card, InfoLine, Logo, Row, Screen, Section, T } from '@/ui';
import { PostCard } from '@/ui/cards';

export default function PartnerScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const loaded = useLoad<Partner>(`partners/${id}`);
  const p = loaded.data;
  return (
    <Screen loaded={loaded}>
      {p ? (
        <>
          <Card>
            <Row>
              <Logo uri={p.logo} name={p.name} size={64} />
              <View style={{ flex: 1, gap: 4 }}>
                <T size={20} weight="800">{p.name}</T>
                <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap' }}>
                  <Badge label="Partenaire Lantante" tone="gold" icon="ribbon" />
                  {p.domain ? <Badge label={p.domain} tone="grey" /> : null}
                </View>
              </View>
            </Row>
            <InfoLine icon="flag-outline" text={p.country} />
            <InfoLine icon="call-outline" text={p.phone} />
            <InfoLine icon="mail-outline" text={p.email} />
            <InfoLine icon="globe-outline" text={p.website} />
          </Card>
          <Row>
            {p.whatsapp ? <View style={{ flex: 1 }}><Button label="WhatsApp" icon="logo-whatsapp" variant="green" small onPress={() => Linking.openURL(whatsappLink(p.whatsapp))} /></View> : null}
            {p.website ? <View style={{ flex: 1 }}><Button label="Site web" icon="globe-outline" variant="outline" small onPress={() => Linking.openURL(p.website.startsWith('http') ? p.website : `https://${p.website}`)} /></View> : null}
          </Row>
          {p.company ? <Button label="Voir sa fiche entreprise" variant="ghost" onPress={() => router.push(`/company/${p.company!.id}` as never)} /> : null}
          {p.description ? <Section title="Présentation"><T color={colors.ink2}>{p.description}</T></Section> : null}
          {p.achievements ? <Section title="Réalisations"><T color={colors.ink2}>{p.achievements}</T></Section> : null}
          {p.posts?.length ? <Section title="Actualités">{p.posts.map((x) => <PostCard key={x.id} post={x} />)}</Section> : null}
        </>
      ) : null}
    </Screen>
  );
}
