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

export type PaperAnalysisResponse = {
  filename: string;
  study_objective: string;
  population: string;
  methods: string;
  results: string;
  limitations: string;
};

export type ChatResponse = {
  question: string;
  answer: string;
  sources: string[];
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
