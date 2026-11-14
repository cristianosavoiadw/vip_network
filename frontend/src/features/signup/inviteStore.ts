/** The invite code travels from /convite to the sign-up wizard (sent with POST /auth/register). */
const KEY = "vip.invite";

export function saveInviteCode(code: string): void {
  try {
    sessionStorage.setItem(KEY, code);
  } catch {
    /* storage blocked: the code still goes in the URL */
  }
}

export function readInviteCode(): string | null {
  try {
    return sessionStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function clearInviteCode(): void {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    /* ignore */
  }
}

export interface InviteCheck {
  code: string;
  inviter: string;
  inviter_color: string;
  company_name: string;
  first_name: string;
  last_name: string;
  email: string;
  bind_email: boolean;
  expires_at: string;
  vip_months: number;
  invites_per_member: number;
  mode: "invite" | "paid" | "both";
}
