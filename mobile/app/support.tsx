import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';

import { post } from '@/lib/api';
import { fieldErrors, messageOf, useLoad } from '@/lib/hooks';
import type { Conversation } from '@/lib/types';
import { Banner, Button, Card, H2, Input, Muted, Screen, notice } from '@/ui';

/** Service client : une seule conversation ouverte à la fois, on la reprend si elle existe. */
export default function Support() {
  const loaded = useLoad<Conversation[]>('conversations');
  const open = loaded.data?.find((c) => c.kind === 'support' && c.status !== 'closed');
  const params = useLocalSearchParams<{ subject?: string }>();
  const [subject, setSubject] = useState(params.subject ?? '');
  const [body, setBody] = useState('');
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const send = async () => {
    setBusy(true);
    setErrors({});
    try {
      const conv = await post<Conversation>('conversations', { support: true, subject: subject || 'Demande au service client', body });
      router.replace(`/chat/${conv.id}` as never);
    } catch (e) {
      setErrors(fieldErrors(e));
      notice('Message non envoyé', messageOf(e));
      setBusy(false);
    }
  };

  return (
    <Screen loaded={loaded}>
      <Banner icon="headset">Notre équipe répond à vos questions sur les offres, les publications et les paiements.</Banner>
      {open ? (
        <Card>
          <H2>Conversation en cours</H2>
          <Muted>Vous avez déjà une conversation ouverte avec le service client.</Muted>
          <Button label="Reprendre la conversation" icon="chatbubbles" onPress={() => router.replace(`/chat/${open.id}` as never)} />
        </Card>
      ) : null}
      <Card>
        <H2>{open ? 'Ajouter un message' : 'Nouvelle demande'}</H2>
        {!open ? <Input label="Sujet" value={subject} onChangeText={setSubject} placeholder="Ex : paiement, publication…" maxLength={160} error={errors.subject} /> : null}
        <Input label="Votre message" value={body} onChangeText={setBody} multiline error={errors.body} />
        <Button label="Envoyer" icon="send" onPress={send} loading={busy} disabled={!body.trim()} />
      </Card>
    </Screen>
  );
}
