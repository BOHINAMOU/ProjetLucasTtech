import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';

import { post } from '@/lib/api';
import { fieldErrors, messageOf } from '@/lib/hooks';
import type { Conversation } from '@/lib/types';
import { Banner, Button, Input, Screen, T, notice } from '@/ui';

/** Premier message à une entreprise (ou à un candidat qui a postulé) : ouvre ensuite la conversation. */
export default function NewMessage() {
  const { user_id, to } = useLocalSearchParams<{ user_id: string; to?: string }>();
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const send = async () => {
    setBusy(true);
    setErrors({});
    try {
      const conv = await post<Conversation>('conversations', { user_id: Number(user_id), subject, body });
      router.replace(`/chat/${conv.id}` as never);
    } catch (e) {
      setErrors(fieldErrors(e));
      notice('Message non envoyé', messageOf(e));
      setBusy(false);
    }
  };

  return (
    <Screen>
      {to ? <T size={16} weight="700">Écrire à {to}</T> : null}
      <Banner icon="information-circle">Soyez clair et courtois : votre message sera lu par la personne concernée.</Banner>
      <Input label="Objet (facultatif)" value={subject} onChangeText={setSubject} error={errors.subject} maxLength={160} />
      <Input label="Message" value={body} onChangeText={setBody} multiline error={errors.body} placeholder="Votre message…" />
      <Button label="Envoyer" icon="send" onPress={send} loading={busy} disabled={!body.trim()} />
    </Screen>
  );
}
