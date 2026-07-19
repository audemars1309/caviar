/** Reusable strongly-typed builder field primitives: labeled inputs,
 *  a month/free-text date field, tag lists (skills/technologies), and
 *  dynamic bullet lists with keyboard-accessible reordering. */
import { ArrowDown, ArrowUp, Plus, X } from "lucide-react";
import { useId, useState, type KeyboardEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

export function TextField({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: string;
}) {
  const id = useId();
  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <Input
        id={id}
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}

export function TextAreaField({
  label,
  value,
  onChange,
  placeholder,
  rows = 4,
  maxLength,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  rows?: number;
  maxLength?: number;
}) {
  const id = useId();
  return (
    <div className="space-y-1.5">
      <div className="flex items-baseline justify-between">
        <Label htmlFor={id}>{label}</Label>
        {maxLength ? (
          <span className="text-xs tabular-nums text-muted-foreground">
            {value.length}/{maxLength}
          </span>
        ) : null}
      </div>
      <Textarea
        id={id}
        rows={rows}
        value={value}
        placeholder={placeholder}
        maxLength={maxLength}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}

/** Free-text date field ("Jun 2024", "Present") - the backend stores
 *  resume dates as short strings by design. */
export function DateField({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <TextField
      label={label}
      value={value}
      onChange={onChange}
      placeholder="e.g. Jun 2024 or Present"
    />
  );
}

export function TagListField({
  label,
  values,
  onChange,
  placeholder = "Type and press Enter",
  maxItems,
}: {
  label: string;
  values: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
  maxItems?: number;
}) {
  const id = useId();
  const [draft, setDraft] = useState("");

  const commit = () => {
    const value = draft.trim();
    if (!value) return;
    if (values.includes(value)) {
      setDraft("");
      return;
    }
    if (maxItems && values.length >= maxItems) return;
    onChange([...values, value]);
    setDraft("");
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      commit();
    } else if (event.key === "Backspace" && draft === "" && values.length > 0) {
      onChange(values.slice(0, -1));
    }
  };

  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <div className="flex flex-wrap items-center gap-1.5 rounded-md border border-input bg-background p-1.5 focus-within:ring-2 focus-within:ring-ring">
        {values.map((value, index) => (
          <span
            key={`${value}-${index}`}
            className="inline-flex items-center gap-1 rounded bg-secondary px-2 py-0.5 text-xs"
          >
            {value}
            <button
              type="button"
              aria-label={`Remove ${value}`}
              className="rounded hover:text-destructive"
              onClick={() => onChange(values.filter((_, i) => i !== index))}
            >
              <X className="size-3" aria-hidden />
            </button>
          </span>
        ))}
        <input
          id={id}
          className="min-w-24 flex-1 bg-transparent px-1 py-0.5 text-sm outline-none placeholder:text-muted-foreground"
          value={draft}
          placeholder={placeholder}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={commit}
        />
      </div>
    </div>
  );
}

export function BulletListField({
  label,
  bullets,
  onChange,
  maxItems = 20,
}: {
  label: string;
  bullets: string[];
  onChange: (bullets: string[]) => void;
  maxItems?: number;
}) {
  const move = (index: number, delta: -1 | 1) => {
    const target = index + delta;
    if (target < 0 || target >= bullets.length) return;
    const next = [...bullets];
    const [item] = next.splice(index, 1);
    next.splice(target, 0, item!);
    onChange(next);
  };

  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-medium">{label}</legend>
      {bullets.map((bullet, index) => (
        <div key={index} className="flex items-start gap-1.5">
          <Textarea
            aria-label={`${label} bullet ${index + 1}`}
            rows={2}
            value={bullet}
            onChange={(event) =>
              onChange(bullets.map((item, i) => (i === index ? event.target.value : item)))
            }
          />
          <div className="flex flex-col">
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              aria-label={`Move bullet ${index + 1} up`}
              disabled={index === 0}
              onClick={() => move(index, -1)}
            >
              <ArrowUp aria-hidden />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              aria-label={`Move bullet ${index + 1} down`}
              disabled={index === bullets.length - 1}
              onClick={() => move(index, 1)}
            >
              <ArrowDown aria-hidden />
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              aria-label={`Remove bullet ${index + 1}`}
              onClick={() => onChange(bullets.filter((_, i) => i !== index))}
            >
              <X aria-hidden />
            </Button>
          </div>
        </div>
      ))}
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={bullets.length >= maxItems}
        onClick={() => onChange([...bullets, ""])}
      >
        <Plus aria-hidden /> Add bullet
      </Button>
    </fieldset>
  );
}

/** Generic dynamic entry list with add / remove / reorder controls. */
export function EntryList<TEntry>({
  entries,
  onChange,
  renderEntry,
  makeEmpty,
  entryLabel,
  maxItems = 20,
}: {
  entries: TEntry[];
  onChange: (entries: TEntry[]) => void;
  renderEntry: (entry: TEntry, update: (entry: TEntry) => void, index: number) => React.ReactNode;
  makeEmpty: () => TEntry;
  entryLabel: string;
  maxItems?: number;
}) {
  const move = (index: number, delta: -1 | 1) => {
    const target = index + delta;
    if (target < 0 || target >= entries.length) return;
    const next = [...entries];
    const [item] = next.splice(index, 1);
    next.splice(target, 0, item!);
    onChange(next);
  };

  return (
    <div className="space-y-4">
      {entries.map((entry, index) => (
        <div key={index} className="space-y-3 rounded-lg border p-4">
          <div className="flex items-center justify-between">
            <p className="text-sm font-medium text-muted-foreground">
              {entryLabel} {index + 1}
            </p>
            <div className="flex gap-1">
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                aria-label={`Move ${entryLabel} ${index + 1} up`}
                disabled={index === 0}
                onClick={() => move(index, -1)}
              >
                <ArrowUp aria-hidden />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                aria-label={`Move ${entryLabel} ${index + 1} down`}
                disabled={index === entries.length - 1}
                onClick={() => move(index, 1)}
              >
                <ArrowDown aria-hidden />
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-7 w-7"
                aria-label={`Remove ${entryLabel} ${index + 1}`}
                disabled={entries.length <= 1}
                onClick={() => onChange(entries.filter((_, i) => i !== index))}
              >
                <X aria-hidden />
              </Button>
            </div>
          </div>
          {renderEntry(
            entry,
            (updated) => onChange(entries.map((item, i) => (i === index ? updated : item))),
            index,
          )}
        </div>
      ))}
      <Button
        type="button"
        variant="outline"
        size="sm"
        disabled={entries.length >= maxItems}
        onClick={() => onChange([...entries, makeEmpty()])}
      >
        <Plus aria-hidden /> Add {entryLabel.toLowerCase()}
      </Button>
    </div>
  );
}
