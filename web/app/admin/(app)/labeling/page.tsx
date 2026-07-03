/* eslint-disable @next/next/no-img-element */
"use client";

import { useEffect, useMemo, useState } from "react";

import {
  AdminListing,
  BagOption,
  ConditionBand,
  RejectionReason,
  getCatalogBags,
  getNextLabel,
  submitLabel,
} from "@/lib/adminApi";
import { adminCopy, conditionBands, rejectionReasons } from "@/lib/adminVocabulary";

type Flags = {
  strap_included: boolean | null;
  lock_included: boolean | null;
  key_included: boolean | null;
  dustbag_included: boolean | null;
  cards_included: boolean | null;
};

const emptyFlags: Flags = {
  strap_included: null,
  lock_included: null,
  key_included: null,
  dustbag_included: null,
  cards_included: null,
};

export default function LabelingPage() {
  const [bags, setBags] = useState<BagOption[]>([]);
  const [bagSlug, setBagSlug] = useState("");
  const [item, setItem] = useState<AdminListing | null>(null);
  const [history, setHistory] = useState<AdminListing[]>([]);
  const [remaining, setRemaining] = useState(0);
  const [mode, setMode] = useState<"accept" | "reject">("accept");
  const [reason, setReason] = useState<RejectionReason>(rejectionReasons[0]);
  const [variantId, setVariantId] = useState<number | "">("");
  const [color, setColor] = useState("");
  const [condition, setCondition] = useState<ConditionBand | "">("");
  const [flags, setFlags] = useState<Flags>(emptyFlags);
  const [showKeys, setShowKeys] = useState(false);
  const [imageFailed, setImageFailed] = useState(false);

  useEffect(() => {
    getCatalogBags().then((response) => {
      setBags(response.items);
      setBagSlug(response.items[0]?.slug ?? "");
    });
  }, []);

  useEffect(() => {
    if (bagSlug) {
      loadNext(undefined, false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bagSlug]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target?.tagName === "INPUT" || target?.tagName === "SELECT" || target?.tagName === "TEXTAREA") {
        return;
      }
      if (event.key === "?") {
        setShowKeys((value) => !value);
      } else if (event.key === "a") {
        setMode("accept");
      } else if (event.key === "r") {
        setMode("reject");
      } else if (event.key === "n") {
        void loadNext(item?.id, true);
      } else if (event.key === "u") {
        showPrevious();
      } else if (event.key === "Enter") {
        void save();
      } else if (/^[0-9]$/.test(event.key)) {
        const index = event.key === "0" ? 9 : Number(event.key) - 1;
        if (rejectionReasons[index]) {
          setReason(rejectionReasons[index]);
          setMode("reject");
        }
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const selectedBag = useMemo(() => bags.find((bag) => bag.slug === bagSlug), [bags, bagSlug]);

  async function loadNext(afterId?: number, remember = true) {
    if (!bagSlug) {
      return;
    }
    const response = await getNextLabel(bagSlug, afterId);
    if (remember && item) {
      setHistory((items) => [...items, item]);
    }
    setItem(response.item);
    setRemaining(response.remaining);
    resetForm();
  }

  function showPrevious() {
    setHistory((items) => {
      const previous = items.at(-1);
      if (!previous) {
        return items;
      }
      setItem(previous);
      resetForm();
      return items.slice(0, -1);
    });
  }

  function resetForm() {
    setMode("accept");
    setReason(rejectionReasons[0]);
    setVariantId("");
    setColor("");
    setCondition("");
    setFlags(emptyFlags);
    setImageFailed(false);
  }

  async function save() {
    if (!item || !selectedBag) {
      return;
    }
    await submitLabel({
      marketplace_item_id: item.marketplace_item_id,
      bag_model_id: selectedBag.id,
      verdict: mode,
      rejection_reason: mode === "reject" ? reason : null,
      accepted_variant_id: mode === "accept" && variantId !== "" ? variantId : null,
      color_family: mode === "accept" ? color || null : null,
      condition_band: mode === "accept" ? condition || null : null,
      ...flags,
    });
    await loadNext(item.id, true);
  }

  return (
    <div className="adminStack">
      <header className="adminHeader">
        <h1>{adminCopy.labeling}</h1>
        <div className="adminActionRow">
          <select
            className="adminSelect"
            value={bagSlug}
            onChange={(event) => {
              setHistory([]);
              setBagSlug(event.target.value);
            }}
          >
            {bags.map((bag) => (
              <option key={bag.slug} value={bag.slug}>
                {bag.brand} {bag.model_name}
              </option>
            ))}
          </select>
          <button className="adminGhostButton" type="button" onClick={() => setShowKeys((value) => !value)}>
            {adminCopy.keys}
          </button>
        </div>
      </header>

      {showKeys ? (
        <div className="adminKeyBox">
          a {adminCopy.accept} | r {adminCopy.reject} | n {adminCopy.skip} | u {adminCopy.previous} |
          Enter {adminCopy.enter}
        </div>
      ) : null}

      <section className="adminTwoColumn">
        <div className="adminTool">
          {item ? (
            <ListingPanel item={item} imageFailed={imageFailed} setImageFailed={setImageFailed} />
          ) : (
            <p className="adminMuted">{adminCopy.noRows}</p>
          )}
        </div>

        <div className="adminTool adminStack">
          <h2>{remaining} remaining</h2>
          <div className="adminActionRow">
            <button
              className={mode === "accept" ? "adminButton" : "adminGhostButton"}
              type="button"
              onClick={() => setMode("accept")}
            >
              {adminCopy.accept}
            </button>
            <button
              className={mode === "reject" ? "adminDangerButton" : "adminGhostButton"}
              type="button"
              onClick={() => setMode("reject")}
            >
              {adminCopy.reject}
            </button>
          </div>

          {mode === "reject" ? (
            <label className="adminStack">
              <span>{adminCopy.reason}</span>
              <select
                className="adminSelect"
                value={reason}
                onChange={(event) => setReason(event.target.value as RejectionReason)}
              >
                {rejectionReasons.map((value, index) => (
                  <option key={value} value={value}>
                    {index + 1 > 9 ? 0 : index + 1}. {value}
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <AcceptForm
              bag={selectedBag}
              variantId={variantId}
              setVariantId={setVariantId}
              color={color}
              setColor={setColor}
              condition={condition}
              setCondition={setCondition}
              flags={flags}
              setFlags={setFlags}
            />
          )}

          <div className="adminActionRow">
            <button className="adminButton" type="button" onClick={() => void save()} disabled={!item}>
              {adminCopy.enter}
            </button>
            <button className="adminGhostButton" type="button" onClick={() => void loadNext(item?.id, true)}>
              {adminCopy.skip}
            </button>
            <button className="adminGhostButton" type="button" onClick={showPrevious}>
              {adminCopy.previous}
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}

function ListingPanel({
  item,
  imageFailed,
  setImageFailed,
}: {
  item: AdminListing;
  imageFailed: boolean;
  setImageFailed: (value: boolean) => void;
}) {
  const trace = item.matcher.rule_trace;
  return (
    <div className="adminStack">
      <h2 className="adminListingTitle">{item.title}</h2>
      <div className="adminMetaGrid">
        <Meta label={adminCopy.price} value={`${item.price} ${item.currency}`} />
        <Meta label={adminCopy.status} value={item.matcher.status} />
        <Meta label={adminCopy.confidence} value={formatConfidence(item.matcher.confidence)} />
        <Meta label={adminCopy.query} value={item.candidate_query ?? "-"} />
        <Meta label={adminCopy.seller} value={item.seller_id ?? "-"} />
        <Meta label={adminCopy.condition} value={item.condition_raw ?? "-"} />
      </div>
      <div className="adminImageFrame">
        {item.image_url && !imageFailed ? (
          <img src={item.image_url} alt="" onError={() => setImageFailed(true)} />
        ) : (
          <span className="adminMuted">{adminCopy.noImage}</span>
        )}
      </div>
      <TracePanel trace={trace} />
    </div>
  );
}

function AcceptForm({
  bag,
  variantId,
  setVariantId,
  color,
  setColor,
  condition,
  setCondition,
  flags,
  setFlags,
}: {
  bag: BagOption | undefined;
  variantId: number | "";
  setVariantId: (value: number | "") => void;
  color: string;
  setColor: (value: string) => void;
  condition: ConditionBand | "";
  setCondition: (value: ConditionBand | "") => void;
  flags: Flags;
  setFlags: (value: Flags) => void;
}) {
  return (
    <div className="adminStack">
      <div className="adminFormGrid">
        <label className="adminStack">
          <span>{adminCopy.variant}</span>
          <select
            className="adminSelect"
            value={variantId}
            onChange={(event) => setVariantId(event.target.value ? Number(event.target.value) : "")}
          >
            <option value="">-</option>
            {bag?.variants.map((variant) => (
              <option key={variant.id} value={variant.id}>
                {variant.name}
              </option>
            ))}
          </select>
        </label>
        <label className="adminStack">
          <span>{adminCopy.color}</span>
          <select className="adminSelect" value={color} onChange={(event) => setColor(event.target.value)}>
            <option value="">-</option>
            {bag?.color_families.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
        <label className="adminStack">
          <span>{adminCopy.condition}</span>
          <select
            className="adminSelect"
            value={condition}
            onChange={(event) => setCondition(event.target.value as ConditionBand | "")}
          >
            <option value="">-</option>
            {conditionBands.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="adminStack">
        <span>{adminCopy.completeness}</span>
        <div className="adminCheckboxRow">
          {[
            ["strap_included", adminCopy.strap],
            ["lock_included", adminCopy.lock],
            ["key_included", adminCopy.key],
            ["dustbag_included", adminCopy.dustBag],
            ["cards_included", adminCopy.cards],
          ].map(([field, label]) => (
            <label key={field}>
              <input
                type="checkbox"
                checked={flags[field as keyof Flags] === true}
                onChange={(event) =>
                  setFlags({
                    ...flags,
                    [field]: event.target.checked ? true : null,
                  })
                }
              />
              {label}
            </label>
          ))}
        </div>
      </div>
    </div>
  );
}

function TracePanel({ trace }: { trace: AdminListing["matcher"]["rule_trace"] }) {
  const selected = trace.candidates?.[0];
  return (
    <div className="adminStack">
      <h2>{adminCopy.trace}</h2>
      <ul className="adminTraceList">
        <li>{trace.matcher_version ?? "-"}</li>
        <li>{trace.status ?? "-"}</li>
        <li>{trace.selected ?? "-"}</li>
      </ul>
      <h2>{adminCopy.ruleHits}</h2>
      <ul className="adminTraceList">
        {selected?.hits.length ? (
          selected.hits.map((hit) => (
            <li key={`${hit.rule}-${hit.term}`}>
              {hit.rule}: {hit.term} ({formatWeight(hit.weight)})
            </li>
          ))
        ) : (
          <li>{adminCopy.noRows}</li>
        )}
      </ul>
      <h2>{adminCopy.exclusions}</h2>
      <ul className="adminTraceList">
        {selected?.exclusions.length ? (
          selected.exclusions.map((hit) => (
            <li className="adminRejectChip" key={`${hit.scope}-${hit.term}`}>
              {hit.term}: {hit.reason}
            </li>
          ))
        ) : (
          <li>{adminCopy.noRows}</li>
        )}
      </ul>
    </div>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="adminMeta">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function formatConfidence(value: number | null) {
  return value === null ? "-" : `${Math.round(value * 100)}%`;
}

function formatWeight(value: number) {
  return value > 0 ? `+${value}` : String(value);
}
