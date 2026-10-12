import { router, useLocalSearchParams } from 'expo-router';
import { Image, Linking, View } from 'react-native';

import { useAuth } from '@/lib/auth';
import { whatsappLink } from '@/lib/format';
import { useLoad } from '@/lib/hooks';
import { colors, space } from '@/lib/theme';
import type { Partner } from '@/lib/types';
import { Badge, Button, Card, InfoLine, Muted, Screen, Section, T } from '@/ui';
import { PostCard } from '@/ui/cards';

const web = (url: string) => (url.startsWith('http') ? url : `https://${url}`);

export default function PartnerScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { user } = useAuth();
  const loaded = useLoad<Partner>(`partners/${id}`);
  const p = loaded.data;
  const company = p?.company;
  const ownPage = !!company && company.user_id === user?.id;
  const canWriteDirect = !!p?.can_message && !ownPage;

  return (
    <Screen loaded={loaded}>
      {p ? (
        <>
          <Card style={{ alignItems: 'center', gap: space.md }}>
            {p.logo
              ? <Image source={{ uri: p.logo }} style={{ width: '100%', height: 120 }} resizeMode="contain" />
              : null}
            <T size={22} weight="800" style={{ textAlign: 'center' }}>{p.name}</T>
            <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap', justifyContent: 'center' }}>
              <Badge label="Partenaire Lantante" tone="gold" icon="ribbon" />
              {p.domain ? <Badge label={p.domain} tone="grey" /> : null}
            </View>
            <InfoLine icon="flag-outline" text={p.country} />
          </Card>

          {canWriteDirect ? (
            <Button label={`Écrire à ${p.name}`} icon="chatbubble-ellipses"
              onPress={() => router.push(`/new-message?partner_id=${p.id}&to=${encodeURIComponent(p.name)}` as never)} />
          ) : !ownPage && p.whatsapp ? (
            <Button label={`Écrire à ${p.name} sur WhatsApp`} icon="logo-whatsapp" variant="green" onPress={() => Linking.openURL(whatsappLink(p.whatsapp))} />
          ) : null}

          {(p.whatsapp || p.phone || p.email || p.website) ? (
            <Card>
              <T weight="700">Prendre contact</T>
              <InfoLine icon="call-outline" text={p.phone} />
              <InfoLine icon="mail-outline" text={p.email} />
              <InfoLine icon="globe-outline" text={p.website} />
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.sm }}>
                {p.whatsapp ? <Button label="WhatsApp" icon="logo-whatsapp" variant="green" small onPress={() => Linking.openURL(whatsappLink(p.whatsapp))} /> : null}
                {p.phone ? <Button label="Appeler" icon="call" variant="outline" small onPress={() => Linking.openURL(`tel:${p.phone}`)} /> : null}
                {p.email ? <Button label="E-mail" icon="mail" variant="outline" small onPress={() => Linking.openURL(`mailto:${p.email}`)} /> : null}
                {p.website ? <Button label="Site web" icon="globe-outline" variant="outline" small onPress={() => Linking.openURL(web(p.website))} /> : null}
              </View>
            </Card>
          ) : null}

          {company ? <Button label="Voir sa fiche entreprise et ses offres" variant="ghost" onPress={() => router.push(`/company/${company.id}` as never)} /> : null}
          {p.description ? <Section title="Présentation"><T color={colors.ink2}>{p.description}</T></Section> : null}
          {p.achievements ? <Section title="Réalisations"><T color={colors.ink2}>{p.achievements}</T></Section> : null}
          {p.posts?.length ? <Section title="Actualités">{p.posts.map((x) => <PostCard key={x.id} post={x} />)}</Section> : null}
          {!p.description && !p.achievements && !p.posts?.length ? <Muted>Ce partenaire n'a pas encore ajouté de description.</Muted> : null}
        </>
      ) : null}
    </Screen>
  );
}
