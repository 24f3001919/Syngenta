import { client, MOCK_MODE, mockDelay, getErrorMessage } from './client';
import {
  MOCK_REP_AUTH,
  MOCK_MANAGER_AUTH,
} from './mockData';
import { adaptAuthResponse, adaptRep } from './adapters';
import type { AuthResponse, OtpSendResponse, Rep, Login2FAResponse } from '../types';

export async function loginWithPassword(
  identifier: string,
  password: string,
): Promise<AuthResponse | Login2FAResponse> {
  if (MOCK_MODE) {
    await mockDelay(null);
    if (identifier.includes('manager')) return MOCK_MANAGER_AUTH;
    if (identifier === 'rep@syngenta.com' || identifier === '9999999999') return MOCK_REP_AUTH;
    throw new Error('Invalid credentials. Use rep@syngenta.com / syngenta123');
  }
  const { data } = await client.post('/auth/login/password', { identifier, password });
  // Backend may return either:
  //   - Full TokenResponse (no 2FA needed)
  //   - Login2FAResponse (2FA challenge — caller must call verify2fa)
  if (data.requires_2fa) {
    return data as Login2FAResponse;
  }
  return adaptAuthResponse(data);
}

export async function registerWithPassword(
  name: string, email: string, phone: string, password: string
): Promise<AuthResponse> {
  if (MOCK_MODE) {
    await mockDelay(null);
    return { ...MOCK_REP_AUTH, rep: { ...MOCK_REP_AUTH.rep, name, email, phone } };
  }
  const { data } = await client.post('/auth/register/password', { name, email, phone, password });
  return adaptAuthResponse(data);
}

export async function sendOtp(phone: string): Promise<OtpSendResponse> {
  if (MOCK_MODE) {
    await mockDelay(null, 600);
    return { message: 'OTP sent', dev_otp: '123456' };
  }
  const { data } = await client.post<{ dev_otp?: string }>('/auth/otp/send', { phone });
  return { message: 'OTP sent', dev_otp: data.dev_otp };
}

export async function verifyOtp(phone: string, code: string): Promise<AuthResponse> {
  if (MOCK_MODE) {
    await mockDelay(null, 500);
    if (code !== '123456') throw new Error('Invalid OTP. Use 123456 in demo mode.');
    return MOCK_REP_AUTH;
  }
  const { data } = await client.post('/auth/otp/verify', { phone, code });
  return adaptAuthResponse(data);
}

export async function loginWithGoogle(id_token: string): Promise<AuthResponse> {
  if (MOCK_MODE) {
    await mockDelay(null);
    return MOCK_REP_AUTH;
  }
  const { data } = await client.post('/auth/google/verify', { id_token });
  return adaptAuthResponse(data);
}

export async function getMe(): Promise<Rep> {
  if (MOCK_MODE) {
    await mockDelay(null, 200);
    const stored = localStorage.getItem('rep');
    if (stored) return JSON.parse(stored) as Rep;
    throw new Error('Not authenticated');
  }
  try {
    const { data } = await client.get('/auth/me');
    return adaptRep(data);
  } catch (err) {
    throw new Error(getErrorMessage(err));
  }
}
// ─── Refresh token (called by AuthContext on app boot) ────────────────────────

export async function refreshAccessToken(): Promise<AuthResponse | null> {
  if (MOCK_MODE) return null;  // mock mode never refreshes
  try {
    const { data } = await client.post('/auth/refresh', {});
    // Save the new access token immediately
    if (data?.access_token) {
      localStorage.setItem('access_token', data.access_token);
    }
    return adaptAuthResponse(data);
  } catch {
    return null;
  }
}

// ─── Logout (revoke refresh token server-side + clear cookie) ─────────────────

export async function logoutApi(): Promise<void> {
  if (MOCK_MODE) return;
  try {
    await client.post('/auth/logout', {});
  } catch {
    // Always silent — logout proceeds client-side regardless
  }
}

// ─── Email verification ────────────────────────────────────────────────────────

export async function verifyEmailToken(token: string): Promise<Rep> {
  const { data } = await client.post('/auth/verify-email', { token });
  return adaptRep(data);
}

export async function resendVerificationEmail(): Promise<void> {
  await client.post('/auth/resend-verification', {});
}

// ─── 2FA verification (email OTP after password) ──────────────────────────────
export async function verify2fa(challenge_id: string, code: string): Promise<AuthResponse> {  if (MOCK_MODE) {
    await mockDelay(null);
    return MOCK_REP_AUTH;
  }
  const { data } = await client.post('/auth/2fa/verify', { challenge_id, code });
  return adaptAuthResponse(data);
}