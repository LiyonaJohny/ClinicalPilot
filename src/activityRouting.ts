import type { NavKey } from './data';

export type ActivityRoute = {
  activity: string;
  target: NavKey;
  message: string;
};

export const activityRoutes: ActivityRoute[] = [
  {
    activity: 'Dataset Upload: Phase II_Vitals_Final.csv',
    target: 'datasets',
    message: 'Opening dataset quality review for the latest uploaded vitals file.',
  },
  {
    activity: 'Study Report Generated: Q2 Enrollment Analysis',
    target: 'reports',
    message: 'Opening the study report generator for the latest enrollment analysis.',
  },
  {
    activity: 'New AI Chat Insight Saved',
    target: 'reports',
    message: 'Opening study reports where saved AI insights can be reviewed.',
  },
  {
    activity: 'Data Integrity Alert: Site 04',
    target: 'datasets',
    message: 'Opening dataset quality review for the Site 04 integrity alert.',
  },
];

export function getActivityRoute(activity: string) {
  return activityRoutes.find((route) => route.activity === activity) ?? null;
}
