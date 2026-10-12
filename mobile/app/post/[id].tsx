import { useLocalSearchParams } from 'expo-router';

import { useAuth } from '@/lib/auth';
import { useLoad } from '@/lib/hooks';
import type { Post } from '@/lib/types';
import { Screen } from '@/ui';
import { PostCard } from '@/ui/cards';

/** Une actualité en entier (texte, image, j'aime, commentaires). */
export default function PostScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { user } = useAuth();
  const loaded = useLoad<Post>(`feed/${id}`);
  return <Screen loaded={loaded}>{loaded.data ? <PostCard key={loaded.data.id} post={loaded.data} canInteract={!!user} /> : null}</Screen>;
}
