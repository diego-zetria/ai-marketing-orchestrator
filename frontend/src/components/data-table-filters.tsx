import { useState } from "react";
import { Filter, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Separator } from "@/components/ui/separator";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface FilterOption {
  value: string;
  label: string;
  count?: number;
}

export interface FilterDefinition {
  id: string;
  label: string;
  options: FilterOption[];
}

export type ActiveFilters = Record<string, string[]>;

// ---------------------------------------------------------------------------
// Single filter popover
// ---------------------------------------------------------------------------

interface FilterPopoverProps {
  filter: FilterDefinition;
  selected: string[];
  onSelectionChange: (filterId: string, values: string[]) => void;
}

function FilterPopover({ filter, selected, onSelectionChange }: FilterPopoverProps) {
  const [open, setOpen] = useState(false);
  const hasSelection = selected.length > 0;

  function toggle(value: string) {
    const next = selected.includes(value)
      ? selected.filter((v) => v !== value)
      : [...selected, value];
    onSelectionChange(filter.id, next);
  }

  function clearAll() {
    onSelectionChange(filter.id, []);
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className={hasSelection ? "border-primary/50 bg-primary/5" : ""}
        >
          <Filter className="mr-1.5 size-3.5" aria-hidden="true" />
          {filter.label}
          {hasSelection && (
            <Badge variant="secondary" className="ml-1.5 px-1 py-0 text-[10px]">
              {selected.length}
            </Badge>
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-52 p-0" align="start">
        <div className="p-3 pb-1">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            {filter.label}
          </p>
        </div>
        <Separator />
        <div className="max-h-48 overflow-y-auto p-2">
          {filter.options.map((option) => (
            <label
              key={option.value}
              className="flex cursor-pointer items-center gap-2 rounded-sm px-2 py-1.5 text-sm hover:bg-accent"
            >
              <Checkbox
                checked={selected.includes(option.value)}
                onCheckedChange={() => toggle(option.value)}
              />
              <span className="flex-1">{option.label}</span>
              {option.count != null && (
                <span className="text-xs text-muted-foreground">{option.count}</span>
              )}
            </label>
          ))}
        </div>
        {hasSelection && (
          <>
            <Separator />
            <div className="p-2">
              <Button
                variant="ghost"
                size="sm"
                className="w-full text-xs"
                onClick={clearAll}
              >
                Limpar filtro
              </Button>
            </div>
          </>
        )}
      </PopoverContent>
    </Popover>
  );
}

// ---------------------------------------------------------------------------
// Filter bar (multiple filters + active badges)
// ---------------------------------------------------------------------------

interface DataTableFiltersProps {
  filters: FilterDefinition[];
  activeFilters: ActiveFilters;
  onFiltersChange: (filters: ActiveFilters) => void;
}

export function DataTableFilters({
  filters,
  activeFilters,
  onFiltersChange,
}: DataTableFiltersProps) {
  function handleSelectionChange(filterId: string, values: string[]) {
    const next = { ...activeFilters, [filterId]: values };
    if (values.length === 0) {
      delete next[filterId];
    }
    onFiltersChange(next);
  }

  function clearAll() {
    onFiltersChange({});
  }

  // Collect all active filter badges
  const activeBadges: { filterId: string; value: string; label: string }[] = [];
  for (const filter of filters) {
    const selected = activeFilters[filter.id] ?? [];
    for (const value of selected) {
      const option = filter.options.find((o) => o.value === value);
      activeBadges.push({
        filterId: filter.id,
        value,
        label: `${filter.label}: ${option?.label ?? value}`,
      });
    }
  }

  function removeBadge(filterId: string, value: string) {
    const current = activeFilters[filterId] ?? [];
    handleSelectionChange(
      filterId,
      current.filter((v) => v !== value)
    );
  }

  return (
    <div className="space-y-2">
      {/* Filter popovers */}
      <div className="flex flex-wrap items-center gap-2">
        {filters.map((filter) => (
          <FilterPopover
            key={filter.id}
            filter={filter}
            selected={activeFilters[filter.id] ?? []}
            onSelectionChange={handleSelectionChange}
          />
        ))}
        {activeBadges.length > 0 && (
          <Button
            variant="ghost"
            size="sm"
            className="text-xs text-muted-foreground"
            onClick={clearAll}
          >
            <X className="mr-1 size-3" aria-hidden="true" />
            Limpar tudo
          </Button>
        )}
      </div>

      {/* Active filter badges */}
      {activeBadges.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5">
          {activeBadges.map((badge) => (
            <Badge
              key={`${badge.filterId}-${badge.value}`}
              variant="secondary"
              className="gap-1 pr-1"
            >
              {badge.label}
              <button
                type="button"
                className="ml-0.5 rounded-sm p-0.5 hover:bg-muted"
                onClick={() => removeBadge(badge.filterId, badge.value)}
                aria-label={`Remover filtro ${badge.label}`}
              >
                <X className="size-3" />
              </button>
            </Badge>
          ))}
        </div>
      )}
    </div>
  );
}
