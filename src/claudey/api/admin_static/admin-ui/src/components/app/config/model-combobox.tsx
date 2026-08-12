import * as React from "react";
import { useEffect, useRef, useState } from "react";
import { ChevronDown, Search } from "lucide-react";

import { cn } from "@/lib/utils";
import { fetchModels } from "@/api/client";

interface ModelComboboxProps {
  value: string;
  onChange: (value: string) => void;
  type: "model" | "optional_model";
  placeholder?: string;
  disabled?: boolean;
}

/**
 * ModelCombobox — searchable input with a dropdown of discovered models.
 * Mirrors the vanilla admin's ModelCombobox class exactly: type-to-filter,
 * arrow-key navigation, Enter to select, Escape to close, custom slug entry.
 * Per design-system: heat accent on the active option, hairline list border.
 */
export function ModelCombobox({
  value,
  onChange,
  type,
  placeholder,
  disabled,
}: ModelComboboxProps) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(-1);
  const [models, setModels] = useState<string[]>([]);

  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  // Load discovered models once on mount
  useEffect(() => {
    let cancelled = false;
    fetchModels()
      .then((res) => {
        if (!cancelled) setModels(res.models || []);
      })
      .catch(() => {
        /* model options remain empty — custom slug entry still works */
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const allValues = type === "optional_model" ? ["None", ...models] : models;

  const filtered = query.trim()
    ? allValues.filter((v) => v.toLowerCase().includes(query.trim().toLowerCase()))
    : allValues;

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  const select = (val: string) => {
    onChange(val);
    setOpen(false);
    setQuery("");
    inputRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      const dir = e.key === "ArrowDown" ? 1 : -1;
      setActiveIndex((prev) => {
        const count = filtered.length;
        if (count === 0) return -1;
        return ((prev === -1 ? 0 : prev) + dir + count) % count;
      });
    } else if (e.key === "Enter" && open) {
      if (activeIndex >= 0 && activeIndex < filtered.length) {
        e.preventDefault();
        select(filtered[activeIndex]);
      }
    } else if (e.key === "Escape" && open) {
      e.preventDefault();
      setOpen(false);
    } else if (e.key === "Tab" && open) {
      setOpen(false);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    onChange(e.target.value);
    setQuery(e.target.value);
    setOpen(true);
    setActiveIndex(-1);
  };

  const handleFocus = () => {
    inputRef.current?.select();
  };

  return (
    <div ref={wrapperRef} className={cn("relative", disabled && "opacity-50")}>
      <div className="relative">
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={handleInputChange}
          onFocus={handleFocus}
          onKeyDown={handleKeyDown}
          onClick={() => setOpen(true)}
          placeholder={placeholder}
          disabled={disabled}
          autoComplete="off"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={open}
          aria-haspopup="listbox"
          className={cn(
            "border-hairline placeholder:text-ink-muted-48 h-10 w-full rounded-sm border bg-canvas pr-9 pl-3 text-[14px] text-ink transition-[border-color,box-shadow] ease-default outline-none",
            "focus-visible:border-heat focus-visible:ring-2 focus-visible:ring-heat/30",
            "disabled:pointer-events-none disabled:cursor-not-allowed",
          )}
        />
        <button
          type="button"
          tabIndex={-1}
          onMouseDown={(e) => e.preventDefault()}
          onClick={() => {
            if (disabled) return;
            setOpen((prev) => !prev);
            inputRef.current?.focus();
          }}
          disabled={disabled}
          aria-label="Show model options"
          className="absolute top-1/2 right-1 -translate-y-1/2 grid size-8 place-items-center rounded-sm text-ink-muted-48 transition-colors hover:text-ink"
        >
          {open ? <Search className="size-3.5" /> : <ChevronDown className="size-4" />}
        </button>
      </div>

      {open && (
        <div
          ref={listRef}
          role="listbox"
          className="animate-in fade-in-0 zoom-in-95 absolute top-full left-0 z-50 mt-1 max-h-64 w-full overflow-y-auto rounded-sm border border-hairline bg-canvas py-1 shadow-float"
        >
          {filtered.length === 0 ? (
            <div className="px-3 py-2 text-[13px] text-ink-muted-48">
              {models.length
                ? "No matching models. You can still enter a custom slug."
                : "No discovered models. Refresh models or enter a custom slug."}
            </div>
          ) : (
            filtered.map((val, index) => (
              <div
                key={val}
                role="option"
                aria-selected={index === activeIndex}
                onMouseDown={(e) => {
                  e.preventDefault();
                  select(val);
                }}
                onMouseEnter={() => setActiveIndex(index)}
                className={cn(
                  "cursor-pointer px-3 py-2 text-[13px] transition-colors duration-100",
                  index === activeIndex ? "bg-parchment text-heat" : "text-ink",
                  val === value && "font-semibold text-heat",
                )}
              >
                {val}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}