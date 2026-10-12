import { TabsLayout } from '@/screens/TabsLayout';

export default function EmployerLayout() {
  return (
    <TabsLayout tabs={[
      { name: 'index', title: 'Accueil', icon: 'home-outline', iconOn: 'home' },
      { name: 'applications', title: 'Candidatures', icon: 'people-outline', iconOn: 'people', badge: 'applications' },
      { name: 'publish', title: 'Publier', icon: 'add-circle-outline', iconOn: 'add-circle' },
      { name: 'messages', title: 'Messages', icon: 'chatbubbles-outline', iconOn: 'chatbubbles', badge: 'messages' },
      { name: 'more', title: 'Plus', icon: 'menu-outline', iconOn: 'menu' },
    ]} />
  );
}
