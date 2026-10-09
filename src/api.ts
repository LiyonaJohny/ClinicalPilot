type UploadableFile = Blob & { name?: string };

const metaEnv = (import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env;

export const API_BASE_URL = metaEnv?.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';

export type DatasetProfile = {
  rows: number;
  columns: string[];
  missing_values: Record<string, number>;
  duplicate_records: number;
  invalid_ages: number;
  outliers: Record<string, number>;
  quality_score: number;
  recommended_actions: string[];
};

export type CohortDiscoveryResponse = {
  filters: Record<string, unknown>;
  matching_patients: number;
  population_share: number;
  top_characteristics: string[];
  patients: Array<Record<string, unknown>>;
};

export type ProtocolCheckResponse = {
  criteria: string;
  eligible_patients: number;
  ineligible_patients: number;
  major_exclusion_reasons: string[];
};

export type PaperSource = {
  chunk_id: number;
  paper: string;
  chunk_index: number;
  score: number;
  excerpt: string;
};

export type PaperAnalysisResponse = {
  filename: string;
  study_objective: string;
  population: string;
  methods: string;
  results: string;
  limitations: string;
  paper_id?: number;
  chunks_indexed?: number;
  sources?: PaperSource[];
};

export type ChatToolCall = {
  name: string;
  input: Record<string, unknown>;
  is_error: boolean;
};

export type ChatResponse = {
  question: string;
  answer: string;
  sources: string[];
  tool_calls?: ChatToolCall[];
};

export type ChatStreamEvent =
  | { event: 'token'; data: { text: string } }
  | { event: 'tool_call'; data: { id: string; name: string; input: Record<string, unknown> } }
  | { event: 'tool_result'; data: { id: string; name: string; is_error: boolean; error?: string } }
  | { event: 'done'; data: ChatResponse }
  | { event: 'error'; data: { detail: string } };

export type SavedReportResponse = {
  id: number;
  status: 'saved';
  title: string;
  dataset_name: string;
  content_length: number;
  metadata: Record<string, unknown>;
};

async function requestJson<T>(path: string, init?: RequestInit, baseUrl = API_BASE_URL): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    headers: init?.body instanceof FormData ? init.headers : { 'Content-Type': 'application/json', ...init?.headers },
  });

  if (!response.ok) {
    throw new Error(`ClinicalPilot API ${response.status}: ${response.statusText}`);
  }

  return response.json() as Promise<T>;
}

export function profileDataset(file: UploadableFile, baseUrl?: string) {
  const formData = new FormData();
  formData.append('file', file, file.name ?? 'dataset.csv');

  return requestJson<DatasetProfile>('/datasets/profile', {
    method: 'POST',
    body: formData,
  }, baseUrl);
}

export function discoverCohort(filters: Record<string, unknown>, baseUrl?: string) {
  return requestJson<CohortDiscoveryResponse>('/cohorts/discover', {
    method: 'POST',
    body: JSON.stringify(filters),
  }, baseUrl);
}

export function checkProtocol(criteria: string, baseUrl?: string) {
  return requestJson<ProtocolCheckResponse>('/protocols/check', {
    method: 'POST',
    body: JSON.stringify({ criteria }),
  }, baseUrl);
}

export function analyzePaper(file: UploadableFile, baseUrl?: string) {
  const formData = new FormData();
  formData.append('file', file, file.name ?? 'paper.pdf');

  return requestJson<PaperAnalysisResponse>('/papers/analyze', {
    method: 'POST',
    body: formData,
  }, baseUrl);
}

export function chatWithDataset(question: string, baseUrl?: string) {
  return requestJson<ChatResponse>('/chat', {
    method: 'POST',
    body: JSON.stringify({ question }),
  }, baseUrl);
}

export function parseSseEvents(buffer: string): { events: ChatStreamEvent[]; rest: string } {
  const blocks = buffer.replace(/\r\n/g, '\n').split('\n\n');
  const rest = blocks.pop() ?? '';
  const events: ChatStreamEvent[] = [];

  for (const block of blocks) {
    let event = 'message';
    const data: string[] = [];
    for (const line of block.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim();
      else if (line.startsWith('data:')) data.push(line.slice(5).trimStart());
    }
    if (data.length) {
      events.push({ event, data: JSON.parse(data.join('\n')) } as ChatStreamEvent);
    }
  }

  return { events, rest };
}

export async function streamChat(
  question: string,
  onEvent?: (event: ChatStreamEvent) => void,
  baseUrl = API_BASE_URL,
): Promise<ChatResponse> {
  const response = await fetch(`${baseUrl}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ question }),
  });

  if (!response.ok) {
    throw new Error(`ClinicalPilot API ${response.status}: ${response.statusText}`);
  }
  if (!response.body) {
    throw new Error('ClinicalPilot API returned an empty stream');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  for (;;) {
    const { done, value } = await reader.read();
    buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
    // A final event may arrive without its trailing blank line when the stream closes.
    const parsed = parseSseEvents(done ? `${buffer}\n\n` : buffer);
    buffer = parsed.rest;

    for (const event of parsed.events) {
      onEvent?.(event);
      if (event.event === 'done') return event.data;
      if (event.event === 'error') throw new Error(`ClinicalPilot API error: ${event.data.detail}`);
    }
    if (done) break;
  }

  throw new Error('ClinicalPilot API stream ended without an answer');
}

export function saveGeneratedReport(payload: {
  title: string;
  dataset_name: string;
  content: string;
  metadata: Record<string, unknown>;
}, baseUrl?: string) {
  return requestJson<SavedReportResponse>('/reports', {
    method: 'POST',
    body: JSON.stringify(payload),
  }, baseUrl);
}
