"use client";

import { useMemo, useState } from "react";

import type { ConditionBand, ListingItem } from "@/lib/publicApi";
import { extractAttributes, type ListingAttributes } from "@/lib/listingAttributes";
import { conditionBandLabels } from "@/lib/vocabulary";

import { AuthLabelBadge, cleanListingTitle } from "./MarketComponents";

const BAND_ORDER: ConditionBand[] = [
  "new_or_unused",
  "excellent",
  "very_good",
  "good",
  "fair",
  "poor",
];

const READ_RANK: Record<string, number> = { below: 0, near: 1, above: 2 };

type SortKey = "price" | "year" | "recency" | "read";
type SortDir = "asc" | "desc";

type Row = { listing: ListingItem; attr: ListingAttributes };

function priceOf(listing: ListingItem): number {
  return Number(listing.total_price ?? listing.price) || 0;
}

function distinct(rows: Row[], pick: (attr: ListingAttributes) => string | number | null): string[] {
  const seen = new Set<string>();
  for (const row of rows) {
    const value = pick(row.attr);
    if (value != null && value !== "") seen.add(String(value));
  }
  return [...seen];
}

export function ListingsExplorer({
  listings,
  protect = "",
}: {
  listings: ListingItem[];
  protect?: string;
}) {
  const rows = useMemo<Row[]>(
    () => listings.map((listing) => ({ listing, attr: extractAttributes(listing.title) })),
    [listings],
  );

  const [band, setBand] = useState<ConditionBand | "all">("all");
  const [color, setColor] = useState("all");
  const [material, setMaterial] = useState("all");
  const [type, setType] = useState("all");
  const [year, setYear] = useState("all");
  const [dealsOnly, setDealsOnly] = useState(false);
  const [authOnly, setAuthOnly] = useState(false);
  const [sortKey, setSortKey] = useState<SortKey>("price");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const bandsPresent = useMemo(
    () => BAND_ORDER.filter((b) => rows.some((r) => r.listing.condition_band === b)),
    [rows],
  );
  const colors = useMemo(() => distinct(rows, (a) => a.color).sort(), [rows]);
  const materials = useMemo(() => distinct(rows, (a) => a.material).sort(), [rows]);
  const types = useMemo(() => distinct(rows, (a) => a.type).sort(), [rows]);
  const years = useMemo(
    () => distinct(rows, (a) => a.year).sort((x, y) => Number(y) - Number(x)),
    [rows],
  );
  const dealCount = useMemo(
    () => rows.filter((r) => r.listing.verdict?.label === "below").length,
    [rows],
  );

  const filtered = useMemo(() => {
    const out = rows.filter(({ listing, attr }) => {
      if (band !== "all" && listing.condition_band !== band) return false;
      if (color !== "all" && attr.color !== color) return false;
      if (material !== "all" && attr.material !== material) return false;
      if (type !== "all" && attr.type !== type) return false;
      if (year !== "all" && String(attr.year) !== year) return false;
      if (dealsOnly && listing.verdict?.label !== "below") return false;
      if (authOnly && listing.auth_label !== "platform_authenticated") return false;
      return true;
    });
    const dir = sortDir === "asc" ? 1 : -1;
    out.sort((a, b) => {
      if (sortKey === "price") return (priceOf(a.listing) - priceOf(b.listing)) * dir;
      if (sortKey === "year") return ((a.attr.year ?? 0) - (b.attr.year ?? 0)) * dir;
      if (sortKey === "recency") return b.listing.last_observed.localeCompare(a.listing.last_observed) * dir;
      // read
      return (
        ((READ_RANK[a.listing.verdict?.label ?? "near"] ?? 1) -
          (READ_RANK[b.listing.verdict?.label ?? "near"] ?? 1)) * dir ||
        priceOf(a.listing) - priceOf(b.listing)
      );
    });
    return out;
  }, [rows, band, color, material, type, year, dealsOnly, authOnly, sortKey, sortDir]);

  function toggleSort(key: SortKey) {
    if (sortKey === key) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortKey(key);
      setSortDir(key === "price" || key === "year" ? "asc" : "desc");
    }
  }

  function resetFacets() {
    setBand("all");
    setColor("all");
    setMaterial("all");
    setType("all");
    setYear("all");
    setDealsOnly(false);
    setAuthOnly(false);
  }

  const arrow = (key: SortKey) => (sortKey === key ? (sortDir === "asc" ? " ▲" : " ▼") : "");
  const anyFilter =
    band !== "all" || color !== "all" || material !== "all" || type !== "all" || year !== "all" || dealsOnly || authOnly;

  return (
    <div className="listingExplorer">
      <div className="listingFilters">
        <div className="listingChips">
          <button
            className={band === "all" ? "listingChip on" : "listingChip"}
            onClick={() => setBand("all")}
            type="button"
          >
            All conditions
          </button>
          {bandsPresent.map((b) => (
            <button
              className={band === b ? "listingChip on" : "listingChip"}
              key={b}
              onClick={() => setBand(b)}
              type="button"
            >
              {conditionBandLabels[b]}
            </button>
          ))}
        </div>

        <div className="listingSelects">
          <FacetSelect label="Color" value={color} options={colors} onChange={setColor} />
          <FacetSelect label="Material" value={material} options={materials} onChange={setMaterial} />
          <FacetSelect label="Type" value={type} options={types} onChange={setType} />
          <FacetSelect label="Year" value={year} options={years} onChange={setYear} />
          <button
            className={dealsOnly ? "listingChip toggle on" : "listingChip toggle"}
            onClick={() => setDealsOnly((v) => !v)}
            type="button"
            disabled={dealCount === 0}
          >
            Below typical{dealCount ? ` (${dealCount})` : ""}
          </button>
          <button
            className={authOnly ? "listingChip toggle on" : "listingChip toggle"}
            onClick={() => setAuthOnly((v) => !v)}
            type="button"
          >
            Platform-authenticated
          </button>
          {anyFilter ? (
            <button className="listingReset" onClick={resetFacets} type="button">
              Clear
            </button>
          ) : null}
        </div>
      </div>

      <p className="muted listingCount">
        {filtered.length} of {listings.length} listings
      </p>

      <div className="listingScroll">
        <div className="listingGrid facet">
          <div className="listingGridHead">
            <span />
            <span>Listing</span>
            <button className="listingSortHead" onClick={() => toggleSort("year")} type="button">
              Year{arrow("year")}
            </button>
            <span>Color</span>
            <span>Material</span>
            <span>Condition</span>
            <button className="listingSortHead" onClick={() => toggleSort("price")} type="button">
              Price{arrow("price")}
            </button>
            <button className="listingSortHead" onClick={() => toggleSort("read")} type="button">
              Read{arrow("read")}
            </button>
          </div>
          {filtered.map(({ listing, attr }) => {
            const content = (
              <>
                <span
                  className="listingThumb"
                  style={listing.image_url ? { backgroundImage: `url("${listing.image_url}")` } : undefined}
                  aria-hidden="true"
                />
                <span className="listingName">
                  <strong>{cleanListingTitle(listing.title, protect)}</strong>
                  <span className="muted">
                    {listing.source}
                    {listing.item_location ? ` · ${listing.item_location}` : ""}
                    {listing.auth_label === "platform_authenticated" ? " · " : ""}
                  </span>
                </span>
                <span className="listingCol mono">{attr.year ?? "—"}</span>
                <span className="listingCol">{attr.color ?? "—"}</span>
                <span className="listingCol">{attr.material ?? "—"}</span>
                <span className="listingCol">
                  {listing.condition_band ? conditionBandLabels[listing.condition_band] : "Unbanded"}
                </span>
                <span className="listingCol listingPriceCol mono">
                  ${listing.total_price ?? listing.price}
                  {listing.shipping_price ? <span className="muted"> +ship</span> : null}
                </span>
                <span className="listingCol">
                  {listing.verdict ? (
                    <span className={`readChip ${listing.verdict.label}`}>
                      {listing.verdict.label === "below" ? "▼" : listing.verdict.label === "above" ? "▲" : "≈"}{" "}
                      {Math.abs(Number(listing.verdict.percent_diff)).toFixed(0)}%
                    </span>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </span>
                {listing.image_url ? (
                  <span
                    className="listingPreview"
                    style={{ backgroundImage: `url("${listing.image_url}")` }}
                    aria-hidden="true"
                  />
                ) : null}
              </>
            );
            return listing.item_url ? (
              <a
                className="listingRow"
                data-analytics-event="outbound_click"
                href={listing.item_url}
                key={listing.id}
                rel="nofollow noopener"
                target="_blank"
              >
                {content}
              </a>
            ) : (
              <div className="listingRow" key={listing.id}>
                {content}
              </div>
            );
          })}
          {filtered.length === 0 ? <p className="muted listingEmpty">No listings match these filters.</p> : null}
        </div>
      </div>
    </div>
  );
}

function FacetSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: string[];
  onChange: (value: string) => void;
}) {
  if (options.length === 0) return null;
  return (
    <label className="facetSelect">
      <span className="visually-hidden">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="all">{label}: all</option>
        {options.map((opt) => (
          <option key={opt} value={opt}>
            {opt}
          </option>
        ))}
      </select>
    </label>
  );
}
