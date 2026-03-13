/**
 * Export tabular data to CSV and trigger browser download.
 */

interface ExportColumn<T> {
  header: string;
  accessor: (row: T) => string | number | boolean | null | undefined;
}

function escapeCell(value: unknown): string {
  if (value === null || value === undefined) return "";
  const str = String(value);
  // Wrap in quotes if the value contains commas, quotes, or newlines
  if (str.includes(",") || str.includes('"') || str.includes("\n")) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

export function exportToCsv<T>(
  data: T[],
  columns: ExportColumn<T>[],
  filename: string
) {
  const header = columns.map((c) => escapeCell(c.header)).join(",");
  const rows = data.map((row) =>
    columns.map((col) => escapeCell(col.accessor(row))).join(",")
  );

  // BOM for Excel UTF-8 compatibility
  const bom = "\uFEFF";
  const csv = bom + [header, ...rows].join("\n");

  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);

  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();

  URL.revokeObjectURL(url);
}

/** Generate a timestamped filename like "clientes_2026-02-23.csv" */
export function csvFilename(entity: string): string {
  const date = new Date().toISOString().slice(0, 10);
  return `${entity}_${date}.csv`;
}
