export const API_URL: string = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/+$/, '') || 'http://localhost:8000';

export const APP_NAME = 'Heir Guard';
// hypothetical: a number in the 555-0100 to 555-0199 range reserved for fiction, not a real line.
export const SPECIALIST_PHONE = '(800) 555-0142';
export const SPECIALIST_HOURS = 'Monday to Friday, 8 a.m. to 8 p.m. ET';

export const FOOTER_TEXT = 'Concept prototype. Not affiliated with Charles Schwab. All data is hypothetical.';

// Mirrors backend/hg/config.py. Hypothetical, tunable. Only used to draw the threshold tick.
export const CONFIDENCE_THRESHOLD = 0.85;


// CaseState.status values (backend/hg/schemas.py) that mean the flow is still reading or checking.
// The API answers once a step finishes, so these mostly show while a request is in flight.
export const READING_STATUSES = ['intake', 'reading_documents', 'checking'];
