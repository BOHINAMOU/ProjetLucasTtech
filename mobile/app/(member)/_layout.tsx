import { TabsLayout } from '@/screens/TabsLayout';

export default function MemberLayout() {
  return (
    <TabsLayout tabs={[
      { name: 'index', title: 'Accueil', icon: 'home-outline', iconOn: 'home' },
      { name: 'publish', title: 'Publier', icon: 'add-circle-outline', iconOn: 'add-circle' },
      { name: 'discover', title: 'Découvrir', icon: 'compass-outline', iconOn: 'compass' },
      { name: 'messages', title: 'Messages', icon: 'chatbubbles-outline', iconOn: 'chatbubbles', badge: 'messages' },
      { name: 'more', title: 'Plus', icon: 'menu-outline', iconOn: 'menu' },
    ]} />
  );
}
