import test from 'node:test';
import assert from 'node:assert/strict';
import {
  analyzePaper,
  chatWithDataset,
  checkProtocol,
  discoverCohort,
  profileDataset,
} from '../src/api.ts';

function mockFetch(handler: (input: string, init?: RequestInit) => Response | Promise<Response>) {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = ((input: string | URL | Request, init?: RequestInit) =>
    handler(String(input), init)) as typeof fetch;

  return () => {
    globalThis.fetch = originalFetch;
  };
}

test('profileDataset posts uploaded files to the FastAPI dataset profile endpoint', async () => {
  const restore = mockFetch((input, init) => {
    assert.equal(input, 'http://api.test/datasets/profile');
    assert.equal(init?.method, 'POST');
    assert.equal(init?.body instanceof FormData, true);
    assert.equal((init?.headers as Record<string, string> | undefined)?.['Content-Type'], undefined);

    return Response.json({
      rows: 2,
      columns: ['PatientID'],
      missing_values: {},
      duplicate_records: 0,
      invalid_ages: 0,
      outliers: {},
      quality_score: 100,
      recommended_actions: [],
    });
  });

  try {
    const response = await profileDataset(new Blob(['PatientID\nCP-1'], { type: 'text/csv' }), 'http://api.test');
    assert.equal(response.rows, 2);
    assert.equal(response.quality_score, 100);
  } finally {
    restore();
  }
});

test('analyzePaper posts uploaded paper files to the paper analysis endpoint', async () => {
  const restore = mockFetch((input, init) => {
    assert.equal(input, 'http://api.test/papers/analyze');
    assert.equal(init?.method, 'POST');
    assert.equal(init?.body instanceof FormData, true);

    return Response.json({
      filename: 'study.pdf',
      study_objective: 'Objective',
      population: 'Population',
      methods: 'Methods',
      results: 'Results',
      limitations: 'Limitations',
    });
  });

  try {
    const response = await analyzePaper(new Blob(['pdf'], { type: 'application/pdf' }), 'http://api.test');
    assert.equal(response.results, 'Results');
  } finally {
    restore();
  }
});

test('discoverCohort posts JSON filters to the cohort endpoint', async () => {
  const restore = mockFetch(async (input, init) => {
    assert.equal(input, 'http://api.test/cohorts/discover');
    assert.equal(init?.method, 'POST');
    assert.equal((init?.headers as Record<string, string>)['Content-Type'], 'application/json');
    assert.deepEqual(JSON.parse(String(init?.body)), { minimum_age: 60 });

    return Response.json({
      filters: { minimum_age: 60 },
      matching_patients: 3,
      population_share: 17.65,
      top_characteristics: ['Age > 60'],
      patients: [],
    });
  });

  try {
    const response = await discoverCohort({ minimum_age: 60 }, 'http://api.test');
    assert.equal(response.matching_patients, 3);
  } finally {
    restore();
  }
});

test('checkProtocol and chatWithDataset post expected JSON payloads', async () => {
  const seen: string[] = [];
  const restore = mockFetch((input, init) => {
    seen.push(input);
    const body = JSON.parse(String(init?.body));

    if (input.endsWith('/protocols/check')) {
      assert.equal(body.criteria, 'Adults with Type 2 Diabetes');
      return Response.json({
        criteria: body.criteria,
        eligible_patients: 4,
        ineligible_patients: 13,
        major_exclusion_reasons: ['Age outside 18-65'],
      });
    }

    assert.equal(body.question, 'What is the hypertension overlap?');
    return Response.json({
      question: body.question,
      answer: '44% overlap',
      sources: ['Cardiovascular_Phase_II.csv'],
    });
  });

  try {
    const protocol = await checkProtocol('Adults with Type 2 Diabetes', 'http://api.test');
    const chat = await chatWithDataset('What is the hypertension overlap?', 'http://api.test');

    assert.equal(protocol.eligible_patients, 4);
    assert.equal(chat.answer, '44% overlap');
    assert.deepEqual(seen, ['http://api.test/protocols/check', 'http://api.test/chat']);
  } finally {
    restore();
  }
});

test('API client throws a useful error for non-2xx responses', async () => {
  const restore = mockFetch(() => new Response('Server error', { status: 500, statusText: 'Internal Server Error' }));

  try {
    await assert.rejects(
      () => chatWithDataset('hello', 'http://api.test'),
      /ClinicalPilot API 500: Internal Server Error/,
    );
  } finally {
    restore();
  }
});
