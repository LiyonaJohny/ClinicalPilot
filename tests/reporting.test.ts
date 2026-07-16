import test from 'node:test';
import assert from 'node:assert/strict';
import { buildStudyReportText, defaultStudyReportTitle, toCsv } from '../src/reporting.ts';
import { clinicalAnalytics } from '../src/clinicalData.ts';

test('given rows for export, toCsv emits headers and quoted values', () => {
  const csv = toCsv([
    { PatientID: 'CP-9901', Diagnosis: 'Hypertension', Notes: 'stable' },
    { PatientID: 'CP-9902', Diagnosis: 'Diabetes T2, Hypertension', Notes: 'needs "review"' },
  ]);

  assert.equal(
    csv,
    [
      'PatientID,Diagnosis,Notes',
      '"CP-9901","Hypertension","stable"',
      '"CP-9902","Diabetes T2, Hypertension","needs ""review"""',
    ].join('\n'),
  );
});

test('given no rows for export, toCsv returns an empty file body', () => {
  assert.equal(toCsv([]), '');
});

test('given default report settings, buildStudyReportText includes project metrics and actions', () => {
  const report = buildStudyReportText();

  assert.match(report, new RegExp(defaultStudyReportTitle));
  assert.match(report, new RegExp(`Dataset: ${clinicalAnalytics.datasetName}`));
  assert.match(report, new RegExp(`Total unique patients: ${clinicalAnalytics.totalPatients}`));
  assert.match(report, new RegExp(`Data quality score: ${clinicalAnalytics.qualityScore}%`));
  assert.match(report, /Recommended next actions:/);
});

test('given a custom title, buildStudyReportText uses it as the report heading', () => {
  const report = buildStudyReportText('Custom Cardiovascular Safety Review');

  assert.equal(report.split('\n')[0], 'Custom Cardiovascular Safety Review');
});
