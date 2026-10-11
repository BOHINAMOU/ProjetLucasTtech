import { ActivityIndicator, FlatList, RefreshControl, View } from 'react-native';
import type { ReactNode } from 'react';

import type { Paged } from '@/lib/paged';
import { colors, space } from '@/lib/theme';

import { ErrorBox, Loader } from './index';

export function PagedList<I>({ paged, render, empty, header }: {
  paged: Paged<I>; render: (item: I) => ReactNode; empty: ReactNode; header?: ReactNode;
}) {
  if (paged.loading && !paged.items.length) return <View style={{ flex: 1 }}>{header}<Loader /></View>;
  if (paged.error && !paged.items.length) return <View style={{ flex: 1 }}>{header}<ErrorBox message={paged.error} onRetry={paged.reload} /></View>;
  return (
    <FlatList
      data={paged.items}
      keyExtractor={(_, i) => String(i)}
      renderItem={({ item }) => <View style={{ paddingHorizontal: space.lg, paddingBottom: space.md }}>{render(item)}</View>}
      ListHeaderComponent={header ? <View style={{ paddingBottom: space.md }}>{header}</View> : null}
      ListEmptyComponent={empty as never}
      ListFooterComponent={paged.loadingMore ? <ActivityIndicator style={{ margin: space.lg }} color={colors.navy} /> : <View style={{ height: 30 }} />}
      onEndReached={paged.more}
      onEndReachedThreshold={0.5}
      keyboardShouldPersistTaps="handled"
      refreshControl={<RefreshControl refreshing={paged.refreshing} onRefresh={paged.refresh} tintColor={colors.navy} />}
    />
  );
}
