import test from 'node:test';
import assert from 'node:assert/strict';
import { getPageTitle, navItems, pageTitles } from '../src/navigation.ts';

test('given the application routes, navItems exposes every primary section once', () => {
  assert.deepEqual(
    navItems.map((item) => item.key),
    ['dashboard', 'datasets', 'papers', 'cohorts', 'reports', 'simulator'],
  );
  assert.equal(new Set(navItems.map((item) => item.key)).size, navItems.length);
});

test('given a dataset route, getPageTitle includes the active dataset name', () => {
  assert.equal(getPageTitle('datasets', 'Cardio.csv'), 'Dataset: Cardio.csv');
});

test('given non-dataset routes, getPageTitle returns their configured title', () => {
  assert.equal(getPageTitle('dashboard', 'Ignored.csv'), pageTitles.dashboard);
  assert.equal(getPageTitle('reports', 'Ignored.csv'), pageTitles.reports);
});
