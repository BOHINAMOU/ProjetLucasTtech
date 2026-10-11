import { Redirect } from 'expo-router';

import { homeFor, useAuth } from '@/lib/auth';

export default function Index() {
  const { kind } = useAuth();
  return <Redirect href={homeFor(kind) as never} />;
}
