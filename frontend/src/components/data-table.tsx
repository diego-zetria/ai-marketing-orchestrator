import { useState, useEffect, useCallback, useRef } from "react";
import {
  useReactTable,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  flexRender,
  type ColumnDef,
  type SortingState,
  type RowSelectionState,
  type PaginationState,
} from "@tanstack/react-table";
import {
  ChevronUp,
  ChevronDown,
  ChevronsUpDown,
  Search,
} from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { Skeleton } from "@/components/ui/skeleton";
import { DataTablePagination } from "@/components/data-table-pagination";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface DataTableProps<TData> {
  columns: ColumnDef<TData, unknown>[];
  data: TData[];

  // Pagination
  pageCount?: number;
  pageIndex?: number;
  pageSize?: number;
  onPaginationChange?: (pagination: {
    pageIndex: number;
    pageSize: number;
  }) => void;

  // Sorting
  sorting?: SortingState;
  onSortingChange?: (sorting: SortingState) => void;

  // Search
  searchValue?: string;
  onSearchChange?: (value: string) => void;
  searchPlaceholder?: string;

  // Row selection
  enableRowSelection?: boolean;
  onRowSelectionChange?: (selection: RowSelectionState) => void;

  // State
  isLoading?: boolean;
  emptyMessage?: string;

  // Server-side mode
  manualPagination?: boolean;
  manualSorting?: boolean;

  // Total count for display
  totalRows?: number;

  // Row click handler
  onRowClick?: (row: TData) => void;
}

// ---------------------------------------------------------------------------
// Debounce hook
// ---------------------------------------------------------------------------

function useDebouncedCallback(
  callback: (value: string) => void,
  delay: number,
) {
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const debouncedFn = useCallback(
    (value: string) => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      timeoutRef.current = setTimeout(() => {
        callback(value);
      }, delay);
    },
    [callback, delay],
  );

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
    };
  }, []);

  return debouncedFn;
}

// ---------------------------------------------------------------------------
// Selection column helper
// ---------------------------------------------------------------------------

function getSelectionColumn<TData>(): ColumnDef<TData, unknown> {
  return {
    id: "select",
    header: ({ table }) => (
      <Checkbox
        checked={
          table.getIsAllPageRowsSelected() ||
          (table.getIsSomePageRowsSelected() && "indeterminate")
        }
        onCheckedChange={(value) => table.toggleAllPageRowsSelected(!!value)}
        aria-label="Selecionar todos"
      />
    ),
    cell: ({ row }) => (
      <Checkbox
        checked={row.getIsSelected()}
        onCheckedChange={(value) => row.toggleSelected(!!value)}
        aria-label="Selecionar linha"
      />
    ),
    enableSorting: false,
    enableHiding: false,
    size: 40,
  };
}

// ---------------------------------------------------------------------------
// Sort indicator
// ---------------------------------------------------------------------------

function SortIndicator({ direction }: { direction: false | "asc" | "desc" }) {
  if (direction === "asc") {
    return <ChevronUp className="ml-1 size-3.5" aria-hidden="true" />;
  }
  if (direction === "desc") {
    return <ChevronDown className="ml-1 size-3.5" aria-hidden="true" />;
  }
  return <ChevronsUpDown className="ml-1 size-3.5 opacity-40" aria-hidden="true" />;
}

// ---------------------------------------------------------------------------
// Loading skeleton rows
// ---------------------------------------------------------------------------

function SkeletonRows({
  columnCount,
  rowCount,
}: {
  columnCount: number;
  rowCount: number;
}) {
  return (
    <>
      {Array.from({ length: rowCount }).map((_, rowIdx) => (
        <TableRow key={rowIdx}>
          {Array.from({ length: columnCount }).map((_, colIdx) => (
            <TableCell key={colIdx}>
              <Skeleton className="h-4 w-full max-w-[120px]" />
            </TableCell>
          ))}
        </TableRow>
      ))}
    </>
  );
}

// ---------------------------------------------------------------------------
// DataTable Component
// ---------------------------------------------------------------------------

export function DataTable<TData>({
  columns,
  data,
  pageCount: controlledPageCount,
  pageIndex: controlledPageIndex,
  pageSize: controlledPageSize,
  onPaginationChange,
  sorting: controlledSorting,
  onSortingChange,
  searchValue,
  onSearchChange,
  searchPlaceholder = "Buscar...",
  enableRowSelection = false,
  onRowSelectionChange,
  isLoading = false,
  emptyMessage = "Nenhum registro encontrado.",
  manualPagination = false,
  manualSorting = false,
  totalRows,
  onRowClick,
}: DataTableProps<TData>) {
  // ---- Internal state (used when not in server-side mode) ----
  const [internalSorting, setInternalSorting] = useState<SortingState>([]);
  const [internalPagination, setInternalPagination] = useState<PaginationState>(
    {
      pageIndex: controlledPageIndex ?? 0,
      pageSize: controlledPageSize ?? 10,
    },
  );
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({});
  const [globalFilter, setGlobalFilter] = useState(searchValue ?? "");

  // Local input value for debounced search
  const [localSearchInput, setLocalSearchInput] = useState(searchValue ?? "");

  // Sync controlled searchValue to local input
  useEffect(() => {
    if (searchValue != null) {
      setLocalSearchInput(searchValue);
    }
  }, [searchValue]);

  // Determine which state to use
  const sorting = controlledSorting ?? internalSorting;
  const pagination: PaginationState = manualPagination
    ? {
        pageIndex: controlledPageIndex ?? 0,
        pageSize: controlledPageSize ?? 10,
      }
    : internalPagination;

  // ---- Debounced search handler ----
  const debouncedSearch = useDebouncedCallback(
    useCallback(
      (value: string) => {
        if (onSearchChange) {
          onSearchChange(value);
        } else {
          setGlobalFilter(value);
        }
      },
      [onSearchChange],
    ),
    300,
  );

  function handleSearchInput(value: string) {
    setLocalSearchInput(value);
    debouncedSearch(value);
  }

  // ---- Row selection sync ----
  useEffect(() => {
    if (onRowSelectionChange) {
      onRowSelectionChange(rowSelection);
    }
  }, [rowSelection, onRowSelectionChange]);

  // ---- Build effective columns ----
  const effectiveColumns: ColumnDef<TData, unknown>[] = enableRowSelection
    ? [getSelectionColumn<TData>(), ...columns]
    : columns;

  // ---- Table instance ----
  // eslint-disable-next-line react-hooks/incompatible-library -- TanStack Table is compatible, this is a known false positive with React Compiler
  const table = useReactTable({
    data,
    columns: effectiveColumns,
    state: {
      sorting,
      pagination,
      rowSelection,
      globalFilter: onSearchChange ? undefined : globalFilter,
    },
    // Sorting
    onSortingChange: (updater) => {
      const next =
        typeof updater === "function" ? updater(sorting) : updater;
      if (onSortingChange) {
        onSortingChange(next);
      } else {
        setInternalSorting(next);
      }
    },
    manualSorting,
    // Pagination
    onPaginationChange: (updater) => {
      const next =
        typeof updater === "function" ? updater(pagination) : updater;
      if (onPaginationChange) {
        onPaginationChange(next);
      }
      if (!manualPagination) {
        setInternalPagination(next);
      }
    },
    manualPagination,
    pageCount: manualPagination ? (controlledPageCount ?? -1) : undefined,
    // Row selection
    onRowSelectionChange: setRowSelection,
    enableRowSelection,
    // Global filter (client-side only)
    onGlobalFilterChange: onSearchChange ? undefined : setGlobalFilter,
    // Row models
    getCoreRowModel: getCoreRowModel(),
    getPaginationRowModel: manualPagination
      ? undefined
      : getPaginationRowModel(),
    getSortedRowModel: manualSorting ? undefined : getSortedRowModel(),
    getFilteredRowModel: onSearchChange ? undefined : getFilteredRowModel(),
  });

  // ---- Header groups for column count ----
  const headerGroups = table.getHeaderGroups();
  const columnCount = headerGroups[0]?.headers.length ?? columns.length;

  const showSearch = onSearchChange != null || searchValue != null || !manualPagination;

  return (
    <div className="space-y-0">
      {/* Search bar */}
      {showSearch && (
        <div className="flex items-center py-4">
          <div className="relative max-w-sm">
            <Search className="absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
            <Input
              placeholder={searchPlaceholder}
              value={localSearchInput}
              onChange={(e) => handleSearchInput(e.target.value)}
              className="pl-8"
              aria-label={searchPlaceholder}
            />
          </div>
        </div>
      )}

      {/* Table */}
      <div className="rounded-md border">
        <Table>
          <TableHeader>
            {headerGroups.map((headerGroup) => (
              <TableRow key={headerGroup.id}>
                {headerGroup.headers.map((header) => {
                  const canSort = header.column.getCanSort();
                  return (
                    <TableHead
                      key={header.id}
                      style={{ width: header.getSize() !== 150 ? header.getSize() : undefined }}
                    >
                      {header.isPlaceholder ? null : canSort ? (
                        <button
                          type="button"
                          className="inline-flex items-center gap-0.5 hover:text-foreground transition-colors -ml-1 px-1 py-0.5 rounded-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                          onClick={header.column.getToggleSortingHandler()}
                          aria-label={`Ordenar por ${typeof header.column.columnDef.header === "string" ? header.column.columnDef.header : header.column.id}`}
                        >
                          {flexRender(
                            header.column.columnDef.header,
                            header.getContext(),
                          )}
                          <SortIndicator
                            direction={header.column.getIsSorted()}
                          />
                        </button>
                      ) : (
                        flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )
                      )}
                    </TableHead>
                  );
                })}
              </TableRow>
            ))}
          </TableHeader>

          <TableBody>
            {/* Loading state */}
            {isLoading && (
              <SkeletonRows
                columnCount={columnCount}
                rowCount={pagination.pageSize}
              />
            )}

            {/* Empty state */}
            {!isLoading && table.getRowModel().rows.length === 0 && (
              <TableRow>
                <TableCell
                  colSpan={columnCount}
                  className="h-24 text-center text-muted-foreground"
                >
                  {emptyMessage}
                </TableCell>
              </TableRow>
            )}

            {/* Data rows */}
            {!isLoading &&
              table.getRowModel().rows.map((row) => (
                <TableRow
                  key={row.id}
                  data-state={row.getIsSelected() ? "selected" : undefined}
                  className={onRowClick ? "cursor-pointer" : undefined}
                  onClick={() => onRowClick?.(row.original)}
                >
                  {row.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </TableCell>
                  ))}
                </TableRow>
              ))}
          </TableBody>
        </Table>
      </div>

      {/* Pagination */}
      <DataTablePagination table={table} totalRows={totalRows} />
    </div>
  );
}

// Re-export useful types for consumers
export type {
  ColumnDef,
  SortingState,
  RowSelectionState,
} from "@tanstack/react-table";
