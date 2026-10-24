import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useState } from 'react';
import { Image, Linking, Pressable, TextInput, View } from 'react-native';

import { post } from '@/lib/api';
import { formatDate, formatDateTime, timeAgo } from '@/lib/format';
import { colors, radius, space } from '@/lib/theme';
import type { Appointment, Application, Company, Conversation, Offer, Order, Partner, Post } from '@/lib/types';

import { Avatar, Badge, Card, InfoLine, Logo, Muted, Row, T, VerifiedBadge, notice, type Tone } from './index';

export function applicationTone(status: string): Tone {
  return ({ received: 'gold', shortlisted: 'navy', interview: 'navy', hired: 'green', refused: 'red', treated: 'grey' } as Record<string, Tone>)[status] ?? 'grey';
}

export function orderTone(status: string): Tone {
  return ({
    quote: 'gold', awaiting_payment: 'warn', payment_declared: 'gold', in_review: 'navy', changes_requested: 'warn',
    published: 'green', refused: 'red', refunded: 'grey', cancelled: 'grey',
  } as Record<string, Tone>)[status] ?? 'grey';
}

export function OfferCard({ offer }: { offer: Offer }) {
  return (
    <Card onPress={() => router.push(`/offer/${offer.slug}` as never)} style={{ padding: 0, overflow: 'hidden' }}>
      {offer.cover_image ? <Image source={{ uri: offer.cover_image }} style={{ height: 120, width: '100%', backgroundColor: colors.surface2 }} /> : null}
      <View style={{ padding: space.lg, gap: space.sm }}>
        <Row>
          <Logo uri={offer.company_logo} name={offer.company} size={44} />
          <View style={{ flex: 1 }}>
            <T weight="700" size={16} lines={2}>{offer.title}</T>
            <Muted lines={1}>{offer.company}</Muted>
          </View>
        </Row>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
          {offer.featured ? <Badge label="À la une" tone="gold" icon="star" /> : null}
          <Badge label={offer.contract_label} tone="navy" />
          {offer.domain_label ? <Badge label={offer.domain_label} tone="grey" /> : null}
        </View>
        <InfoLine icon="location-outline" text={offer.city} />
        {offer.deadline ? <InfoLine icon="time-outline" text={`Jusqu'au ${formatDate(offer.deadline)}`} /> : null}
      </View>
    </Card>
  );
}

export function CompanyCard({ company }: { company: Company }) {
  return (
    <Card onPress={() => router.push(`/company/${company.id}` as never)}>
      <Row>
        <Logo uri={company.logo} name={company.name} size={52} />
        <View style={{ flex: 1, gap: 2 }}>
          <Row gap={6}>
            <View style={{ flexShrink: 1 }}><T weight="700" size={16} lines={1}>{company.name}</T></View>
            {company.verified ? <VerifiedBadge /> : null}
          </Row>
          <Muted lines={1}>{[company.sector_label, company.city].filter(Boolean).join(' · ')}</Muted>
        </View>
        <Ionicons name="chevron-forward" size={18} color={colors.muted} />
      </Row>
    </Card>
  );
}

export function PartnerCard({ partner }: { partner: Partner }) {
  return (
    <Card onPress={() => router.push(`/partner/${partner.id}` as never)}>
      <Row>
        <Logo uri={partner.logo} name={partner.name} size={52} />
        <View style={{ flex: 1, gap: 2 }}>
          <T weight="700" size={16} lines={1}>{partner.name}</T>
          <Muted lines={2}>{partner.description || partner.country}</Muted>
        </View>
        <Ionicons name="chevron-forward" size={18} color={colors.muted} />
      </Row>
    </Card>
  );
}

export function PostDetail({ post: initial, canInteract = true }: { post: Post; canInteract?: boolean }) {
  const [item, setItem] = useState(initial);
  return (
    <Card style={{ padding: 0, overflow: 'hidden' }}>
      <View style={{ padding: space.lg, gap: space.sm }}>
        <Row>
          <Pressable disabled={!item.author_company_id} onPress={() => item.author_company_id && router.push(`/company/${item.author_company_id}` as never)}>
            <Avatar uri={item.author_logo} name={item.author} size={40} />
          </Pressable>
          <View style={{ flex: 1 }}>
            <Row gap={4}>
              <View style={{ flexShrink: 1 }}><T weight="700" lines={1}>{item.author}</T></View>
              {item.author_verified ? <VerifiedBadge /> : null}
            </Row>
            <Muted size={12}>{timeAgo(item.created_at)}</Muted>
          </View>
          {item.sponsored ? <Badge label="Sponsorisé" tone="gold" /> : item.featured ? <Badge label="À la une" tone="gold" icon="star" /> : null}
        </Row>
        {item.kind === 'product' ? <Badge label="Nouveau produit / service" tone="green" /> : null}
        <T size={20} weight="800" color={colors.green}>{item.headline}</T>
      </View>
      {item.image ? <Image source={{ uri: item.image }} style={{ width: '100%', aspectRatio: 1.4, backgroundColor: colors.surface2 }} resizeMode="cover" /> : null}
      {item.body ? <View style={{ padding: space.lg }}><T color={colors.ink2}>{item.body}</T></View> : null}
      <ShareRow post={item} />
      <Row style={{ padding: space.md, paddingHorizontal: space.lg, borderTopWidth: 1, borderTopColor: colors.border }} gap={8}>
        <Ionicons name="chatbubbles-outline" size={20} color={colors.navy} />
        <T weight="700" color={colors.navy}>Commentaires ({item.comments.length})</T>
      </Row>
      <Comments item={item} onChange={setItem} canInteract={canInteract} />
    </Card>
  );
}

const SQUARE = { width: 32, height: 32, backgroundColor: '#111', alignItems: 'center', justifyContent: 'center', borderRadius: 2 } as const;

/** « Partager sur : f  WhatsApp » (liens vers la page publique de l'actualité). */
export function ShareRow({ post: p, bordered = true }: { post: Post; bordered?: boolean }) {
  const url = encodeURIComponent(p.share_url);
  const text = encodeURIComponent(`${p.headline} `);
  return (
    <Row style={[{ justifyContent: 'space-between', paddingVertical: 8, paddingHorizontal: bordered ? space.lg : 0 }, bordered ? { borderTopWidth: 1, borderTopColor: colors.border } : null]}>
      <Muted size={13}>Publié le {formatDate(p.created_at)}</Muted>
      <Row gap={6}>
        <Muted size={13}>Partager sur :</Muted>
        <Pressable accessibilityLabel="Facebook" onPress={() => Linking.openURL(`https://www.facebook.com/sharer/sharer.php?u=${url}`)} style={SQUARE}>
          <Ionicons name="logo-facebook" size={18} color="#fff" />
        </Pressable>
        <Pressable accessibilityLabel="WhatsApp" onPress={() => Linking.openURL(`https://wa.me/?text=${text}${url}`)} style={SQUARE}>
          <Ionicons name="logo-whatsapp" size={18} color="#fff" />
        </Pressable>
      </Row>
    </Row>
  );
}

/** Carte d'actualité des listes : grande image, titre vert avec flèche, date et partage ; un toucher ouvre l'actualité. */
export function PostCard({ post: p }: { post: Post; canInteract?: boolean }) {
  const open = () => router.push(`/post/${p.id}` as never);
  return (
    <View style={{ gap: 0 }}>
      <Pressable onPress={open}>
        {p.image
          ? <Image source={{ uri: p.image }} style={{ width: '100%', aspectRatio: 1.85, backgroundColor: colors.surface2 }} resizeMode="cover" />
          : <View style={{ width: '100%', aspectRatio: 1.85, backgroundColor: colors.navy, alignItems: 'center', justifyContent: 'center' }}>
              <T size={44} weight="800" color={colors.white}>{(p.author || '?').charAt(0).toUpperCase()}</T>
            </View>}
      </Pressable>
      <Pressable onPress={open} style={{ flexDirection: 'row', gap: 10, alignItems: 'flex-start', justifyContent: 'space-between', marginTop: 14, marginBottom: 12 }}>
        <View style={{ flex: 1 }}><T size={19} weight="800" color={colors.green}>{p.headline}</T></View>
        <Ionicons name="arrow-forward-circle-outline" size={26} color={colors.ink2} style={{ marginTop: 2 }} />
      </Pressable>
      <View style={{ borderBottomWidth: 1, borderBottomColor: colors.border }}>
        <ShareRow post={p} bordered />
      </View>
      <Row gap={6} style={{ marginTop: 8, flexWrap: 'wrap' }}>
        <Muted size={12} style={{ fontWeight: '700' }}>{p.author}</Muted>
        {p.author_verified ? <VerifiedBadge /> : null}
        {p.sponsored ? <Badge label="Sponsorisé" tone="gold" /> : p.featured ? <Badge label="À la une" tone="gold" icon="star" /> : null}
        {p.kind === 'product' ? <Badge label="Nouveau produit" tone="green" /> : null}
        <View style={{ flex: 1 }} />
        <Ionicons name="chatbubble-outline" size={13} color={colors.muted} /><Muted size={12}>{p.comments.length} commentaire{p.comments.length > 1 ? 's' : ''}</Muted>
      </Row>
    </View>
  );
}

/** Bandeau de rubrique vert, comme sur les sites d'actualité. */
export function SectionBar({ title }: { title: string }) {
  return (
    <View style={{ backgroundColor: colors.green, borderLeftWidth: 6, borderLeftColor: colors.gold, paddingVertical: 7, paddingHorizontal: 14 }}>
      <T size={14} weight="800" color={colors.white} style={{ textTransform: 'uppercase', letterSpacing: 0.4 }}>{title}</T>
    </View>
  );
}

function Comments({ item, onChange, canInteract }: { item: Post; onChange: (p: Post) => void; canInteract: boolean }) {
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const send = async () => {
    if (!text.trim() || busy) return;
    setBusy(true);
    try {
      const res = await post<Post & { comment_pending?: boolean }>(`feed/${item.id}/comments`, { text: text.trim() });
      onChange(res);
      setText('');
      if (res.comment_pending) notice('Merci !', 'Votre commentaire sera publié après validation par notre équipe.');
    } catch {
      /* le message reste dans le champ pour réessayer */
    } finally {
      setBusy(false);
    }
  };
  return (
    <View style={{ padding: space.lg, paddingTop: space.sm, gap: space.sm, backgroundColor: colors.surface2 }}>
      {item.comments.map((c) => (
        <View key={c.id} style={{ gap: 2 }}>
          <T size={13} weight="700">{c.author} <Muted size={12}>· {timeAgo(c.created_at)}</Muted></T>
          <T size={14}>{c.text}</T>
        </View>
      ))}
      {canInteract ? (
        <Row>
          <TextInput value={text} onChangeText={setText} placeholder="Écrire un commentaire…" placeholderTextColor="#94a3b8"
            style={{ flex: 1, backgroundColor: colors.surface, borderRadius: radius.pill, paddingHorizontal: 14, paddingVertical: 8, fontSize: 14 }} />
          <Pressable onPress={send} disabled={busy}><Ionicons name="send" size={22} color={colors.navy} /></Pressable>
        </Row>
      ) : null}
    </View>
  );
}

export function ConversationCard({ conv }: { conv: Conversation }) {
  return (
    <Card onPress={() => router.push(`/chat/${conv.id}` as never)}>
      <Row>
        <Avatar name={conv.title} size={44} />
        <View style={{ flex: 1, gap: 2 }}>
          <Row style={{ justifyContent: 'space-between' }}>
            <View style={{ flex: 1 }}><T weight={conv.unread ? '800' : '700'} lines={1}>{conv.title}</T></View>
            <Muted size={12}>{timeAgo(conv.updated_at)}</Muted>
          </Row>
          {conv.kind === 'support' ? <Badge label="Service client" tone="green" /> : null}
          <Muted lines={1} size={14}>{conv.last_message}</Muted>
        </View>
        {conv.unread ? <Badge label={String(conv.unread)} tone="warn" /> : null}
      </Row>
    </Card>
  );
}

export function AppointmentCard({ appointment, footer }: { appointment: Appointment; footer?: React.ReactNode }) {
  const tone: Tone = ({ proposed: 'gold', confirmed: 'green', declined: 'red', done: 'grey', cancelled: 'grey' } as Record<string, Tone>)[appointment.status] ?? 'grey';
  return (
    <Card>
      <Row style={{ justifyContent: 'space-between' }}>
        <View style={{ flex: 1 }}><T weight="700">{appointment.title}</T></View>
        <Badge label={appointment.status_label} tone={tone} />
      </Row>
      <InfoLine icon="calendar-outline" text={formatDateTime(appointment.scheduled_at)} />
      <InfoLine icon="location-outline" text={appointment.place} />
      <InfoLine icon="business-outline" text={appointment.company} />
      <InfoLine icon="person-outline" text={appointment.candidate} />
      <InfoLine icon="document-text-outline" text={appointment.notes} />
      {footer}
    </Card>
  );
}

export function ApplicationCard({ application, onPress, employer }: { application: Application; onPress?: () => void; employer?: boolean }) {
  return (
    <Card onPress={onPress}>
      <Row style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <View style={{ flex: 1, gap: 2 }}>
          <T weight="700" size={16} lines={2}>{employer && application.candidate ? application.candidate.name : application.title}</T>
          <Muted lines={1}>{employer ? application.title : application.company}</Muted>
        </View>
        <Badge label={application.status_label} tone={applicationTone(application.status)} />
      </Row>
      <Muted size={12}>Reçue le {formatDate(application.created_at)}</Muted>
      {employer && application.candidate?.headline ? <T size={14} color={colors.ink2}>{application.candidate.headline}</T> : null}
      {application.incomplete?.length ? <Badge label={`Dossier incomplet : ${application.incomplete.join(', ')}`} tone="warn" icon="alert-circle" /> : null}
    </Card>
  );
}

const NEWS_KINDS = ['news', 'news_boost', 'ad'];

/** Aperçu d'une actualité en cours de publication, présenté comme dans le fil (image, titre vert, date). */
export function OrderPreview({ order, onPress }: { order: Order; onPress?: () => void }) {
  const Wrapper: any = onPress ? Pressable : View;
  return (
    <View>
      <Wrapper onPress={onPress}>
        {order.image
          ? <Image source={{ uri: order.image }} style={{ width: '100%', aspectRatio: 1.85, backgroundColor: colors.surface2 }} resizeMode="cover" />
          : <View style={{ width: '100%', aspectRatio: 1.85, backgroundColor: colors.navy, alignItems: 'center', justifyContent: 'center' }}>
              <T size={44} weight="800" color={colors.white}>{(order.headline || '?').charAt(0).toUpperCase()}</T>
            </View>}
        <View style={{ flexDirection: 'row', gap: 10, alignItems: 'flex-start', justifyContent: 'space-between', marginTop: 14, marginBottom: 12 }}>
          <View style={{ flex: 1 }}><T size={19} weight="800" color={colors.green}>{order.headline}</T></View>
          {onPress ? <Ionicons name="arrow-forward-circle-outline" size={26} color={colors.ink2} style={{ marginTop: 2 }} /> : null}
        </View>
      </Wrapper>
      <View style={{ borderTopWidth: 1, borderBottomWidth: 1, borderColor: colors.border, paddingVertical: 8, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
        <Muted size={13}>Publié le {formatDate(order.created_at)}</Muted>
        <Muted size={13}>{order.plan.name}</Muted>
      </View>
    </View>
  );
}

export function OrderCard({ order }: { order: Order }) {
  const go = () => router.push(`/order/${order.id}` as never);
  if (NEWS_KINDS.includes(order.plan.kind)) {
    return (
      <View style={{ gap: 8 }}>
        <OrderPreview order={order} onPress={go} />
        <Row style={{ justifyContent: 'space-between' }}>
          <Badge label={order.status_label} tone={orderTone(order.status)} />
          <Muted size={13}>{order.amount_label} · Réf. {order.reference}</Muted>
        </Row>
      </View>
    );
  }
  return (
    <Card onPress={go}>
      <Row style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <View style={{ flex: 1, gap: 2 }}>
          <T weight="700" lines={2}>{order.headline}</T>
          <Muted>{order.plan.name} · {order.amount_label}</Muted>
        </View>
        <Badge label={order.status_label} tone={orderTone(order.status)} />
      </Row>
      <Muted size={12}>Réf. {order.reference} · {formatDate(order.created_at)}</Muted>
    </Card>
  );
}
