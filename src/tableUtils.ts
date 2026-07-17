export type SortDirection = 'asc' | 'desc';

type Row = Record<string, unknown>;

function normalize(value: unknown) {
  if (Array.isArray(value)) return value.join(' ');
  if (value === null || value === undefined) return '';
  return String(value);
}

export function filterRows<T extends Row>(rows: T[], searchTerm: string) {
  const query = searchTerm.trim().toLowerCase();
  if (!query) return rows;

  return rows.filter((row) =>
    Object.values(row).some((value) => normalize(value).toLowerCase().includes(query)),
  );
}

export function sortRows<T extends Row>(rows: T[], sortKey: keyof T, direction: SortDirection) {
  const multiplier = direction === 'asc' ? 1 : -1;

  return [...rows].sort((left, right) => {
    const leftValue = left[sortKey];
    const rightValue = right[sortKey];

    if (typeof leftValue === 'number' && typeof rightValue === 'number') {
      return (leftValue - rightValue) * multiplier;
    }

    return normalize(leftValue).localeCompare(normalize(rightValue), undefined, {
      numeric: true,
      sensitivity: 'base',
    }) * multiplier;
  });
}

export function paginateRows<T>(rows: T[], page: number, rowsPerPage: number) {
  const safeRowsPerPage = Math.max(1, rowsPerPage);
  const maxPage = Math.max(0, Math.ceil(rows.length / safeRowsPerPage) - 1);
  const safePage = Math.min(Math.max(0, page), maxPage);
  const start = safePage * safeRowsPerPage;

  return {
    page: safePage,
    rows: rows.slice(start, start + safeRowsPerPage),
  };
}

export function getVisibleRows<T extends Row>({
  rows,
  searchTerm,
  sortKey,
  sortDirection,
  page,
  rowsPerPage,
}: {
  rows: T[];
  searchTerm: string;
  sortKey: keyof T;
  sortDirection: SortDirection;
  page: number;
  rowsPerPage: number;
}) {
  const filteredRows = filterRows(rows, searchTerm);
  const sortedRows = sortRows(filteredRows, sortKey, sortDirection);
  const paginatedRows = paginateRows(sortedRows, page, rowsPerPage);

  return {
    filteredRows,
    sortedRows,
    visibleRows: paginatedRows.rows,
    page: paginatedRows.page,
    total: filteredRows.length,
  };
}
