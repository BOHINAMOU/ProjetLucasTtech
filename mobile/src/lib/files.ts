import * as DocumentPicker from 'expo-document-picker';
import * as FileSystem from 'expo-file-system/legacy';
import * as ImagePicker from 'expo-image-picker';
import * as Sharing from 'expo-sharing';
import { Linking, Platform } from 'react-native';

import { authHeaders } from './api';
import type { FilePart } from './api';

export type Picked = FilePart & { size?: number };

/** Choisit un fichier (PDF, Word, Excel, image…) sur le téléphone. */
export async function pickDocument(types: string[] = ['application/pdf']): Promise<Picked | null> {
  const res = await DocumentPicker.getDocumentAsync({ type: types, copyToCacheDirectory: true, multiple: false });
  if (res.canceled || !res.assets?.length) return null;
  const a = res.assets[0];
  return { uri: a.uri, name: a.name, type: a.mimeType || 'application/octet-stream', size: a.size };
}

/** Choisit une photo dans la galerie. */
export async function pickImage(square = false): Promise<Picked | null> {
  const res = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ['images'], quality: 0.8, allowsEditing: square, aspect: square ? [1, 1] : undefined,
  });
  if (res.canceled || !res.assets?.length) return null;
  const a = res.assets[0];
  const name = a.fileName || `photo-${Date.now()}.jpg`;
  return { uri: a.uri, name, type: a.mimeType || 'image/jpeg', size: a.fileSize };
}

/** Télécharge un fichier privé (CV, diplôme) avec le jeton du compte, puis le propose à l'ouverture. */
export async function openPrivateFile(url: string, fileName: string) {
  if (Platform.OS === 'web') {
    await Linking.openURL(url);
    return;
  }
  const safe = fileName.replace(/[^\w.-]+/g, '_');
  const target = `${FileSystem.cacheDirectory}${Date.now()}-${safe}`;
  const result = await FileSystem.downloadAsync(url, target, { headers: await authHeaders() });
  if (result.status !== 200) throw new Error("Impossible d'ouvrir ce fichier.");
  if (await Sharing.isAvailableAsync()) {
    await Sharing.shareAsync(result.uri, { mimeType: result.headers?.['Content-Type'] });
  }
}
