import DateTimePicker from '@react-native-community/datetimepicker';
import { Ionicons } from '@expo/vector-icons';
import { useState, type ReactNode } from 'react';
import {
  ActivityIndicator, Alert, FlatList, Image, KeyboardAvoidingView, Modal, Platform, Pressable, RefreshControl, ScrollView,
  StyleSheet, Text, TextInput, View, type StyleProp, type TextInputProps, type ViewStyle,
} from 'react-native';

import { formatDate, formatDateTime, initials, toApiDate, toApiDateTime } from '@/lib/format';
import type { Loaded } from '@/lib/hooks';
import { colors, radius, shadow, space } from '@/lib/theme';
import type { Choice } from '@/lib/types';

type IconName = keyof typeof Ionicons.glyphMap;

// ───────── Textes ─────────
export function T({ children, style, size = 15, weight = '400', color = colors.ink, lines, onPress }: {
  children?: ReactNode; style?: StyleProp<any>; size?: number; weight?: '400' | '500' | '600' | '700' | '800'; color?: string; lines?: number;
  onPress?: () => void;
}) {
  return <Text numberOfLines={lines} onPress={onPress} style={[{ fontSize: size, fontWeight: weight, color, lineHeight: size * 1.4 }, style]}>{children}</Text>;
}
export const H1 = ({ children, color }: { children: ReactNode; color?: string }) => <T size={24} weight="800" color={color}>{children}</T>;
export const H2 = ({ children }: { children: ReactNode }) => <T size={18} weight="700">{children}</T>;
export const Muted = ({ children, style, lines, size = 13 }: { children?: ReactNode; style?: StyleProp<any>; lines?: number; size?: number }) =>
  <T size={size} color={colors.muted} style={style} lines={lines}>{children}</T>;

// ───────── Écran ─────────
export function Screen({ children, loaded, padded = true, scroll = true, footer }: {
  children?: ReactNode; loaded?: Loaded<any>; padded?: boolean; scroll?: boolean; footer?: ReactNode;
}) {
  const body = loaded?.loading && !loaded.data ? <Loader /> : loaded?.error && !loaded.data
    ? <ErrorBox message={loaded.error} onRetry={loaded.reload} /> : children;
  return (
    <KeyboardAvoidingView style={styles.screen} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      {scroll ? (
        <ScrollView
          contentContainerStyle={[padded && { padding: space.lg, gap: space.md }, { paddingBottom: 40 }]}
          keyboardShouldPersistTaps="handled"
          refreshControl={loaded ? <RefreshControl refreshing={loaded.refreshing} onRefresh={loaded.refresh} tintColor={colors.navy} /> : undefined}
        >
          {body}
        </ScrollView>
      ) : <View style={{ flex: 1 }}>{body}</View>}
      {footer}
    </KeyboardAvoidingView>
  );
}

/** Liste défilante avec « tirer pour actualiser » et chargement par pages. */
export function List<I>({ loaded, data, render, empty, header, onEnd, ListFooter }: {
  loaded: Loaded<any>; data: I[]; render: (item: I) => ReactNode; empty?: ReactNode; header?: ReactNode; onEnd?: () => void; ListFooter?: ReactNode;
}) {
  if (loaded.loading && !loaded.data) return <Loader />;
  if (loaded.error && !loaded.data) return <ErrorBox message={loaded.error} onRetry={loaded.reload} />;
  return (
    <FlatList
      data={data}
      keyExtractor={(_, i) => String(i)}
      renderItem={({ item }) => <View>{render(item)}</View>}
      contentContainerStyle={{ padding: space.lg, gap: space.md, paddingBottom: 40 }}
      ListHeaderComponent={header ? <View style={{ gap: space.md, marginBottom: space.md }}>{header}</View> : null}
      ListEmptyComponent={(empty ?? null) as never}
      ListFooterComponent={(ListFooter ?? null) as never}
      onEndReached={onEnd}
      onEndReachedThreshold={0.4}
      keyboardShouldPersistTaps="handled"
      refreshControl={<RefreshControl refreshing={loaded.refreshing} onRefresh={loaded.refresh} tintColor={colors.navy} />}
    />
  );
}

export function Loader() {
  return <View style={styles.center}><ActivityIndicator size="large" color={colors.navy} /></View>;
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <View style={[styles.center, { gap: space.md, padding: space.xl }]}>
      <Ionicons name="cloud-offline-outline" size={40} color={colors.muted} />
      <T color={colors.ink2} style={{ textAlign: 'center' }}>{message}</T>
      {onRetry && <Button label="Réessayer" onPress={onRetry} variant="outline" />}
    </View>
  );
}

export function Empty({ icon = 'file-tray-outline', title, text, action }: { icon?: IconName; title: string; text?: string; action?: ReactNode }) {
  return (
    <View style={[styles.center, { gap: space.sm, padding: space.xl }]}>
      <View style={styles.emptyIcon}><Ionicons name={icon} size={30} color={colors.navy} /></View>
      <T weight="700" size={16} style={{ textAlign: 'center' }}>{title}</T>
      {text ? <Muted style={{ textAlign: 'center' }}>{text}</Muted> : null}
      {action}
    </View>
  );
}

// ───────── Cartes et blocs ─────────
export function Card({ children, onPress, style }: { children: ReactNode; onPress?: () => void; style?: StyleProp<ViewStyle> }) {
  const content = <View style={[styles.card, style]}>{children}</View>;
  return onPress ? <Pressable onPress={onPress} style={({ pressed }) => pressed && { opacity: 0.85 }}>{content}</Pressable> : content;
}

export function Section({ title, children, action }: { title: string; children: ReactNode; action?: ReactNode }) {
  return (
    <View style={{ gap: space.sm }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' }}>
        <H2>{title}</H2>{action}
      </View>
      {children}
    </View>
  );
}

export function Row({ children, style, gap = space.md }: { children: ReactNode; style?: StyleProp<ViewStyle>; gap?: number }) {
  return <View style={[{ flexDirection: 'row', alignItems: 'center', gap }, style]}>{children}</View>;
}

export function InfoLine({ icon, text }: { icon: IconName; text?: string | null }) {
  if (!text) return null;
  return (
    <Row gap={space.sm}>
      <Ionicons name={icon} size={16} color={colors.muted} />
      <View style={{ flex: 1 }}><Muted size={14}>{text}</Muted></View>
    </Row>
  );
}

export function Tile({ icon, value, label, onPress, tone = 'navy' }: {
  icon: IconName; value: string | number; label: string; onPress?: () => void; tone?: 'navy' | 'green' | 'gold' | 'warn';
}) {
  const tint = { navy: colors.navy, green: colors.green, gold: '#8a6d1d', warn: colors.warn }[tone];
  const bg = { navy: colors.blueBg, green: colors.greenBg, gold: colors.goldBg, warn: colors.warnBg }[tone];
  return (
    <Pressable onPress={onPress} disabled={!onPress} style={({ pressed }) => [styles.tile, pressed && { opacity: 0.85 }]}>
      <View style={[styles.tileIcon, { backgroundColor: bg }]}><Ionicons name={icon} size={20} color={tint} /></View>
      <T size={22} weight="800">{value}</T>
      <Muted lines={2}>{label}</Muted>
    </Pressable>
  );
}

export function TileGrid({ children }: { children: ReactNode }) {
  return <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.md }}>{children}</View>;
}

export function Menu({ items }: { items: { icon: IconName; label: string; onPress: () => void; badge?: number; danger?: boolean }[] }) {
  return (
    <View style={[styles.card, { padding: 0, overflow: 'hidden' }]}>
      {items.map((item, index) => (
        <Pressable key={item.label} onPress={item.onPress}
          style={({ pressed }) => [styles.menuRow, index > 0 && styles.menuSep, pressed && { backgroundColor: colors.surface2 }]}>
          <Ionicons name={item.icon} size={20} color={item.danger ? colors.danger : colors.navy} />
          <View style={{ flex: 1 }}><T weight="500" color={item.danger ? colors.danger : colors.ink}>{item.label}</T></View>
          {item.badge ? <Badge label={String(item.badge)} tone="warn" /> : null}
          <Ionicons name="chevron-forward" size={18} color={colors.muted} />
        </Pressable>
      ))}
    </View>
  );
}

// ───────── Badges, avatars, étapes ─────────
const TONES = {
  navy: [colors.blueBg, colors.navy], green: [colors.greenBg, colors.green], gold: [colors.goldBg, '#7a5f12'],
  warn: [colors.warnBg, colors.warn], red: [colors.dangerBg, colors.danger], grey: [colors.surface2, colors.ink2],
} as const;
export type Tone = keyof typeof TONES;

export function Badge({ label, tone = 'navy', icon }: { label: string; tone?: Tone; icon?: IconName }) {
  const [bg, fg] = TONES[tone];
  return (
    <View style={[styles.badge, { backgroundColor: bg }]}>
      {icon ? <Ionicons name={icon} size={12} color={fg} /> : null}
      <Text style={{ color: fg, fontSize: 12, fontWeight: '700' }}>{label}</Text>
    </View>
  );
}

export function VerifiedBadge() {
  return <Ionicons name="checkmark-circle" size={16} color="#1d6fd8" />;
}

export function Avatar({ uri, name, size = 44 }: { uri?: string | null; name: string; size?: number }) {
  if (uri) return <Image source={{ uri }} style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: colors.surface2 }} />;
  return (
    <View style={{ width: size, height: size, borderRadius: size / 2, backgroundColor: colors.navy, alignItems: 'center', justifyContent: 'center' }}>
      <Text style={{ color: colors.white, fontWeight: '700', fontSize: size * 0.36 }}>{initials(name)}</Text>
    </View>
  );
}

export function Logo({ uri, name, size = 48 }: { uri?: string | null; name: string; size?: number }) {
  if (uri) return <Image source={{ uri }} style={{ width: size, height: size, borderRadius: radius.sm, backgroundColor: colors.surface2 }} resizeMode="contain" />;
  return (
    <View style={{ width: size, height: size, borderRadius: radius.sm, backgroundColor: colors.blueBg, alignItems: 'center', justifyContent: 'center' }}>
      <Text style={{ color: colors.navy, fontWeight: '800', fontSize: size * 0.36 }}>{initials(name)}</Text>
    </View>
  );
}

export function Progress({ percent }: { percent: number }) {
  return (
    <View style={{ height: 8, backgroundColor: 'rgba(255,255,255,0.25)', borderRadius: 4, overflow: 'hidden' }}>
      <View style={{ width: `${Math.max(0, Math.min(100, percent))}%`, height: 8, backgroundColor: colors.gold, borderRadius: 4 }} />
    </View>
  );
}

/** Suivi en étapes (candidature, commande) : une pastille par étape, l'étape courante en bleu. */
export function Steps({ labels, current, failedAt }: { labels: string[]; current: number; failedAt?: number }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'flex-start' }}>
      {labels.map((label, i) => {
        const done = i < current;
        const active = i === current;
        const failed = failedAt === i;
        const tint = failed ? colors.danger : done || active ? colors.green : colors.border;
        return (
          <View key={label} style={{ flex: 1, alignItems: 'center', gap: 4 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', width: '100%' }}>
              <View style={{ flex: 1, height: 3, backgroundColor: i === 0 ? 'transparent' : (i <= current ? colors.green : colors.border) }} />
              <View style={[styles.dot, { backgroundColor: done || active || failed ? tint : colors.surface, borderColor: tint }]}>
                {done ? <Ionicons name="checkmark" size={12} color={colors.white} /> : failed ? <Ionicons name="close" size={12} color={colors.white} /> : null}
              </View>
              <View style={{ flex: 1, height: 3, backgroundColor: i === labels.length - 1 ? 'transparent' : (i < current ? colors.green : colors.border) }} />
            </View>
            <Text style={{ fontSize: 11, textAlign: 'center', color: active ? colors.ink : colors.muted, fontWeight: active ? '700' : '400' }}>{label}</Text>
          </View>
        );
      })}
    </View>
  );
}

// ───────── Boutons ─────────
export function Button({ label, onPress, variant = 'solid', loading, disabled, icon, small, style }: {
  label: string; onPress: () => void; variant?: 'solid' | 'outline' | 'ghost' | 'green' | 'danger' | 'gold'; loading?: boolean;
  disabled?: boolean; icon?: IconName; small?: boolean; style?: StyleProp<ViewStyle>;
}) {
  const palette = {
    solid: { bg: colors.navy, fg: colors.white, border: colors.navy },
    green: { bg: colors.green, fg: colors.white, border: colors.green },
    gold: { bg: colors.gold, fg: colors.ink, border: colors.gold },
    danger: { bg: colors.danger, fg: colors.white, border: colors.danger },
    outline: { bg: 'transparent', fg: colors.navy, border: colors.navy },
    ghost: { bg: 'transparent', fg: colors.navy, border: 'transparent' },
  }[variant];
  const off = disabled || loading;
  return (
    <Pressable onPress={onPress} disabled={off}
      style={({ pressed }) => [styles.button, small && { paddingVertical: 8, paddingHorizontal: 14 },
        { backgroundColor: palette.bg, borderColor: palette.border, opacity: off ? 0.55 : pressed ? 0.85 : 1 }, style]}>
      {loading ? <ActivityIndicator color={palette.fg} size="small" /> : (
        <>
          {icon ? <Ionicons name={icon} size={small ? 15 : 18} color={palette.fg} /> : null}
          <Text style={{ color: palette.fg, fontWeight: '700', fontSize: small ? 13 : 15 }}>{label}</Text>
        </>
      )}
    </Pressable>
  );
}

// ───────── Champs de formulaire ─────────
export function Field({ label, error, hint, children }: { label?: string; error?: string; hint?: string; children: ReactNode }) {
  return (
    <View style={{ gap: 6 }}>
      {label ? <T size={13} weight="600" color={colors.ink2}>{label}</T> : null}
      {children}
      {hint && !error ? <Muted size={12}>{hint}</Muted> : null}
      {error ? <T size={12} color={colors.danger}>{error}</T> : null}
    </View>
  );
}

export function Input({ label, error, hint, multiline, ...rest }: TextInputProps & { label?: string; error?: string; hint?: string }) {
  return (
    <Field label={label} error={error} hint={hint}>
      <TextInput
        placeholderTextColor="#94a3b8"
        multiline={multiline}
        textAlignVertical={multiline ? 'top' : 'center'}
        {...rest}
        style={[styles.input, multiline && { minHeight: 110, paddingTop: 12 }, !!error && { borderColor: colors.danger }]}
      />
    </Field>
  );
}

/** Liste de choix : ouvre une fenêtre pour sélectionner une (ou plusieurs) valeur(s). */
export function Select({ label, value, options, onChange, placeholder = 'Choisir…', error, allowEmpty }: {
  label?: string; value: string; options: Choice[]; onChange: (v: string) => void; placeholder?: string; error?: string; allowEmpty?: string;
}) {
  const [open, setOpen] = useState(false);
  const current = options.find((o) => o.value === value);
  return (
    <Field label={label} error={error}>
      <Pressable onPress={() => setOpen(true)} style={[styles.input, styles.selectRow, !!error && { borderColor: colors.danger }]}>
        <Text style={{ flex: 1, color: current ? colors.ink : '#94a3b8', fontSize: 15 }} numberOfLines={1}>{current ? current.label : placeholder}</Text>
        <Ionicons name="chevron-down" size={18} color={colors.muted} />
      </Pressable>
      <Modal visible={open} transparent animationType="slide" onRequestClose={() => setOpen(false)}>
        <Pressable style={styles.backdrop} onPress={() => setOpen(false)}>
          <View style={styles.sheet}>
            <T weight="700" size={16} style={{ padding: space.lg, paddingBottom: space.sm }}>{label || 'Choisir'}</T>
            <ScrollView>
              {allowEmpty ? (
                <Pressable onPress={() => { onChange(''); setOpen(false); }} style={styles.optionRow}>
                  <T color={colors.muted}>{allowEmpty}</T>
                </Pressable>
              ) : null}
              {options.map((o) => (
                <Pressable key={o.value} onPress={() => { onChange(o.value); setOpen(false); }} style={styles.optionRow}>
                  <View style={{ flex: 1 }}><T weight={o.value === value ? '700' : '400'}>{o.label}</T></View>
                  {o.value === value ? <Ionicons name="checkmark" size={20} color={colors.green} /> : null}
                </Pressable>
              ))}
            </ScrollView>
          </View>
        </Pressable>
      </Modal>
    </Field>
  );
}

export function MultiChoice({ label, options, values, onChange }: { label?: string; options: Choice[]; values: string[]; onChange: (v: string[]) => void }) {
  return (
    <Field label={label}>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: space.sm }}>
        {options.map((o) => {
          const on = values.includes(o.value);
          return (
            <Pressable key={o.value} onPress={() => onChange(on ? values.filter((v) => v !== o.value) : [...values, o.value])}
              style={[styles.chip, on && { backgroundColor: colors.navy, borderColor: colors.navy }]}>
              <Text style={{ color: on ? colors.white : colors.ink2, fontWeight: '600', fontSize: 13 }}>{o.label}</Text>
            </Pressable>
          );
        })}
      </View>
    </Field>
  );
}

export function Chips({ options, value, onChange }: { options: Choice[]; value: string; onChange: (v: string) => void }) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: space.sm, paddingHorizontal: space.lg }}>
      {options.map((o) => {
        const on = o.value === value;
        return (
          <Pressable key={o.value} onPress={() => onChange(o.value)} style={[styles.chip, on && { backgroundColor: colors.navy, borderColor: colors.navy }]}>
            <Text style={{ color: on ? colors.white : colors.ink2, fontWeight: '600', fontSize: 13 }}>{o.label}</Text>
          </Pressable>
        );
      })}
    </ScrollView>
  );
}

export function Switch2({ label, value, onChange }: { label: string; value: boolean; onChange: (v: boolean) => void }) {
  return (
    <Pressable onPress={() => onChange(!value)} style={{ flexDirection: 'row', alignItems: 'center', gap: space.md }}>
      <View style={[styles.checkbox, value && { backgroundColor: colors.navy, borderColor: colors.navy }]}>
        {value ? <Ionicons name="checkmark" size={16} color={colors.white} /> : null}
      </View>
      <View style={{ flex: 1 }}><T>{label}</T></View>
    </Pressable>
  );
}

/** Choix d'une date (ou d'une date et heure) avec le sélecteur du téléphone. */
export function DateField({ label, value, onChange, withTime, error, minimumDate }: {
  label?: string; value: Date | null; onChange: (d: Date | null) => void; withTime?: boolean; error?: string; minimumDate?: Date;
}) {
  const [show, setShow] = useState(false);
  const [stage, setStage] = useState<'date' | 'time'>('date');
  const [draft, setDraft] = useState<Date>(value ?? new Date());
  const text = value ? (withTime ? formatDateTime(value.toISOString()) : formatDate(value.toISOString())) : '';

  if (Platform.OS === 'web') {
    return (
      <Input label={label} error={error} value={value ? (withTime ? toApiDateTime(value).slice(0, 16) : toApiDate(value)) : ''}
        placeholder={withTime ? 'AAAA-MM-JJTHH:MM' : 'AAAA-MM-JJ'}
        onChangeText={(t) => { const d = new Date(t); onChange(isNaN(d.getTime()) ? null : d); }} />
    );
  }
  const onPick = (_: unknown, picked?: Date) => {
    if (Platform.OS === 'android') {
      setShow(false);
      if (!picked) return;
      if (withTime && stage === 'date') {
        setDraft(picked);
        setStage('time');
        setTimeout(() => setShow(true), 50);
        return;
      }
      const merged = new Date(draft);
      if (withTime && stage === 'time') merged.setHours(picked.getHours(), picked.getMinutes(), 0, 0);
      else merged.setTime(picked.getTime());
      setStage('date');
      onChange(merged);
    } else if (picked) {
      setDraft(picked);
    }
  };
  return (
    <Field label={label} error={error}>
      <Pressable onPress={() => { setStage('date'); setShow(true); }} style={[styles.input, styles.selectRow, !!error && { borderColor: colors.danger }]}>
        <Text style={{ flex: 1, color: text ? colors.ink : '#94a3b8', fontSize: 15 }}>{text || 'Choisir une date'}</Text>
        <Ionicons name="calendar-outline" size={18} color={colors.muted} />
        {value ? <Pressable onPress={() => onChange(null)} hitSlop={10}><Ionicons name="close-circle" size={18} color={colors.muted} /></Pressable> : null}
      </Pressable>
      {show && Platform.OS === 'android' ? (
        <DateTimePicker value={draft} mode={stage} minimumDate={minimumDate} onChange={onPick} is24Hour />
      ) : null}
      {show && Platform.OS === 'ios' ? (
        <Modal transparent animationType="slide" visible onRequestClose={() => setShow(false)}>
          <View style={styles.backdrop}>
            <View style={[styles.sheet, { padding: space.lg, gap: space.md }]}>
              <DateTimePicker value={draft} mode={withTime ? 'datetime' : 'date'} display="spinner" minimumDate={minimumDate}
                locale="fr-FR" onChange={onPick} />
              <Button label="Valider" onPress={() => { onChange(draft); setShow(false); }} />
              <Button label="Annuler" variant="ghost" onPress={() => setShow(false)} />
            </View>
          </View>
        </Modal>
      ) : null}
    </Field>
  );
}

/** Choix d'un fichier : affiche le nom du fichier choisi ou le fichier déjà envoyé. */
export function FilePicker({ label, fileName, onPress, icon = 'attach', error, hint }: {
  label?: string; fileName?: string | null; onPress: () => void; icon?: IconName; error?: string; hint?: string;
}) {
  return (
    <Field label={label} error={error} hint={hint}>
      <Pressable onPress={onPress} style={[styles.input, styles.selectRow, { borderStyle: 'dashed' }, !!error && { borderColor: colors.danger }]}>
        <Ionicons name={icon} size={20} color={colors.navy} />
        <Text style={{ flex: 1, color: fileName ? colors.ink : colors.navy, fontSize: 15, fontWeight: fileName ? '400' : '600' }} numberOfLines={1}>
          {fileName || 'Choisir un fichier'}
        </Text>
      </Pressable>
    </Field>
  );
}

// ───────── Alertes ─────────
export function notice(title: string, message?: string) {
  if (Platform.OS === 'web') globalThis.alert?.(message ? `${title}\n${message}` : title);
  else Alert.alert(title, message);
}

export function confirm(title: string, message: string, confirmLabel: string, onConfirm: () => void, destructive = false) {
  if (Platform.OS === 'web') {
    if (globalThis.confirm?.(`${title}\n${message}`)) onConfirm();
    return;
  }
  Alert.alert(title, message, [
    { text: 'Annuler', style: 'cancel' },
    { text: confirmLabel, style: destructive ? 'destructive' : 'default', onPress: onConfirm },
  ]);
}

export function Banner({ tone = 'navy', icon = 'information-circle', children }: { tone?: Tone; icon?: IconName; children: ReactNode }) {
  const [bg, fg] = TONES[tone];
  return (
    <View style={{ flexDirection: 'row', gap: space.sm, padding: space.md, borderRadius: radius.md, backgroundColor: bg }}>
      <Ionicons name={icon} size={20} color={fg} />
      <View style={{ flex: 1 }}><Text style={{ color: fg, fontSize: 14, lineHeight: 20 }}>{children}</Text></View>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', minHeight: 200 },
  emptyIcon: { width: 64, height: 64, borderRadius: 32, backgroundColor: colors.blueBg, alignItems: 'center', justifyContent: 'center' },
  card: { backgroundColor: colors.surface, borderRadius: radius.md, padding: space.lg, gap: space.sm, borderWidth: 1, borderColor: colors.border, ...shadow },
  tile: { flexBasis: '47%', flexGrow: 1, backgroundColor: colors.surface, borderRadius: radius.md, padding: space.lg, gap: 6, borderWidth: 1, borderColor: colors.border, ...shadow },
  tileIcon: { width: 38, height: 38, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  menuRow: { flexDirection: 'row', alignItems: 'center', gap: space.md, paddingHorizontal: space.lg, paddingVertical: 14 },
  menuSep: { borderTopWidth: 1, borderTopColor: colors.border },
  badge: { flexDirection: 'row', alignItems: 'center', gap: 4, alignSelf: 'flex-start', paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.pill },
  dot: { width: 22, height: 22, borderRadius: 11, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
  button: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingVertical: 14, paddingHorizontal: 20, borderRadius: radius.md, borderWidth: 1.5 },
  input: { backgroundColor: colors.surface, borderWidth: 1, borderColor: 'rgba(15,23,42,0.18)', borderRadius: radius.md, paddingHorizontal: 14, paddingVertical: 12, fontSize: 15, color: colors.ink },
  selectRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  backdrop: { flex: 1, backgroundColor: 'rgba(15,23,42,0.45)', justifyContent: 'flex-end' },
  sheet: { backgroundColor: colors.surface, borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg, maxHeight: '75%', paddingBottom: 24 },
  optionRow: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: space.lg, paddingVertical: 14, borderTopWidth: 1, borderTopColor: colors.border },
  chip: { paddingHorizontal: 14, paddingVertical: 8, borderRadius: radius.pill, borderWidth: 1, borderColor: 'rgba(15,23,42,0.18)', backgroundColor: colors.surface },
  checkbox: { width: 24, height: 24, borderRadius: 6, borderWidth: 2, borderColor: 'rgba(15,23,42,0.3)', alignItems: 'center', justifyContent: 'center' },
});
