import { Ionicons } from '@expo/vector-icons';
import { useEffect } from 'react';
import { View } from 'react-native';

import { post } from '@/lib/api';
import { timeAgo } from '@/lib/format';
import { usePaged } from '@/lib/paged';
import { openFromUrl } from '@/lib/push';
import { colors } from '@/lib/theme';
import type { Notice } from '@/lib/types';
import { Card, Empty, Muted, Row, T } from '@/ui';
import { PagedList } from '@/ui/PagedList';

export default function Notifications() {
  const paged = usePaged<Notice>('notifications');

  // On marque tout comme lu après l'affichage de la liste (les pastilles se mettent à jour au retour).
  useEffect(() => {
    const id = setTimeout(() => { post('notifications').catch(() => {}); }, 1500);
    return () => clearTimeout(id);
  }, []);

  return (
    <PagedList paged={paged}
      render={(n) => (
        <Card onPress={() => openFromUrl(n.url)} style={!n.is_read ? { borderColor: colors.gold, borderWidth: 1.5 } : undefined}>
          <Row style={{ alignItems: 'flex-start' }}>
            <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: n.is_read ? colors.surface2 : colors.goldBg, alignItems: 'center', justifyContent: 'center' }}>
              <Ionicons name="notifications" size={18} color={n.is_read ? colors.muted : '#8a6d1d'} />
            </View>
            <View style={{ flex: 1, gap: 2 }}>
              <T weight={n.is_read ? '400' : '700'}>{n.text}</T>
              <Muted size={12}>{timeAgo(n.created_at)}</Muted>
            </View>
          </Row>
        </Card>
      )}
      empty={<Empty icon="notifications-off-outline" title="Aucune notification" text="Vous serez prévenu ici de l'avancée de vos candidatures et publications." />} />
  );
}
