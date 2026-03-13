import type { Table } from "@tanstack/react-table";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

interface DataTablePaginationProps<TData> {
  table: Table<TData>;
  pageSizeOptions?: number[];
  totalRows?: number;
}

export function DataTablePagination<TData>({
  table,
  pageSizeOptions = [10, 20, 50],
  totalRows,
}: DataTablePaginationProps<TData>) {
  const { pageIndex, pageSize } = table.getState().pagination;
  const pageCount = table.getPageCount();

  const displayTotal =
    totalRows != null ? totalRows : table.getFilteredRowModel().rows.length;

  return (
    <div className="flex items-center justify-between px-2 py-4">
      {/* Left: total count */}
      <p className="text-sm text-muted-foreground">
        {displayTotal === 1
          ? "1 registro no total"
          : `${displayTotal} registros no total`}
      </p>

      {/* Right: page size + navigation */}
      <div className="flex items-center gap-4">
        {/* Page size selector */}
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Linhas</span>
          <Select
            value={String(pageSize)}
            onValueChange={(value) => {
              table.setPageSize(Number(value));
            }}
          >
            <SelectTrigger size="sm" className="w-[70px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent align="end">
              {pageSizeOptions.map((size) => (
                <SelectItem key={size} value={String(size)}>
                  {size}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Page info */}
        <span className="text-sm text-muted-foreground">
          Pagina {pageIndex + 1} de {pageCount || 1}
        </span>

        {/* Navigation buttons */}
        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="icon-sm"
            onClick={() => table.previousPage()}
            disabled={!table.getCanPreviousPage()}
            aria-label="Pagina anterior"
          >
            <ChevronLeft className="size-4" />
          </Button>
          <Button
            variant="outline"
            size="icon-sm"
            onClick={() => table.nextPage()}
            disabled={!table.getCanNextPage()}
            aria-label="Proxima pagina"
          >
            <ChevronRight className="size-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
