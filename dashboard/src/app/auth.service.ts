import { Injectable } from '@angular/core';

const TOKEN_KEY = 'gw_access_token';
const USER_KEY = 'gw_username';
const PKCE_KEY = 'gw_pkce';
const CLIENT_ID = 'groundwire-dashboard';

@Injectable({ providedIn: 'root' })
export class AuthService {
  issuer(): string {
    return 'http://localhost:8081/realms/groundwire';
  }

  accessToken(): string | null {
    return sessionStorage.getItem(TOKEN_KEY);
  }

  username(): string | null {
    return sessionStorage.getItem(USER_KEY);
  }

  signedIn(): boolean {
    return Boolean(this.accessToken());
  }

  async handleCallback(): Promise<void> {
    const params = new URLSearchParams(window.location.search);
    const code = params.get('code');
    if (!code) {
      return;
    }
    const verifier = sessionStorage.getItem(PKCE_KEY) ?? '';
    const body = new URLSearchParams({
      grant_type: 'authorization_code',
      client_id: CLIENT_ID,
      code,
      redirect_uri: `${window.location.origin}/`,
      code_verifier: verifier,
    });
    const response = await fetch(`${this.issuer()}/protocol/openid-connect/token`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    });
    if (!response.ok) {
      throw new Error('token exchange failed');
    }
    const json = (await response.json()) as { access_token: string };
    sessionStorage.setItem(TOKEN_KEY, json.access_token);
    sessionStorage.setItem(USER_KEY, usernameFromToken(json.access_token));
    sessionStorage.removeItem(PKCE_KEY);
    history.replaceState({}, '', '/');
  }

  async login(): Promise<void> {
    const verifier = randomString();
    sessionStorage.setItem(PKCE_KEY, verifier);
    const challenge = await sha256Base64Url(verifier);
    const url = new URL(`${this.issuer()}/protocol/openid-connect/auth`);
    url.searchParams.set('client_id', CLIENT_ID);
    url.searchParams.set('redirect_uri', `${window.location.origin}/`);
    url.searchParams.set('response_type', 'code');
    url.searchParams.set('scope', 'openid profile');
    url.searchParams.set('code_challenge', challenge);
    url.searchParams.set('code_challenge_method', 'S256');
    window.location.href = url.toString();
  }

  logout(): void {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(USER_KEY);
    const url = new URL(`${this.issuer()}/protocol/openid-connect/logout`);
    url.searchParams.set('client_id', CLIENT_ID);
    url.searchParams.set('post_logout_redirect_uri', `${window.location.origin}/`);
    window.location.href = url.toString();
  }
}

function usernameFromToken(token: string): string {
  try {
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')));
    return payload.preferred_username || payload.sub || 'signalman';
  } catch {
    return 'signalman';
  }
}

function randomString(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(32));
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('');
}

async function sha256Base64Url(input: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(input));
  const bytes = String.fromCharCode(...new Uint8Array(digest));
  return btoa(bytes).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}
