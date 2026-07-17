import test from 'node:test';
import assert from 'node:assert/strict';
import { activities } from '../src/data.ts';
import { activityRoutes, getActivityRoute } from '../src/activityRouting.ts';

test('given recent activities, every activity has a navigation target', () => {
  for (const activity of activities) {
    assert.notEqual(getActivityRoute(activity), null, `${activity} should have a route`);
  }
});

test('given a dataset upload or integrity alert, activity routing opens dataset review', () => {
  assert.equal(getActivityRoute('Dataset Upload: Phase II_Vitals_Final.csv')?.target, 'datasets');
  assert.equal(getActivityRoute('Data Integrity Alert: Site 04')?.target, 'datasets');
});

test('given report or AI insight activity, activity routing opens study reports', () => {
  assert.equal(getActivityRoute('Study Report Generated: Q2 Enrollment Analysis')?.target, 'reports');
  assert.equal(getActivityRoute('New AI Chat Insight Saved')?.target, 'reports');
});

test('given an unknown activity, activity routing returns null', () => {
  assert.equal(getActivityRoute('Unknown activity'), null);
});

test('given configured activity routes, each route includes user feedback text', () => {
  assert.equal(activityRoutes.every((route) => route.message.length > 20), true);
});
