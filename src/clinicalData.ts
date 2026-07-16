export type ClinicalRecord = {
  patientId: string;
  age: number;
  gender: 'M' | 'F';
  race: string;
  diagnosis: string;
  systolicBP: number | null;
  diastolicBP: number | null;
  treatment: 'Standard Care' | 'Compound-X';
  outcome: 'Controlled' | 'Uncontrolled' | 'Readmitted';
  site: string;
  enrolledMonth: 'Jan' | 'Feb' | 'Mar' | 'Apr' | 'May' | 'Jun';
  lastLabDate: string;
  diabetesType2: boolean;
  hypertension: boolean;
  kidneyDisease: boolean;
};

export const clinicalDataset: ClinicalRecord[] = [
  { patientId: 'CP-9901', age: 45, gender: 'M', race: 'White', diagnosis: 'Hypertension', systolicBP: 140, diastolicBP: 90, treatment: 'Standard Care', outcome: 'Uncontrolled', site: 'NYC-01', enrolledMonth: 'Jan', lastLabDate: '24 Oct 2023', diabetesType2: false, hypertension: true, kidneyDisease: false },
  { patientId: 'CP-9902', age: 250, gender: 'F', race: 'Black', diagnosis: 'Hypotension', systolicBP: 90, diastolicBP: 60, treatment: 'Standard Care', outcome: 'Controlled', site: 'NYC-01', enrolledMonth: 'Jan', lastLabDate: '01 Nov 2023', diabetesType2: false, hypertension: false, kidneyDisease: false },
  { patientId: 'CP-9903', age: 32, gender: 'M', race: 'Hispanic', diagnosis: 'N/A', systolicBP: null, diastolicBP: null, treatment: 'Compound-X', outcome: 'Controlled', site: 'LON-04', enrolledMonth: 'Feb', lastLabDate: '11 Nov 2023', diabetesType2: false, hypertension: false, kidneyDisease: false },
  { patientId: 'CP-9904', age: 58, gender: 'M', race: 'Asian', diagnosis: 'Diabetes T2', systolicBP: 120, diastolicBP: 80, treatment: 'Compound-X', outcome: 'Controlled', site: 'NYC-01', enrolledMonth: 'Feb', lastLabDate: '14 Nov 2023', diabetesType2: true, hypertension: false, kidneyDisease: false },
  { patientId: 'CP-9904', age: 58, gender: 'M', race: 'Asian', diagnosis: 'Diabetes T2', systolicBP: 120, diastolicBP: 80, treatment: 'Compound-X', outcome: 'Controlled', site: 'NYC-01', enrolledMonth: 'Feb', lastLabDate: '14 Nov 2023', diabetesType2: true, hypertension: false, kidneyDisease: false },
  { patientId: 'CP-9905', age: 61, gender: 'F', race: 'White', diagnosis: 'Arrhythmia', systolicBP: 135, diastolicBP: 85, treatment: 'Standard Care', outcome: 'Controlled', site: 'LON-04', enrolledMonth: 'Mar', lastLabDate: '20 Nov 2023', diabetesType2: false, hypertension: false, kidneyDisease: false },
  { patientId: 'CP-88421', age: 68, gender: 'M', race: 'Black', diagnosis: 'Diabetes T2; Hypertension', systolicBP: 142, diastolicBP: 88, treatment: 'Compound-X', outcome: 'Controlled', site: 'NYC-01', enrolledMonth: 'Mar', lastLabDate: '24 Oct 2023', diabetesType2: true, hypertension: true, kidneyDisease: false },
  { patientId: 'CP-91203', age: 72, gender: 'F', race: 'White', diagnosis: 'Diabetes T2', systolicBP: 155, diastolicBP: 92, treatment: 'Standard Care', outcome: 'Uncontrolled', site: 'LON-04', enrolledMonth: 'Mar', lastLabDate: '12 Nov 2023', diabetesType2: true, hypertension: false, kidneyDisease: false },
  { patientId: 'CP-77412', age: 65, gender: 'M', race: 'Hispanic', diagnosis: 'Diabetes T2; Kidney Disease', systolicBP: 148, diastolicBP: 85, treatment: 'Standard Care', outcome: 'Readmitted', site: 'SFO-07', enrolledMonth: 'Apr', lastLabDate: '02 Jan 2024', diabetesType2: true, hypertension: false, kidneyDisease: true },
  { patientId: 'CP-11409', age: 81, gender: 'F', race: 'White', diagnosis: 'Diabetes T2', systolicBP: 140, diastolicBP: 80, treatment: 'Compound-X', outcome: 'Controlled', site: 'BER-02', enrolledMonth: 'Apr', lastLabDate: '15 Dec 2023', diabetesType2: true, hypertension: false, kidneyDisease: false },
  { patientId: 'CP-10011', age: 54, gender: 'F', race: 'Asian', diagnosis: 'Hypertension', systolicBP: 152, diastolicBP: 91, treatment: 'Compound-X', outcome: 'Controlled', site: 'NYC-01', enrolledMonth: 'Apr', lastLabDate: '08 Jan 2024', diabetesType2: false, hypertension: true, kidneyDisease: false },
  { patientId: 'CP-10012', age: 49, gender: 'M', race: 'Black', diagnosis: 'Diabetes T2; Hypertension', systolicBP: null, diastolicBP: null, treatment: 'Compound-X', outcome: 'Controlled', site: 'LON-04', enrolledMonth: 'May', lastLabDate: '13 Jan 2024', diabetesType2: true, hypertension: true, kidneyDisease: false },
  { patientId: 'CP-10013', age: 63, gender: 'F', race: 'White', diagnosis: 'COPD', systolicBP: 128, diastolicBP: 78, treatment: 'Standard Care', outcome: 'Controlled', site: 'SFO-07', enrolledMonth: 'May', lastLabDate: '15 Jan 2024', diabetesType2: false, hypertension: false, kidneyDisease: false },
  { patientId: 'CP-10014', age: 59, gender: 'M', race: 'Hispanic', diagnosis: 'Diabetes T2; Hypertension', systolicBP: 146, diastolicBP: 87, treatment: 'Compound-X', outcome: 'Controlled', site: 'NYC-01', enrolledMonth: 'May', lastLabDate: '22 Jan 2024', diabetesType2: true, hypertension: true, kidneyDisease: false },
  { patientId: 'CP-10015', age: 77, gender: 'F', race: 'White', diagnosis: 'Hypertension', systolicBP: 164, diastolicBP: 94, treatment: 'Standard Care', outcome: 'Readmitted', site: 'BER-02', enrolledMonth: 'Jun', lastLabDate: '29 Jan 2024', diabetesType2: false, hypertension: true, kidneyDisease: false },
  { patientId: 'CP-10016', age: 52, gender: 'F', race: 'Asian', diagnosis: 'Diabetes T2', systolicBP: 118, diastolicBP: 76, treatment: 'Compound-X', outcome: 'Controlled', site: 'NYC-01', enrolledMonth: 'Jun', lastLabDate: '02 Feb 2024', diabetesType2: true, hypertension: false, kidneyDisease: false },
  { patientId: 'CP-10017', age: 70, gender: 'M', race: 'Black', diagnosis: 'Diabetes T2; Hypertension', systolicBP: 170, diastolicBP: 96, treatment: 'Standard Care', outcome: 'Uncontrolled', site: 'LON-04', enrolledMonth: 'Jun', lastLabDate: '08 Feb 2024', diabetesType2: true, hypertension: true, kidneyDisease: false },
  { patientId: 'CP-10018', age: 43, gender: 'F', race: 'Hispanic', diagnosis: 'Hypertension', systolicBP: null, diastolicBP: null, treatment: 'Compound-X', outcome: 'Controlled', site: 'SFO-07', enrolledMonth: 'Jun', lastLabDate: '10 Feb 2024', diabetesType2: false, hypertension: true, kidneyDisease: false },
];

const months: ClinicalRecord['enrolledMonth'][] = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'];
const diseaseColors: Record<string, string> = {
  Hypertension: '#00796b',
  'Diabetes T2': '#7cebd8',
  COPD: '#e0b54c',
  Other: '#c7cbd1',
};

const uniquePatients = Array.from(new Map(clinicalDataset.map((row) => [row.patientId, row])).values());
const duplicateIds = clinicalDataset
  .map((row) => row.patientId)
  .filter((id, index, ids) => ids.indexOf(id) !== index);

const validAges = uniquePatients.map((row) => row.age).filter((age) => age > 0 && age <= 120);
const diabeticPatients = uniquePatients.filter((row) => row.diabetesType2);
const diabeticWithHypertension = diabeticPatients.filter((row) => row.hypertension);
const cohortMatches = uniquePatients.filter(
  (row) => row.age > 60 && row.diabetesType2 && (row.systolicBP ?? 0) >= 140,
);
const protocolEligible = uniquePatients.filter(
  (row) => row.age >= 18 && row.age <= 65 && row.diabetesType2 && !row.kidneyDisease,
);

function percent(part: number, whole: number) {
  return whole === 0 ? 0 : Math.round((part / whole) * 100);
}

function diseaseCount(label: string) {
  if (label === 'Hypertension') return uniquePatients.filter((row) => row.hypertension).length;
  if (label === 'Diabetes T2') return uniquePatients.filter((row) => row.diabetesType2).length;
  if (label === 'COPD') return uniquePatients.filter((row) => row.diagnosis.includes('COPD')).length;
  return uniquePatients.filter((row) => !row.hypertension && !row.diabetesType2 && !row.diagnosis.includes('COPD')).length;
}

function getQuality(row: ClinicalRecord) {
  if (row.age > 120 || row.age < 0) return 'Invalid';
  if (row.systolicBP === null || row.diastolicBP === null || row.diagnosis === 'N/A') return 'Missing';
  if (duplicateIds.includes(row.patientId)) return 'Duplicate';
  return 'Clean';
}

export const clinicalAnalytics = {
  datasetName: 'Cardiovascular_Phase_II.csv',
  datasetPath: 'sample_data/cardiovascular_phase_ii.csv',
  totalRows: clinicalDataset.length,
  totalPatients: uniquePatients.length,
  averageAge: Number((validAges.reduce((sum, age) => sum + age, 0) / validAges.length).toFixed(1)),
  genderFemalePercent: percent(uniquePatients.filter((row) => row.gender === 'F').length, uniquePatients.length),
  diabeticHypertensionPercent: percent(diabeticWithHypertension.length, diabeticPatients.length),
  duplicateCount: duplicateIds.length,
  duplicateIds,
  missingBpCount: clinicalDataset.filter((row) => row.systolicBP === null || row.diastolicBP === null).length,
  missingDiagnosisCount: clinicalDataset.filter((row) => row.diagnosis === 'N/A').length,
  invalidAgeCount: clinicalDataset.filter((row) => row.age > 120 || row.age < 0).length,
  qualityScore: 100 - duplicateIds.length * 3 - clinicalDataset.filter((row) => row.systolicBP === null || row.diagnosis === 'N/A').length * 2 - clinicalDataset.filter((row) => row.age > 120).length * 5,
  treatmentEffectiveness: percent(uniquePatients.filter((row) => row.treatment === 'Compound-X' && row.outcome === 'Controlled').length, uniquePatients.filter((row) => row.treatment === 'Compound-X').length),
  cohortMatches,
  cohortMatchPercent: Number(((cohortMatches.length / uniquePatients.length) * 100).toFixed(2)),
  protocolEligibleCount: protocolEligible.length,
  protocolIneligibleCount: uniquePatients.length - protocolEligible.length,
  enrollmentData: months.map((month, index) => ({
    month,
    patients: uniquePatients.filter((row) => months.indexOf(row.enrolledMonth) <= index).length,
    target: Math.round(((index + 1) / months.length) * uniquePatients.length),
  })),
  ageData: [
    { range: '18-30', value: validAges.filter((age) => age >= 18 && age <= 30).length },
    { range: '31-45', value: validAges.filter((age) => age >= 31 && age <= 45).length },
    { range: '46-60', value: validAges.filter((age) => age >= 46 && age <= 60).length },
    { range: '61-75', value: validAges.filter((age) => age >= 61 && age <= 75).length },
    { range: '76+', value: validAges.filter((age) => age >= 76).length },
  ],
  diseaseData: ['Hypertension', 'Diabetes T2', 'COPD', 'Other'].map((name) => ({
    name,
    value: percent(diseaseCount(name), uniquePatients.length),
    count: diseaseCount(name),
    color: diseaseColors[name],
  })),
  qualityIssues: [
    {
      label: 'Invalid Entries',
      value: `${clinicalDataset.filter((row) => row.age > 120 || row.age < 0).length} Entry`,
      detail: 'Age = 250 detected in patient CP-9902. Outside biological range.',
      severity: 'high' as const,
    },
    {
      label: 'Missing Values',
      value: `${clinicalDataset.filter((row) => row.systolicBP === null || row.diastolicBP === null).length} BP Missing`,
      detail: `${clinicalDataset.filter((row) => row.systolicBP === null || row.diastolicBP === null).length} missing blood pressure readings require imputation or review.`,
      severity: 'medium' as const,
    },
    {
      label: 'Duplicates',
      value: `${duplicateIds.length} PatientID`,
      detail: `PatientID ${duplicateIds.join(', ')} appears more than once. Review required.`,
      severity: 'neutral' as const,
    },
  ],
  patientRows: clinicalDataset.slice(0, 7).map((row) => ({
    id: row.patientId,
    age: row.age,
    gender: row.gender,
    diagnosis: row.diagnosis,
    bp: row.systolicBP === null || row.diastolicBP === null ? 'Missing' : `${row.systolicBP}/${row.diastolicBP}`,
    quality: getQuality(row),
  })),
  cohortRows: cohortMatches.slice(0, 4).map((row, index) => ({
    id: row.patientId,
    ageSex: `${row.age} / ${row.gender}`,
    diagnosis: row.diagnosis.split('; '),
    bp: `${row.systolicBP} / ${row.diastolicBP}`,
    lab: row.lastLabDate,
    match: [98, 94, 91, 89][index] ?? 87,
  })),
};
