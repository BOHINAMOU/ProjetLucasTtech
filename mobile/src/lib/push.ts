import Constants from 'expo-constants';
import * as Device from 'expo-device';
import * as Notifications from 'expo-notifications';
import { router } from 'expo-router';
import { Platform } from 'react-native';

import { api, post } from './api';

let currentToken: string | null = null;

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

/** Ouvre le bon écran à partir du chemin du site contenu dans la notification (« /emploi/messages/12/ »). */
export function openFromUrl(url?: string | null) {
  if (!url) return;
  try {
    const messages = url.match(/\/messages\/(\d+)/);
    if (messages) return router.push(`/chat/${messages[1]}` as never);
    if (url.includes('/rendez-vous')) return router.push('/appointments' as never);
    if (url.includes('/candidatures-recues')) return router.push('/(employer)/applications' as never);
    if (url.includes('/mes-commandes') || url.includes('/commandes')) return router.push('/orders' as never);
    if (url.includes('/mes-candidatures')) return router.push('/(candidate)/applications' as never);
    router.push('/notifications' as never);
  } catch {
    /* écran non disponible : on ignore */
  }
}

/** Demande l'autorisation, récupère l'adresse Expo Push du téléphone et l'envoie au serveur. */
export async function registerForPush() {
  try {
    if (Platform.OS === 'web' || !Device.isDevice) return;
    if (Platform.OS === 'android') {
      await Notifications.setNotificationChannelAsync('default', {
        name: 'Notifications',
        importance: Notifications.AndroidImportance.MAX,
        lightColor: '#0d3b7a',
      });
    }
    let { status } = await Notifications.getPermissionsAsync();
    if (status !== 'granted') status = (await Notifications.requestPermissionsAsync()).status;
    if (status !== 'granted') return;
    const projectId = Constants.expoConfig?.extra?.eas?.projectId ?? Constants.easConfig?.projectId;
    const token = (await Notifications.getExpoPushTokenAsync(projectId ? { projectId } : undefined)).data;
    currentToken = token;
    await post('devices', { token, platform: Platform.OS });
  } catch {
    /* les notifications sont un confort : l'application fonctionne sans */
  }
}

export async function unregisterPush() {
  try {
    if (currentToken) await api('DELETE', 'devices', { token: currentToken });
  } catch {
    /* ignoré */
  }
}

/** À brancher une fois : ouvre l'écran voulu quand l'utilisateur touche une notification. */
export function listenToNotificationTaps() {
  const sub = Notifications.addNotificationResponseReceivedListener((response) => {
    const data = response.notification.request.content.data as { url?: string } | undefined;
    openFromUrl(data?.url);
  });
  return () => sub.remove();
}
