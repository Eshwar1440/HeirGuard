import { API_URL } from '../config';

export class ApiError extends Error {
  constructor(public status: number, message: string, public body?: unknown) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, init);
  const text = await res.text();
  const body = text ? safeJson(text) : undefined;
  if (!res.ok) {
    const detail = (body as { detail?: unknown })?.detail;
    throw new ApiError(res.status, typeof detail === 'string' ? detail : `Request failed (${res.status})`, body);
  }
  return body as T;
}

function safeJson(text: string): unknown {
  try { return JSON.parse(text); } catch { return text; }
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: body === undefined ? undefined : JSON.stringify(body),
});

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) => request<T>(path, json('POST', body)),
  upload: <T>(path: string, files: File[]) => {
    const fd = new FormData();
    files.forEach((f) => fd.append('files', f));
    return request<T>(path, { method: 'POST', body: fd });
  },
};
