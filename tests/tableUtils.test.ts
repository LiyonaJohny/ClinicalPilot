import test from 'node:test';
import assert from 'node:assert/strict';
import { clinicalAnalytics } from '../src/clinicalData.ts';
import { filterRows, getVisibleRows, paginateRows, sortRows } from '../src/tableUtils.ts';

test('given patient rows, filterRows searches across every displayed column', () => {
  assert.equal(filterRows(clinicalAnalytics.patientRows, 'CP-9902').at(0)?.id, 'CP-9902');
  assert.equal(filterRows(clinicalAnalytics.patientRows, 'hypotension').at(0)?.diagnosis, 'Hypotension');
  assert.equal(filterRows(clinicalAnalytics.patientRows, 'missing').some((row) => row.bp === 'Missing'), true);
});

test('given cohort rows, filterRows searches array values such as diagnoses', () => {
  const kidneyRows = filterRows(clinicalAnalytics.cohortRows, 'kidney');

  assert.equal(kidneyRows.length, 1);
  assert.equal(kidneyRows[0].id, 'CP-77412');
});

test('given rows and a numeric key, sortRows orders numbers in both directions', () => {
  const ascending = sortRows(clinicalAnalytics.patientRows, 'age', 'asc');
  const descending = sortRows(clinicalAnalytics.patientRows, 'age', 'desc');

  assert.equal(ascending[0].age, 32);
  assert.equal(descending[0].age, 250);
});

test('given rows and a string key, sortRows orders strings case-insensitively', () => {
  const sorted = sortRows(clinicalAnalytics.patientRows, 'diagnosis', 'asc');

  assert.equal(sorted[0].diagnosis, 'Arrhythmia');
});

test('given rows and pagination settings, paginateRows returns the requested page', () => {
  const result = paginateRows(clinicalAnalytics.patientRows, 1, 3);

  assert.equal(result.page, 1);
  assert.deepEqual(result.rows.map((row) => row.id), ['CP-9904', 'CP-9904', 'CP-9905']);
});

test('given a page beyond available rows, getVisibleRows clamps to the last valid page', () => {
  const result = getVisibleRows({
    rows: clinicalAnalytics.cohortRows,
    searchTerm: '',
    sortKey: 'match',
    sortDirection: 'desc',
    page: 10,
    rowsPerPage: 3,
  });

  assert.equal(result.page, 1);
  assert.equal(result.visibleRows.length, 1);
  assert.equal(result.total, clinicalAnalytics.cohortRows.length);
});

test('given a narrowed search, getVisibleRows reports filtered totals before pagination', () => {
  const result = getVisibleRows({
    rows: clinicalAnalytics.cohortRows,
    searchTerm: 'diabetes',
    sortKey: 'id',
    sortDirection: 'asc',
    page: 0,
    rowsPerPage: 2,
  });

  assert.equal(result.total, clinicalAnalytics.cohortRows.length);
  assert.equal(result.visibleRows.length, 2);
});
