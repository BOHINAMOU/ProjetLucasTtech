import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { View } from 'react-native';

import { useLoad } from '@/lib/hooks';
import { colors } from '@/lib/theme';
import type { Conversation } from '@/lib/types';
import { Card, Empty, List, Muted, Row, T } from '@/ui';
import { ConversationCard } from '@/ui/cards';

/** Messagerie : conversations directes avec les entreprises / candidats et service client Lantante. */
export default function Messages() {
  const loaded = useLoad<Conversation[]>('conversations');
  const support = (
    <Card onPress={() => router.push('/support' as never)} style={{ backgroundColor: colors.navy }}>
      <Row>
        <View style={{ width: 42, height: 42, borderRadius: 21, backgroundColor: colors.gold, alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name="headset" size={22} color={colors.navy} />
        </View>
        <View style={{ flex: 1 }}>
          <T weight="700" color={colors.white}>Service client Lantante</T>
          <Muted size={13} style={{ color: 'rgba(255,255,255,0.8)' }}>Une question ? Écrivez-nous, nous répondons vite.</Muted>
        </View>
        <Ionicons name="chevron-forward" size={18} color={colors.white} />
      </Row>
    </Card>
  );
  return (
    <List loaded={loaded} data={loaded.data ?? []} header={support} render={(c) => <ConversationCard conv={c} />}
      empty={<Empty icon="chatbubbles-outline" title="Aucune conversation" text="Écrivez à une entreprise depuis sa fiche, ou contactez notre service client." />} />
  );
}
