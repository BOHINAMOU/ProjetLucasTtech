import { TabsLayout } from '@/screens/TabsLayout';

export default function CandidateLayout() {
  return (
    <TabsLayout tabs={[
      { name: 'index', title: 'Accueil', icon: 'home-outline', iconOn: 'home' },
      { name: 'applications', title: 'Candidatures', icon: 'paper-plane-outline', iconOn: 'paper-plane' },
      { name: 'discover', title: 'Découvrir', icon: 'compass-outline', iconOn: 'compass' },
      { name: 'messages', title: 'Messages', icon: 'chatbubbles-outline', iconOn: 'chatbubbles', badge: 'messages' },
      { name: 'profile', title: 'Profil', icon: 'person-circle-outline', iconOn: 'person-circle' },
    ]} />
  );
}
