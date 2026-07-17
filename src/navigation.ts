import type { NavKey } from './data';

export const navItems = [
  { key: 'dashboard', label: 'Research Dashboard' },
  { key: 'datasets', label: 'Datasets' },
  { key: 'papers', label: 'Paper Analyzer' },
  { key: 'cohorts', label: 'Cohort Discovery' },
  { key: 'reports', label: 'Study Reports' },
  { key: 'simulator', label: 'Digital Twin' },
] as const satisfies ReadonlyArray<{ key: NavKey; label: string }>;

export const pageTitles: Record<NavKey, string> = {
  dashboard: 'Research Dashboard',
  datasets: 'Dataset',
  papers: 'Paper Analyzer',
  cohorts: 'Cohort Discovery',
  reports: 'Study Report Generator',
  simulator: 'Digital Twin Simulator',
};

export function getPageTitle(active: NavKey, datasetName: string) {
  return active === 'datasets' ? `${pageTitles.datasets}: ${datasetName}` : pageTitles[active];
}
