import test from 'node:test';
import assert from 'node:assert/strict';
import {
  analyzePaper,
  chatWithDataset,
  checkProtocol,
  discoverCohort,
  parseSseEvents,
  profileDataset,
  saveGeneratedReport,
  streamChat,
  type ChatStreamEvent,
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

test('saveGeneratedReport posts generated report content to the persistence endpoint', async () => {
  const restore = mockFetch((input, init) => {
    assert.equal(input, 'http://api.test/reports');
    assert.equal(init?.method, 'POST');
    assert.equal((init?.headers as Record<string, string>)['Content-Type'], 'application/json');
    assert.deepEqual(JSON.parse(String(init?.body)), {
      title: 'Q3 Report',
      dataset_name: 'Cardiovascular_Phase_II.csv',
      content: 'Report body',
      metadata: { qualityScore: 86 },
    });

    return Response.json({
      id: 12,
      status: 'saved',
      title: 'Q3 Report',
      dataset_name: 'Cardiovascular_Phase_II.csv',
      content_length: 11,
      metadata: { qualityScore: 86 },
    });
  });

  try {
    const response = await saveGeneratedReport({
      title: 'Q3 Report',
      dataset_name: 'Cardiovascular_Phase_II.csv',
      content: 'Report body',
      metadata: { qualityScore: 86 },
    }, 'http://api.test');

    assert.equal(response.id, 12);
    assert.equal(response.status, 'saved');
  } finally {
    restore();
  }
});

function sseResponse(chunks: string[]) {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
}

const doneEvent = {
  question: 'How many patients have hypertension?',
  answer: '8 patients have hypertension.',
  sources: ['Cardiovascular_Phase_II.csv'],
  tool_calls: [{ name: 'discover_cohort', input: { filters: { hypertension: true } }, is_error: false }],
};

test('parseSseEvents returns complete events and keeps the unfinished remainder', () => {
  const { events, rest } = parseSseEvents(
    'event: token\ndata: {"text":"8 "}\n\nevent: token\r\ndata: {"text":"patients"}\r\n\r\nevent: done\ndata: {"ans',
  );

  assert.deepEqual(events, [
    { event: 'token', data: { text: '8 ' } },
    { event: 'token', data: { text: 'patients' } },
  ]);
  assert.equal(rest, 'event: done\ndata: {"ans');
});

test('streamChat posts the question and reports events as they arrive', async () => {
  const stream = [
    'event: tool_call\ndata: {"id":"toolu_1","name":"discover_cohort","input":{"filters":{"hypertension":true}}}\n\n',
    'event: tool_result\ndata: {"id":"toolu_1","name":"discover_cohort","is_error":false}\n\n',
    'event: token\ndata: {"text":"8 patients "}\n\n',
    'event: token\ndata: {"text":"have hypertension."}\n\n',
    `event: done\ndata: ${JSON.stringify(doneEvent)}\n\n`,
  ].join('');
  // Split at arbitrary offsets so events straddle chunk boundaries.
  const chunks = [stream.slice(0, 37), stream.slice(37, 150), stream.slice(150, 151), stream.slice(151)];
  const restore = mockFetch((input, init) => {
    assert.equal(input, 'http://api.test/chat/stream');
    assert.equal(init?.method, 'POST');
    assert.deepEqual(JSON.parse(String(init?.body)), { question: doneEvent.question });
    return sseResponse(chunks);
  });

  try {
    const seen: ChatStreamEvent[] = [];
    const response = await streamChat(doneEvent.question, (event) => seen.push(event), 'http://api.test');

    assert.deepEqual(seen.map((event) => event.event), ['tool_call', 'tool_result', 'token', 'token', 'done']);
    assert.equal(
      seen.map((event) => (event.event === 'token' ? event.data.text : '')).join(''),
      '8 patients have hypertension.',
    );
    assert.deepEqual(response, doneEvent);
  } finally {
    restore();
  }
});

test('streamChat reads a final event that has no trailing blank line', async () => {
  const restore = mockFetch(() => sseResponse([`event: done\ndata: ${JSON.stringify(doneEvent)}`]));

  try {
    assert.deepEqual(await streamChat(doneEvent.question, undefined, 'http://api.test'), doneEvent);
  } finally {
    restore();
  }
});

test('streamChat rejects on error events, incomplete streams, and non-2xx responses', async () => {
  const cases: Array<[Response, RegExp]> = [
    [sseResponse(['event: error\ndata: {"detail":"The model declined to answer this question."}\n\n']), /ClinicalPilot API error: The model declined/],
    [sseResponse(['event: token\ndata: {"text":"8 "}\n\n']), /stream ended without an answer/],
    [new Response('{"detail":"No Anthropic credentials found."}', { status: 503, statusText: 'Service Unavailable' }), /ClinicalPilot API 503: Service Unavailable/],
  ];

  for (const [response, expected] of cases) {
    const restore = mockFetch(() => response);
    try {
      await assert.rejects(() => streamChat('hello', undefined, 'http://api.test'), expected);
    } finally {
      restore();
    }
  }
});
