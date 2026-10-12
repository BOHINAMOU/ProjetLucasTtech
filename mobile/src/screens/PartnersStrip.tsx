import { router } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { Animated, Easing, Image, Platform, Pressable, View } from 'react-native';

import { useLoad } from '@/lib/hooks';
import { colors, radius } from '@/lib/theme';
import type { Page, Partner } from '@/lib/types';
import { Logo, T } from '@/ui';

const SHOW_MS = 3000; // temps d'affichage de chaque partenaire
const MOVE_MS = 350;
const HEIGHT = 150;

/** Bannière rectangulaire en haut de l'accueil (comme les bannières d'une application de transport) :
 * un partenaire à la fois, environ 3 secondes, puis il sort et le suivant arrive. */
export default function PartnersStrip() {
  const loaded = useLoad<Page<Partner>>('partners');
  const partners = loaded.data?.results ?? [];
  const count = partners.length;
  const [index, setIndex] = useState(0);
  const [width, setWidth] = useState(0);
  const x = useRef(new Animated.Value(0)).current;
  const native = Platform.OS !== 'web';

  useEffect(() => {
    if (count < 2 || !width) return;
    let alive = true;
    const timer = setInterval(() => {
      Animated.timing(x, { toValue: -width, duration: MOVE_MS, easing: Easing.in(Easing.quad), useNativeDriver: native }).start(() => {
        if (!alive) return;
        setIndex((i) => (i + 1) % count);
        x.setValue(width);
        Animated.timing(x, { toValue: 0, duration: MOVE_MS, easing: Easing.out(Easing.quad), useNativeDriver: native }).start();
      });
    }, SHOW_MS + MOVE_MS * 2);
    return () => { alive = false; clearInterval(timer); };
  }, [count, width, x, native]);

  if (!count) return null;
  const current = index % count;
  const p = partners[current];
  const open = () => router.push(`/partner/${p.id}` as never);

  return (
    <View onLayout={(e) => setWidth(e.nativeEvent.layout.width)}
      style={{ height: HEIGHT, borderRadius: radius.sm + 2, overflow: 'hidden', backgroundColor: colors.navy }}>
      <Animated.View style={{ flex: 1, flexDirection: 'row', transform: [{ translateX: x }] }}>
        {/* Moitié gauche : le logo sur fond blanc, pleine hauteur */}
        <Pressable onPress={open} style={{ width: '42%', backgroundColor: colors.white, alignItems: 'center', justifyContent: 'center', padding: 12 }}>
          {p.logo ? <Image source={{ uri: p.logo }} style={{ width: '100%', height: '100%' }} resizeMode="contain" /> : <Logo name={p.name} size={84} />}
        </Pressable>
        {/* Moitié droite : le nom et le bouton, fond marine */}
        <Pressable onPress={open} style={{ flex: 1, padding: 14, justifyContent: 'center', gap: 6 }}>
          <T size={11} weight="800" color={colors.gold} style={{ letterSpacing: 1 }}>NOTRE PARTENAIRE</T>
          <T size={18} weight="800" color={colors.white} lines={2}>{p.name}</T>
          {p.domain ? <T size={12} color="rgba(255,255,255,0.8)" lines={2}>{p.domain}</T> : null}
          <View style={{ alignSelf: 'flex-start', backgroundColor: colors.gold, borderRadius: radius.pill, paddingHorizontal: 14, paddingVertical: 7, marginTop: 2 }}>
            <T size={13} weight="800" color={colors.ink}>Voir le détail  ›</T>
          </View>
        </Pressable>
      </Animated.View>
      {count > 1 ? (
        <View pointerEvents="none" style={{ position: 'absolute', bottom: 6, left: 0, right: 0, flexDirection: 'row', justifyContent: 'center', gap: 5 }}>
          {partners.map((q, i) => (
            <View key={q.id} style={{ width: i === current ? 16 : 6, height: 6, borderRadius: 3, backgroundColor: i === current ? colors.gold : 'rgba(13,59,122,0.35)' }} />
          ))}
        </View>
      ) : null}
    </View>
  );
}
