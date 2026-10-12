import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Platform, Pressable, View } from 'react-native';

import { colors, radius, space } from '@/lib/theme';
import { Button, Muted, T } from '@/ui';

type Mode = 'hidden' | 'prompt' | 'ios' | 'manual';
type InstallEvent = { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> };
type Win = { __installPrompt?: InstallEvent };

/** Version web : bouton « Installer l'application » (Android/Chrome) ou explication (iPhone/Safari). Invisible dans l'application installée. */
export default function InstallApp({ dismissible = false }: { dismissible?: boolean }) {
  const [mode, setMode] = useState<Mode>('hidden');

  useEffect(() => {
    if (Platform.OS !== 'web' || typeof window === 'undefined') return;
    const nav = window.navigator as Navigator & { standalone?: boolean };
    if (window.matchMedia?.('(display-mode: standalone)').matches || nav.standalone) return; // déjà installée
    try {
      if (dismissible && globalThis.localStorage?.getItem('install_dismissed') === '1') return;
    } catch {
      /* ignoré */
    }
    const ios = /iphone|ipad|ipod/i.test(nav.userAgent || '');
    const update = () => setMode((window as unknown as Win).__installPrompt ? 'prompt' : ios ? 'ios' : 'manual');
    update();
    window.addEventListener('installready', update);
    return () => window.removeEventListener('installready', update);
  }, [dismissible]);

  if (mode === 'hidden') return null;

  const dismiss = () => {
    try {
      globalThis.localStorage?.setItem('install_dismissed', '1');
    } catch {
      /* ignoré */
    }
    setMode('hidden');
  };

  const install = async () => {
    const w = window as unknown as Win;
    const evt = w.__installPrompt;
    if (!evt) return;
    await evt.prompt();
    await evt.userChoice;
    w.__installPrompt = undefined;
    setMode('hidden');
  };

  return (
    <View style={{ backgroundColor: colors.blueBg, borderRadius: radius.md, padding: space.lg, gap: space.sm }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: space.sm }}>
        <Ionicons name="download-outline" size={20} color={colors.navy} />
        <View style={{ flex: 1 }}><T weight="700" color={colors.navy}>Installer l'application</T></View>
        {dismissible ? <Pressable onPress={dismiss} hitSlop={10}><Ionicons name="close" size={20} color={colors.navy} /></Pressable> : null}
      </View>
      {mode === 'prompt' ? (
        <>
          <Muted size={13}>Ajoutez Lantante Technologie Job à votre écran d'accueil pour l'ouvrir comme une application.</Muted>
          <Button label="Installer l'application" icon="download" onPress={install} />
        </>
      ) : mode === 'ios' ? (
        <Muted size={13}>Dans Safari, touchez le bouton Partager (le carré avec une flèche vers le haut), puis « Sur l'écran d'accueil ».</Muted>
      ) : (
        <Muted size={13}>Dans le menu de votre navigateur (⋮ ou ⋯), choisissez « Installer l'application » ou « Ajouter à l'écran d'accueil ».</Muted>
      )}
      <T size={13} weight="700" color={colors.navy} onPress={() => router.push('/telecharger' as never)}>Voir toutes les explications  ›</T>
    </View>
  );
}
