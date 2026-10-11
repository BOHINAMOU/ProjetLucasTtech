import { useState } from 'react';
import { View } from 'react-native';

import { useLoad } from '@/lib/hooks';
import { usePaged } from '@/lib/paged';
import { space } from '@/lib/theme';
import type { Company, Page, Partner, Post } from '@/lib/types';
import { Chips, Empty, List } from '@/ui';
import { CompanyCard, PartnerCard, PostCard } from '@/ui/cards';
import { PagedList } from '@/ui/PagedList';

const SECTIONS = [
  { value: 'feed', label: 'Actualités' },
  { value: 'companies', label: 'Entreprises' },
  { value: 'partners', label: 'Partenaires' },
];

/** Actualités, entreprises acceptées et partenaires : visibles par tous les types de compte. */
export default function Discover() {
  const [section, setSection] = useState('feed');
  const header = <View style={{ paddingTop: space.lg }}><Chips options={SECTIONS} value={section} onChange={setSection} /></View>;
  return (
    <View style={{ flex: 1 }}>
      {section === 'feed' ? <Feed header={header} /> : section === 'companies' ? <Companies header={header} /> : <Partners header={header} />}
    </View>
  );
}

function Feed({ header }: { header: React.ReactNode }) {
  const paged = usePaged<Post>('feed');
  return <PagedList paged={paged} header={header} render={(p) => <PostCard post={p} />}
    empty={<Empty icon="newspaper-outline" title="Pas encore d'actualité" text="Les publications des entreprises et de Lantante apparaîtront ici." />} />;
}

function Companies({ header }: { header: React.ReactNode }) {
  const paged = usePaged<Company>('companies');
  return <PagedList paged={paged} header={header} render={(c) => <CompanyCard company={c} />}
    empty={<Empty icon="business-outline" title="Aucune entreprise pour le moment" />} />;
}

function Partners({ header }: { header: React.ReactNode }) {
  const loaded = useLoad<Page<Partner>>('partners');
  return <List loaded={loaded} data={loaded.data?.results ?? []} header={header} render={(p) => <PartnerCard partner={p} />}
    empty={<Empty icon="ribbon-outline" title="Aucun partenaire pour le moment" />} />;
}
