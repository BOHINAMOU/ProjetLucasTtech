import { Ionicons } from '@expo/vector-icons';
import { Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { FlatList, KeyboardAvoidingView, Platform, Pressable, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { post } from '@/lib/api';
import { formatDate, formatTime } from '@/lib/format';
import { messageOf, useLoad } from '@/lib/hooks';
import { colors, radius, space } from '@/lib/theme';
import type { Conversation, Message } from '@/lib/types';
import { Badge, ErrorBox, Loader, Muted, T, notice } from '@/ui';

export default function Chat() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const loaded = useLoad<Conversation>(`conversations/${id}`);
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const list = useRef<FlatList<Message>>(null);
  const insets = useSafeAreaInsets();

  useEffect(() => { if (loaded.data?.messages) setMessages(loaded.data.messages); }, [loaded.data]);

  // Nouveaux messages de l'autre personne : on actualise toutes les 8 secondes tant que l'écran est ouvert.
  useEffect(() => {
    const timer = setInterval(() => { loaded.refresh(); }, 8000);
    return () => clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const send = async () => {
    const body = text.trim();
    if (!body || busy) return;
    setBusy(true);
    try {
      const conv = await post<Conversation>(`conversations/${id}/messages`, { body });
      setMessages(conv.messages ?? []);
      setText('');
      setTimeout(() => list.current?.scrollToEnd({ animated: true }), 100);
    } catch (e) {
      notice('Message non envoyé', messageOf(e));
    } finally {
      setBusy(false);
    }
  };

  if (loaded.loading && !loaded.data) return <Loader />;
  if (loaded.error && !loaded.data) return <ErrorBox message={loaded.error} onRetry={loaded.reload} />;

  return (
    <KeyboardAvoidingView style={{ flex: 1, backgroundColor: colors.bg }} behavior={Platform.OS === 'ios' ? 'padding' : undefined} keyboardVerticalOffset={90}>
      <Stack.Screen options={{ title: loaded.data?.title || 'Conversation' }} />
      <FlatList
        ref={list}
        data={messages}
        keyExtractor={(m) => String(m.id)}
        contentContainerStyle={{ padding: space.lg, gap: 8 }}
        onContentSizeChange={() => list.current?.scrollToEnd({ animated: false })}
        ListHeaderComponent={loaded.data?.kind === 'support' ? (
          <View style={{ alignItems: 'center', marginBottom: 8 }}><Badge label="Service client Lantante" tone="green" icon="headset" /></View>
        ) : null}
        renderItem={({ item, index }) => {
          const showDay = index === 0 || formatDate(messages[index - 1].created_at) !== formatDate(item.created_at);
          return (
            <View>
              {showDay ? <Muted size={12} style={{ textAlign: 'center', marginVertical: 8 }}>{formatDate(item.created_at)}</Muted> : null}
              <View style={{ alignSelf: item.mine ? 'flex-end' : 'flex-start', maxWidth: '82%', gap: 2 }}>
                {!item.mine ? <Muted size={11}>{item.author}{item.is_automatic ? ' · message automatique' : ''}</Muted> : null}
                <View style={{ backgroundColor: item.mine ? colors.navy : colors.surface, borderRadius: radius.md, padding: 12,
                  borderBottomRightRadius: item.mine ? 4 : radius.md, borderBottomLeftRadius: item.mine ? radius.md : 4,
                  borderWidth: item.mine ? 0 : 1, borderColor: colors.border }}>
                  <T color={item.mine ? colors.white : colors.ink}>{item.body}</T>
                </View>
                <Muted size={11} style={{ alignSelf: item.mine ? 'flex-end' : 'flex-start' }}>{formatTime(item.created_at)}</Muted>
              </View>
            </View>
          );
        }}
      />
      <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 8, padding: space.md, paddingBottom: Math.max(insets.bottom, space.md),
        backgroundColor: colors.surface, borderTopWidth: 1, borderTopColor: colors.border }}>
        <TextInput value={text} onChangeText={setText} placeholder="Votre message…" placeholderTextColor="#94a3b8" multiline
          style={{ flex: 1, maxHeight: 120, backgroundColor: colors.surface2, borderRadius: 20, paddingHorizontal: 14, paddingVertical: 10, fontSize: 15 }} />
        <Pressable onPress={send} disabled={busy || !text.trim()}
          style={{ width: 44, height: 44, borderRadius: 22, backgroundColor: text.trim() ? colors.navy : colors.border, alignItems: 'center', justifyContent: 'center' }}>
          <Ionicons name="send" size={20} color={colors.white} />
        </Pressable>
      </View>
    </KeyboardAvoidingView>
  );
}
