// Formes des réponses de l'API (voir docs/API.md).
export type Kind = 'candidate' | 'employer' | 'member' | 'undefined' | 'anonymous';

export interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  name: string;
  phone: string;
  city: string;
  country: string;
  avatar: string | null;
  account_type: string;
  kind: Kind;
  is_staff: boolean;
  has_profile: boolean;
  employer_status?: 'pending' | 'approved' | 'rejected';
  unread_notifications?: number;
  unread_messages?: number;
  new_applications?: number;
}

export interface Choice { value: string; label: string }

export interface AppConfig {
  domains: Choice[];
  contracts: Choice[];
  education_levels: Choice[];
  internship_durations: string[];
  request_types: Choice[];
  document_kinds: Choice[];
  account_types: Choice[];
  payment: { flooz: string; tmoney: string; whatsapp: string };
  api_version: number;
}

export interface Page<T> { count: number; page: number; pages: number; results: T[]; counts?: Record<string, number> }

export interface Company {
  id: number; name: string; logo: string | null; sector: string; sector_label: string; city: string;
  verified: boolean; is_partner: boolean; user_id: number;
  description?: string; products?: string[]; website?: string; whatsapp?: string; contact_email?: string;
  employees_count?: number; offers?: Offer[]; posts?: Post[]; can_message?: boolean;
}

export interface Offer {
  id: number; slug: string; title: string; company: string; company_id: number | null; company_logo: string | null;
  domain: string; domain_label: string; contract: string; contract_label: string; city: string; duration: string;
  salary: string; deadline: string | null; featured: boolean; cover_image: string | null;
  requires_cover_letter: boolean; status: string; created_at: string;
  description?: string; requirements?: string; skills?: string[];
  applied?: boolean; can_apply?: boolean; applications?: number;
}

export interface OfferDetail extends Omit<Offer, 'company'> { company: Company | null; company_name?: string }

export interface Slot { start: string; note: string }

export interface Appointment {
  id: number; title: string; scheduled_at: string; place: string; notes: string; status: string; status_label: string;
  candidate: string; company: string | null; application_id: number | null;
}

export interface Document { id: number; kind: string; kind_label: string; title: string; url: string; created_at: string }

export interface Candidate {
  id: number; name: string; headline: string; domain: string; domain_label: string; skills: string[]; city: string;
  bio: string; experience_years: number; education_level: string; contract_wanted: string[]; available: boolean;
  seeking_internship: boolean; internship_duration: string; available_from: string | null; avatar: string | null;
  is_published: boolean; user_id?: number; email?: string; phone?: string; cover_letter?: string; has_cv?: boolean; cv_url?: string | null;
  documents?: Document[];
}

export interface Application {
  id: number; status: string; status_label: string; step: number; offer: Offer | null; title: string; company: string;
  created_at: string; cover_letter: string; status_message: string; internship_duration: string;
  available_from: string | null; consent: string; origin: string; incomplete: string[]; slots: Slot[];
  appointments: Appointment[]; candidate?: Candidate;
}

export interface SpontaneousRequest {
  id: number; request_type: string; request_type_label: string; domain: string; domain_label: string; skills: string[];
  city: string; available_from: string | null; duration: string; message: string; status: string; status_label: string;
  status_message: string; withdrawn: boolean; can_edit: boolean; is_open: boolean; created_at: string;
}

export interface Plan {
  code: string; kind: string; name: string; description: string; advantages: string[]; price: number; price_label: string;
  quote_only: boolean; duration_days: number;
}

export interface Order {
  id: number; reference: string; plan: Plan; status: string; status_label: string; step: number; amount: number;
  amount_label: string; title: string; text: string; post_kind: string; link_url: string; image: string | null;
  review_message: string; can_pay: boolean; can_edit: boolean; payment_method: string; payment_reference: string;
  receipt_number: string; paid_at: string | null; visible_until: string | null; created_at: string; offer_id: number | null;
}

export interface Comment { id: number; author: string; text: string; created_at: string }

export interface Post {
  id: number; author: string; author_verified: boolean; author_company_id: number | null; author_logo: string | null;
  text: string; image: string | null; kind: string; sponsored: boolean; featured: boolean; likes: number; liked: boolean;
  comments: Comment[]; created_at: string;
}

export interface Notice { id: number; text: string; url: string; is_read: boolean; created_at: string }

export interface Message {
  id: number; author: string; author_role: string; is_automatic: boolean; mine: boolean; body: string; created_at: string;
}

export interface Conversation {
  id: number; title: string; subject: string; kind: string; status: string; last_message: string; updated_at: string;
  unread: number; assignee?: { name: string }; messages?: Message[];
}

export interface Partner {
  id: number; name: string; logo: string | null; country: string; domain: string; description: string; website: string;
  whatsapp: string; phone: string; email: string; achievements?: string; company?: Company; posts?: Post[]; can_message?: boolean;
}

export interface Dashboard {
  user: User; kind: Kind; unread_notifications: number; unread_messages: number; new_applications?: number;
  completion?: number; applications?: number; upcoming_appointments?: number; shortlisted?: Application[]; pending_consent?: Application[];
  company_status?: 'pending' | 'approved' | 'rejected'; offers?: number;
}

export interface EmployerProfileData extends Company {
  exists: boolean; status: 'pending' | 'approved' | 'rejected'; status_label: string; decision_message: string;
  has_document: boolean; publishing_free: boolean;
}
