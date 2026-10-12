import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { Image, View } from 'react-native';

import { colors, space } from '@/lib/theme';
import InstallApp from '@/screens/InstallApp';
import { Banner, Button, Card, H2, Muted, Screen, T } from '@/ui';

const Step = ({ n, children }: { n: number; children: React.ReactNode }) => (
  <View style={{ flexDirection: 'row', gap: space.md, alignItems: 'flex-start' }}>
    <View style={{ width: 26, height: 26, borderRadius: 13, backgroundColor: colors.navy, alignItems: 'center', justifyContent: 'center' }}>
      <T size={13} weight="800" color={colors.white}>{n}</T>
    </View>
    <View style={{ flex: 1 }}><T size={14} color={colors.ink2}>{children}</T></View>
  </View>
);

/** Page « Installer l'application » : accessible sans compte, à partager (https://lantantetechnologie.com/app/telecharger). */
export default function Download() {
  return (
    <Screen>
      <View style={{ alignItems: 'center', gap: space.sm }}>
        <Image source={require('../assets/images/icon.png')} style={{ width: 110, height: 110 }} resizeMode="contain" />
        <T size={22} weight="800" style={{ textAlign: 'center' }}>Lantante Technologie Job</T>
        <Muted size={14} style={{ textAlign: 'center' }}>Offres d'emploi, stages et recrutement au Togo et en Afrique.</Muted>
      </View>
      <InstallApp />
      <Card>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}><Ionicons name="logo-android" size={22} color={colors.green} /><H2>Android</H2></View>
        <Step n={1}>Ouvrez ce lien dans Chrome (pas dans WhatsApp ou Facebook).</Step>
        <Step n={2}>Touchez le menu ⋮ en haut à droite.</Step>
        <Step n={3}>Choisissez « Installer l'application » ou « Ajouter à l'écran d'accueil ».</Step>
      </Card>
      <Card>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}><Ionicons name="logo-apple" size={22} color={colors.ink} /><H2>iPhone</H2></View>
        <Step n={1}>Ouvrez ce lien dans Safari.</Step>
        <Step n={2}>Touchez le bouton Partager (le carré avec une flèche vers le haut).</Step>
        <Step n={3}>Choisissez « Sur l'écran d'accueil », puis Ajouter.</Step>
      </Card>
      <Banner icon="information-circle">L'icône Lantante Technologie apparaît ensuite sur votre écran d'accueil et l'application s'ouvre en plein écran.</Banner>
      <Button label="Ouvrir l'application" icon="arrow-forward" onPress={() => router.replace('/')} />
    </Screen>
  );
}
