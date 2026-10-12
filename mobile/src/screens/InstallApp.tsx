import { Ionicons } from '@expo/vector-icons';
import { useEffect, useState } from 'react';
import { Platform, View } from 'react-native';

import { colors, radius, space } from '@/lib/theme';
import { Button, Muted, T } from '@/ui';

type Mode = 'hidden' | 'prompt' | 'ios' | 'manual';

/** Version web : bouton « Installer l'application » (Android/Chrome) ou explication (iPhone/Safari). Invisible dans l'application installée. */
export default function InstallApp() {
  const [mode, setMode] = useState<Mode>('hidden');

  useEffect(() => {
    if (Platform.OS !== 'web' || typeof window === 'undefined') return;
    const w = window as unknown as { __installPrompt?: unknown; matchMedia: typeof window.matchMedia; navigator: Navigator & { standalone?: boolean } };
    if (w.matchMedia?.('(display-mode: standalone)').matches || w.navigator.standalone) return; // déjà installée
    const ua = w.navigator.userAgent || '';
    const ios = /iphone|ipad|ipod/i.test(ua);
    const update = () => setMode(w.__installPrompt ? 'prompt' : ios ? 'ios' : 'manual');
    update();
    window.addEventListener('installready', update);
    return () => window.removeEventListener('installready', update);
  }, []);

  if (mode === 'hidden') return null;

  const install = async () => {
    const w = window as unknown as { __installPrompt?: { prompt: () => Promise<void>; userChoice: Promise<{ outcome: string }> } };
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
        <T weight="700" color={colors.navy}>Installer l'application</T>
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
    </View>
  );
}
