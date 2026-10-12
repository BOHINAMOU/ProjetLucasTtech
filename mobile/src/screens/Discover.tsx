import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { TextInput, View } from 'react-native';

import { usePaged } from '@/lib/paged';
import { colors, radius, space } from '@/lib/theme';
import type { DirectoryItem, Post } from '@/lib/types';
import { Badge, Card, Chips, Empty, Logo, Muted, Row, T, VerifiedBadge } from '@/ui';
import { PostCard } from '@/ui/cards';
import { PagedList } from '@/ui/PagedList';

const SECTIONS = [
  { value: 'feed', label: 'Actualités' },
  { value: 'orgs', label: 'Entreprises et partenaires' },
];

/** Actualités, et liste unique des entreprises et partenaires (c'est la même chose) : visibles par tous les types de compte. */
export default function Discover() {
  const [section, setSection] = useState('feed');
  const header = <View style={{ paddingTop: space.lg }}><Chips options={SECTIONS} value={section} onChange={setSection} /></View>;
  return <View style={{ flex: 1 }}>{section === 'feed' ? <Feed header={header} /> : <Organizations header={header} />}</View>;
}

function Feed({ header }: { header: React.ReactNode }) {
  const paged = usePaged<Post>('feed');
  return <PagedList paged={paged} header={header} render={(p) => <PostCard post={p} />}
    empty={<Empty icon="newspaper-outline" title="Pas encore d'actualité" text="Les publications des entreprises et de Lantante apparaîtront ici." />} />;
}

function Organizations({ header }: { header: React.ReactNode }) {
  const [text, setText] = useState('');
  const [q, setQ] = useState('');
  useEffect(() => {
    const id = setTimeout(() => setQ(text.trim()), 400);
    return () => clearTimeout(id);
  }, [text]);
  const paged = usePaged<DirectoryItem>('directory', { q });
  const top = (
    <View style={{ gap: space.md }}>
      {header}
      <View style={{ paddingHorizontal: space.lg }}>
        <Row style={{ backgroundColor: colors.surface, borderRadius: radius.pill, paddingHorizontal: 16, borderWidth: 1, borderColor: colors.border }} gap={8}>
          <Ionicons name="search" size={18} color={colors.muted} />
          <TextInput value={text} onChangeText={setText} placeholder="Nom, domaine, ville…" placeholderTextColor="#94a3b8" style={{ flex: 1, paddingVertical: 12, fontSize: 15 }} />
        </Row>
      </View>
    </View>
  );
  return (
    <PagedList paged={paged} header={top}
      render={(o) => (
        <Card onPress={() => router.push(`/${o.kind}/${o.id}` as never)}>
          <Row>
            <Logo uri={o.logo} name={o.name} size={52} />
            <View style={{ flex: 1, gap: 2 }}>
              <Row gap={6}><View style={{ flexShrink: 1 }}><T weight="700" size={16} lines={1}>{o.name}</T></View>{o.verified ? <VerifiedBadge /> : null}</Row>
              <Muted lines={1}>{[o.subtitle, o.city].filter(Boolean).join(' · ')}</Muted>
              {o.is_partner ? <Badge label="Partenaire" tone="gold" icon="ribbon" /> : null}
            </View>
            <Ionicons name="chevron-forward" size={18} color={colors.muted} />
          </Row>
        </Card>
      )}
      empty={<Empty icon="business-outline" title="Aucun résultat" />} />
  );
}
