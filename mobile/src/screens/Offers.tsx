import { Ionicons } from '@expo/vector-icons';
import { useEffect, useState } from 'react';
import { TextInput, View } from 'react-native';

import { useAuth } from '@/lib/auth';
import { usePaged } from '@/lib/paged';
import { colors, radius, space } from '@/lib/theme';
import type { Offer } from '@/lib/types';
import { Chips, Empty, Row } from '@/ui';
import { OfferCard } from '@/ui/cards';
import { PagedList } from '@/ui/PagedList';

import HighlightsBanner from './HighlightsBanner';

/** Offres d'emploi ouvertes : recherche par mots, filtre par domaine. */
export default function Offers() {
  const { config } = useAuth();
  const [text, setText] = useState('');
  const [q, setQ] = useState('');
  const [domain, setDomain] = useState('');

  useEffect(() => {
    const id = setTimeout(() => setQ(text.trim()), 400); // on attend la fin de la frappe
    return () => clearTimeout(id);
  }, [text]);

  const paged = usePaged<Offer>('offers', { q, domain });
  const domains = [{ value: '', label: 'Tous' }, ...(config?.domains ?? [])];

  const header = (
    <View style={{ gap: space.md, paddingTop: space.lg }}>
      <View style={{ paddingHorizontal: space.lg }}><HighlightsBanner /></View>
      <View style={{ paddingHorizontal: space.lg }}>
        <Row style={{ backgroundColor: colors.surface, borderRadius: radius.pill, paddingHorizontal: 16, borderWidth: 1, borderColor: colors.border }} gap={8}>
          <Ionicons name="search" size={18} color={colors.muted} />
          <TextInput value={text} onChangeText={setText} placeholder="Poste, compétence, entreprise…" placeholderTextColor="#94a3b8"
            style={{ flex: 1, paddingVertical: 12, fontSize: 15 }} returnKeyType="search" />
        </Row>
      </View>
      <Chips options={domains} value={domain} onChange={setDomain} />
    </View>
  );

  return (
    <PagedList paged={paged} header={header} render={(o) => <OfferCard offer={o} />}
      empty={<Empty icon="briefcase-outline" title="Aucune offre pour le moment"
        text="Modifiez votre recherche ou revenez bientôt : de nouvelles offres sont publiées régulièrement." />} />
  );
}
