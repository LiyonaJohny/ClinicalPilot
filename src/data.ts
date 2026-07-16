export type NavKey = 'dashboard' | 'datasets' | 'papers' | 'cohorts' | 'reports' | 'simulator';

export const enrollmentData = [
  { month: 'Jan', patients: 320, target: 280 },
  { month: 'Feb', patients: 580, target: 550 },
  { month: 'Mar', patients: 890, target: 780 },
  { month: 'Apr', patients: 1250, target: 1120 },
  { month: 'May', patients: 1700, target: 1540 },
  { month: 'Jun', patients: 2143, target: 1900 },
];

export const ageData = [
  { range: '18-30', value: 182 },
  { range: '31-45', value: 406 },
  { range: '46-60', value: 721 },
  { range: '61-75', value: 596 },
  { range: '76+', value: 238 },
];

export const diseaseData = [
  { name: 'Hypertension', value: 42, color: '#00796b' },
  { name: 'Diabetes', value: 38, color: '#7cebd8' },
  { name: 'COPD', value: 9, color: '#e0b54c' },
  { name: 'Other', value: 11, color: '#c7cbd1' },
];

export const qualityIssues = [
  {
    label: 'Invalid Entries',
    value: '1 Entry',
    detail: 'Age = 250 detected in row 142. Outside biological range.',
    severity: 'high',
  },
  {
    label: 'Missing Values',
    value: '15 BP Missing',
    detail: "Missing blood pressure readings in cohort 'Alpha-Beta'. Confidence score: 88%.",
    severity: 'medium',
  },
  {
    label: 'Duplicates',
    value: '2 PatientIDs',
    detail: 'Conflicting entries for PatientID #9901 and #9904. Review required.',
    severity: 'neutral',
  },
];

export const patientRows = [
  { id: '#9901', age: 45, gender: 'M', diagnosis: 'Hypertension', bp: '140/90', quality: 'Clean' },
  { id: '#9902', age: 250, gender: 'F', diagnosis: 'Hypotension', bp: '90/60', quality: 'Invalid' },
  { id: '#9903', age: 32, gender: 'M', diagnosis: 'N/A', bp: 'Missing', quality: 'Missing' },
  { id: '#9904', age: 58, gender: 'M', diagnosis: 'Diabetes T2', bp: '120/80', quality: 'Duplicate' },
  { id: '#9905', age: 61, gender: 'F', diagnosis: 'Arrhythmia', bp: '135/85', quality: 'Clean' },
];

export const cohortRows = [
  { id: '#CP-88421', ageSex: '68 / M', diagnosis: ['Diabetes T2', 'Hypertension'], bp: '142 / 88', lab: '24 Oct 2023', match: 98 },
  { id: '#CP-91203', ageSex: '72 / F', diagnosis: ['Diabetes T2'], bp: '155 / 92', lab: '12 Nov 2023', match: 94 },
  { id: '#CP-77412', ageSex: '65 / M', diagnosis: ['Diabetes T2', 'Kidney Disease'], bp: '148 / 85', lab: '02 Jan 2024', match: 91 },
  { id: '#CP-11409', ageSex: '81 / F', diagnosis: ['Diabetes T2'], bp: '140 / 80', lab: '15 Dec 2023', match: 89 },
];

export const paperInsights = [
  {
    title: 'Study Objective',
    body: 'Evaluate the efficacy and safety of novel Compound-X versus standard of care in patients with chronic heart failure and reduced ejection fraction.',
    tone: 'primary',
  },
  {
    title: 'Population',
    body: 'N=12,450. Participants aged 45-80 with NYHA Class II-IV heart failure. 45% female, 55% male.',
    tone: 'default',
  },
  {
    title: 'Methods',
    body: 'Double-blind, randomized controlled trial across 45 clinical sites. Median follow-up period of 24 months.',
    tone: 'default',
  },
  {
    title: 'Key Results',
    body: '18% relative risk reduction in primary composite endpoint. p < 0.001. No significant increase in adverse renal events.',
    tone: 'success',
  },
  {
    title: 'Limitations',
    body: 'Under-representation of participants over 80 years of age. Limited data on long-term outcomes beyond 3 years.',
    tone: 'danger',
  },
];

export const activities = [
  'Dataset Upload: Phase II_Vitals_Final.csv',
  'Study Report Generated: Q2 Enrollment Analysis',
  'New AI Chat Insight Saved',
  'Data Integrity Alert: Site 04',
];
