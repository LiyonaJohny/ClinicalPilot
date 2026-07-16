import test from 'node:test';
import assert from 'node:assert/strict';
import { clinicalAnalytics, clinicalDataset } from '../src/clinicalData.ts';

test('given the packaged clinical dataset, it computes core population metrics', () => {
  assert.equal(clinicalDataset.length, 18);
  assert.equal(clinicalAnalytics.totalRows, 18);
  assert.equal(clinicalAnalytics.totalPatients, 17);
  assert.equal(clinicalAnalytics.averageAge, 59.3);
  assert.equal(clinicalAnalytics.genderFemalePercent, 53);
});

test('given quality defects in source data, it identifies missing, duplicate, and invalid records', () => {
  assert.equal(clinicalAnalytics.missingBpCount, 3);
  assert.equal(clinicalAnalytics.missingDiagnosisCount, 1);
  assert.equal(clinicalAnalytics.duplicateCount, 1);
  assert.deepEqual(clinicalAnalytics.duplicateIds, ['CP-9904']);
  assert.equal(clinicalAnalytics.invalidAgeCount, 1);
  assert.equal(clinicalAnalytics.qualityScore, 86);
});

test('given diabetes and hypertension flags, it calculates overlap and cohort discovery outputs', () => {
  assert.equal(clinicalAnalytics.diabeticHypertensionPercent, 44);
  assert.equal(clinicalAnalytics.cohortMatches.length, 5);
  assert.equal(clinicalAnalytics.cohortMatchPercent, 29.41);
  assert.equal(clinicalAnalytics.protocolEligibleCount, 4);
  assert.equal(clinicalAnalytics.protocolIneligibleCount, 13);
});

test('given treatment outcomes, it computes report-ready efficacy metrics', () => {
  assert.equal(clinicalAnalytics.treatmentEffectiveness, 100);
  assert.equal(clinicalAnalytics.enrollmentData.at(-1)?.patients, clinicalAnalytics.totalPatients);
  assert.equal(clinicalAnalytics.patientRows.some((row) => row.quality === 'Invalid'), true);
  assert.equal(clinicalAnalytics.patientRows.some((row) => row.quality === 'Duplicate'), true);
});
