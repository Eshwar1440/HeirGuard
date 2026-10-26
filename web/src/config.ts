export const API_URL: string = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/+$/, '') || 'http://localhost:8000';

export const APP_NAME = 'Heir Guard';
export const FOOTER_TEXT = 'Concept prototype. Not affiliated with Charles Schwab. All data is hypothetical.';

// Mirrors backend/hg/config.py. Hypothetical, tunable. Only used to draw the threshold tick.
export const CONFIDENCE_THRESHOLD = 0.85;


// CaseState.status values (backend/hg/schemas.py) that mean the flow is still reading or checking.
// The API answers once a step finishes, so these mostly show while a request is in flight.
export const READING_STATUSES = ['intake', 'reading_documents', 'checking'];
