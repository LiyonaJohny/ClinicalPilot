import { clinicalAnalytics } from './clinicalData.ts';

type CsvValue = string | number | boolean | null | undefined;

export const defaultStudyReportTitle = 'Hypertension Efficacy Analysis Q3';

export function toCsv(rows: Array<Record<string, CsvValue>>) {
  if (!rows.length) return '';

  const headers = Object.keys(rows[0]);
  const escape = (value: CsvValue) => `"${String(value ?? '').replaceAll('"', '""')}"`;

  return [headers.join(','), ...rows.map((row) => headers.map((header) => escape(row[header])).join(','))].join('\n');
}

export function buildStudyReportText(title = defaultStudyReportTitle) {
  return [
    title,
    '',
    `Dataset: ${clinicalAnalytics.datasetName}`,
    `Total unique patients: ${clinicalAnalytics.totalPatients}`,
    `Total source rows: ${clinicalAnalytics.totalRows}`,
    `Average age: ${clinicalAnalytics.averageAge}`,
    `Data quality score: ${clinicalAnalytics.qualityScore}%`,
    `Missing BP values: ${clinicalAnalytics.missingBpCount}`,
    `Duplicate PatientIDs: ${clinicalAnalytics.duplicateIds.join(', ') || 'None'}`,
    `Invalid age entries: ${clinicalAnalytics.invalidAgeCount}`,
    `Diabetic-hypertension overlap: ${clinicalAnalytics.diabeticHypertensionPercent}%`,
    `Compound-X controlled outcome rate: ${clinicalAnalytics.treatmentEffectiveness}%`,
    '',
    'Recommended next actions:',
    '- Review duplicate PatientID records.',
    '- Impute or source-verify missing blood pressure values.',
    '- Flag biologically implausible ages before downstream analysis.',
  ].join('\n');
}
