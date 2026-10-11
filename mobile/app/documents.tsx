import { Ionicons } from '@expo/vector-icons';
import { useState } from 'react';
import { Pressable, View } from 'react-native';

import { api, post } from '@/lib/api';
import { formatDate } from '@/lib/format';
import { openPrivateFile, pickDocument, type Picked } from '@/lib/files';
import { fieldErrors, messageOf, useLoad } from '@/lib/hooks';
import { colors } from '@/lib/theme';
import type { Document } from '@/lib/types';
import { useAuth } from '@/lib/auth';
import { Button, Card, Empty, FilePicker, Input, List, Muted, Row, Section, Select, T, confirm, notice } from '@/ui';

export default function Documents() {
  const { config } = useAuth();
  const loaded = useLoad<Document[]>('candidate/documents');
  const [kind, setKind] = useState('diplome');
  const [title, setTitle] = useState('');
  const [file, setFile] = useState<Picked | null>(null);
  const [busy, setBusy] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const add = async () => {
    setBusy(true);
    setErrors({});
    try {
      await post('candidate/documents', { kind, title, file });
      setTitle('');
      setFile(null);
      await loaded.reload();
    } catch (e) {
      setErrors(fieldErrors(e));
      notice('Ajout impossible', messageOf(e));
    } finally {
      setBusy(false);
    }
  };

  const remove = (d: Document) => confirm('Supprimer ce document ?', d.title, 'Supprimer', async () => {
    try {
      await api('DELETE', `candidate/documents/${d.id}`);
      await loaded.reload();
    } catch (e) {
      notice('Suppression impossible', messageOf(e));
    }
  }, true);

  const open = async (d: Document) => {
    try {
      await openPrivateFile(d.url, d.title);
    } catch (e) {
      notice('Ouverture impossible', messageOf(e));
    }
  };

  const form = (
    <Section title="Ajouter un document">
      <Card>
        <Select label="Type" value={kind} options={config?.document_kinds ?? []} onChange={setKind} error={errors.kind} />
        <Input label="Intitulé" value={title} onChangeText={setTitle} placeholder="Licence en gestion, 2023" error={errors.title} />
        <FilePicker label="Fichier" fileName={file?.name} error={errors.file} hint="PDF, JPG ou PNG, 5 Mo maximum."
          onPress={async () => setFile((await pickDocument(['application/pdf', 'image/jpeg', 'image/png'])) ?? file)} />
        <Button label="Ajouter" icon="add" onPress={add} loading={busy} disabled={!file || !title.trim()} />
      </Card>
    </Section>
  );

  return (
    <List loaded={loaded} data={loaded.data ?? []} header={form}
      render={(d) => (
        <Card>
          <Row>
            <Ionicons name="document-text" size={26} color={colors.navy} />
            <Pressable style={{ flex: 1 }} onPress={() => open(d)}>
              <T weight="700" lines={2}>{d.title}</T>
              <Muted size={12}>{d.kind_label} · {formatDate(d.created_at)}</Muted>
            </Pressable>
            <Pressable onPress={() => remove(d)} hitSlop={10}><Ionicons name="trash-outline" size={22} color={colors.danger} /></Pressable>
          </Row>
        </Card>
      )}
      empty={<View><Empty icon="school-outline" title="Aucun document" text="Ajoutez vos diplômes et attestations : ils sont joints à vos candidatures." /></View>} />
  );
}
