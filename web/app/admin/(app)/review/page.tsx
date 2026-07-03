/* eslint-disable @next/next/no-img-element */
"use client";

import { useEffect, useMemo, useState } from "react";

import {
  AdminListing,
  BagOption,
  RejectionReason,
  getCatalogBags,
  getReviewQueue,
  submitReviewDecision,
} from "@/lib/adminApi";
import { adminCopy, rejectionReasons } from "@/lib/adminVocabulary";

export default function ReviewPage() {
  const [bags, setBags] = useState<BagOption[]>([]);
  const [bagSlug, setBagSlug] = useState("");
  const [items, setItems] = useState<AdminListing[]>([]);
  const [activeIndex, setActiveIndex] = useState(0);
  const [reason, setReason] = useState<RejectionReason>(rejectionReasons[0]);
  const [reassignBagId, setReassignBagId] = useState<number | "">("");
  const [variantId, setVariantId] = useState<number | "">("");
  const [imageFailed, setImageFailed] = useState(false);

  useEffect(() => {
    getCatalogBags().then((response) => setBags(response.items));
  }, []);

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bagSlug]);

  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (target?.tagName === "INPUT" || target?.tagName === "SELECT") {
        return;
      }
      if (event.key === "j") {
        setActiveIndex((index) => Math.min(index + 1, items.length - 1));
      } else if (event.key === "k") {
        setActiveIndex((index) => Math.max(index - 1, 0));
      } else if (event.key === "a") {
        void decide("approve");
      } else if (event.key === "r") {
        void decide("reject");
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const active = items[activeIndex] ?? null;
  const reassignBag = useMemo(
    () => bags.find((bag) => bag.id === reassignBagId),
    [bags, reassignBagId],
  );

  async function refresh() {
    const response = await getReviewQueue(bagSlug || undefined);
    setItems(response.items);
    setActiveIndex(0);
    setImageFailed(false);
  }

  async function decide(action: "approve" | "reassign" | "reject") {
    if (!active) {
      return;
    }
    await submitReviewDecision(active.id, {
      action,
      bag_model_id:
        action === "reassign"
          ? reassignBagId || null
          : active.matcher.matched_bag_model_id ?? active.candidate_bag_model_id,
      variant_id: variantId || null,
      rejection_reason: action === "reject" ? reason : null,
    });
    await refresh();
  }

  return (
    <div className="adminStack">
      <header className="adminHeader">
        <h1>{adminCopy.review}</h1>
        <select className="adminSelect" value={bagSlug} onChange={(event) => setBagSlug(event.target.value)}>
          <option value="">All bags</option>
          {bags.map((bag) => (
            <option key={bag.slug} value={bag.slug}>
              {bag.brand} {bag.model_name}
            </option>
          ))}
        </select>
      </header>

      <section className="adminTwoColumn">
        <div className="adminTool">
          <table className="adminTable">
            <thead>
              <tr>
                <th>{adminCopy.item}</th>
                <th>{adminCopy.price}</th>
                <th>{adminCopy.status}</th>
              </tr>
            </thead>
            <tbody>
              {items.length ? (
                items.map((row, index) => (
                  <tr
                    className="adminQueueRow"
                    aria-selected={index === activeIndex}
                    key={row.id}
                    onClick={() => {
                      setActiveIndex(index);
                      setImageFailed(false);
                    }}
                  >
                    <td>{row.title}</td>
                    <td>
                      {row.price} {row.currency}
                    </td>
                    <td>{row.matcher.status}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={3}>{adminCopy.noRows}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="adminTool adminStack">
          {active ? (
            <>
              <h2 className="adminListingTitle">{active.title}</h2>
              <div className="adminMetaGrid">
                <Meta label={adminCopy.confidence} value={formatConfidence(active.matcher.confidence)} />
                <Meta label={adminCopy.query} value={active.candidate_query ?? "-"} />
              </div>
              <div className="adminImageFrame">
                {active.image_url && !imageFailed ? (
                  <img src={active.image_url} alt="" onError={() => setImageFailed(true)} />
                ) : (
                  <span className="adminMuted">{adminCopy.noImage}</span>
                )}
              </div>
              <Trace trace={active.matcher.rule_trace} />

              <div className="adminFormGrid">
                <label className="adminStack">
                  <span>{adminCopy.reassign}</span>
                  <select
                    className="adminSelect"
                    value={reassignBagId}
                    onChange={(event) => setReassignBagId(event.target.value ? Number(event.target.value) : "")}
                  >
                    <option value="">-</option>
                    {bags.map((bag) => (
                      <option key={bag.id} value={bag.id}>
                        {bag.brand} {bag.model_name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="adminStack">
                  <span>{adminCopy.variant}</span>
                  <select
                    className="adminSelect"
                    value={variantId}
                    onChange={(event) => setVariantId(event.target.value ? Number(event.target.value) : "")}
                  >
                    <option value="">-</option>
                    {reassignBag?.variants.map((variant) => (
                      <option key={variant.id} value={variant.id}>
                        {variant.name}
                      </option>
                    ))}
                  </select>
                </label>
                <label className="adminStack">
                  <span>{adminCopy.reason}</span>
                  <select
                    className="adminSelect"
                    value={reason}
                    onChange={(event) => setReason(event.target.value as RejectionReason)}
                  >
                    {rejectionReasons.map((value) => (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <div className="adminActionRow">
                <button className="adminButton" type="button" onClick={() => void decide("approve")}>
                  {adminCopy.approve}
                </button>
                <button className="adminGhostButton" type="button" onClick={() => void decide("reassign")}>
                  {adminCopy.reassign}
                </button>
                <button className="adminDangerButton" type="button" onClick={() => void decide("reject")}>
                  {adminCopy.reject}
                </button>
              </div>
            </>
          ) : (
            <p className="adminMuted">{adminCopy.noRows}</p>
          )}
        </div>
      </section>
    </div>
  );
}

function Trace({ trace }: { trace: AdminListing["matcher"]["rule_trace"] }) {
  const selected = trace.candidates?.[0];
  return (
    <div className="adminStack">
      <h2>{adminCopy.trace}</h2>
      <ul className="adminTraceList">
        {selected?.hits.map((hit) => (
          <li key={`${hit.rule}-${hit.term}`}>
            {hit.rule}: {hit.term}
          </li>
        ))}
        {selected?.exclusions.map((hit) => (
          <li className="adminRejectChip" key={`${hit.scope}-${hit.term}`}>
            {hit.term}: {hit.reason}
          </li>
        ))}
        {!selected ? <li>{adminCopy.noRows}</li> : null}
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
