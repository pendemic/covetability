"use client";

import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import {
  BagOption,
  ConditionBand,
  CulturalNote,
  EvidencePayload,
  EvidenceRecord,
  addCulturalNote,
  addEvidenceRecord,
  deleteCulturalNote,
  deleteEvidenceRecord,
  getCatalogBags,
  getCulturalNotes,
  getEvidenceRecords,
} from "@/lib/adminApi";
import { adminCopy, conditionBands } from "@/lib/adminVocabulary";

const sourceTypes = ["manual", "user_submitted", "auction_record"] as const;

export default function EvidencePage() {
  const [bags, setBags] = useState<BagOption[]>([]);
  const [selectedSlug, setSelectedSlug] = useState("chloe-paddington");
  const [records, setRecords] = useState<EvidenceRecord[]>([]);
  const [notes, setNotes] = useState<CulturalNote[]>([]);
  const [status, setStatus] = useState<string | null>(null);
  const selectedBag = useMemo(
    () => bags.find((bag) => bag.slug === selectedSlug) ?? null,
    [bags, selectedSlug],
  );

  const refresh = useCallback(
    async (slug = selectedSlug) => {
      const [recordResponse, noteResponse] = await Promise.all([
        getEvidenceRecords(slug),
        getCulturalNotes(slug),
      ]);
      setRecords(recordResponse.items);
      setNotes(noteResponse.items);
    },
    [selectedSlug],
  );

  useEffect(() => {
    getCatalogBags()
      .then((response) => {
        setBags(response.items);
        if (!selectedSlug && response.items[0]) {
          setSelectedSlug(response.items[0].slug);
        }
      })
      .catch(() => setStatus("Evidence catalog could not be loaded."));
  }, [selectedSlug]);

  useEffect(() => {
    if (!selectedSlug) {
      return;
    }
    let cancelled = false;
    Promise.all([getEvidenceRecords(selectedSlug), getCulturalNotes(selectedSlug)])
      .then(([recordResponse, noteResponse]) => {
        if (cancelled) {
          return;
        }
        setRecords(recordResponse.items);
        setNotes(noteResponse.items);
      })
      .catch(() => {
        if (!cancelled) {
          setStatus("Evidence rows could not be loaded.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [selectedSlug]);

  return (
    <div className="adminStack">
      <header className="adminHeader">
        <h1>{adminCopy.evidence}</h1>
        <select
          className="adminSelect"
          value={selectedSlug}
          onChange={(event) => setSelectedSlug(event.target.value)}
        >
          {bags.map((bag) => (
            <option key={bag.slug} value={bag.slug}>
              {bag.brand} {bag.model_name}
            </option>
          ))}
        </select>
      </header>

      {status ? <p className="adminMuted">{status}</p> : null}

      {selectedBag ? (
        <div className="adminTwoColumn">
          <section className="adminStack">
            <EvidenceForm bag={selectedBag} onSaved={() => refresh()} />
            <RecordsTable records={records} onDelete={(id) => deleteEvidenceRecord(id).then(() => refresh())} />
          </section>
          <section className="adminStack">
            <ContextForm slug={selectedSlug} onSaved={() => refresh()} />
            <NotesList notes={notes} onDelete={(id) => deleteCulturalNote(id).then(() => refresh())} />
          </section>
        </div>
      ) : (
        <p className="adminMuted">{adminCopy.noRows}</p>
      )}
    </div>
  );
}

function EvidenceForm({ bag, onSaved }: { bag: BagOption; onSaved: () => Promise<void> }) {
  const [sourceType, setSourceType] = useState<(typeof sourceTypes)[number]>("manual");
  const [source, setSource] = useState("");
  const [observedAt, setObservedAt] = useState(new Date().toISOString().slice(0, 10));
  const [enteredBy, setEnteredBy] = useState("");
  const [url, setUrl] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [price, setPrice] = useState("");
  const [currency, setCurrency] = useState("USD");
  const [shippingIncluded, setShippingIncluded] = useState(false);
  const [conditionBand, setConditionBand] = useState<ConditionBand>("good");
  const [conditionRaw, setConditionRaw] = useState("");
  const [notes, setNotes] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    const payload: EvidencePayload = {
      bag_model_id: bag.id,
      source,
      source_type: sourceType,
      observed_at: `${observedAt}T12:00:00Z`,
      entered_by: enteredBy,
      listing_url: url,
      confirmed,
      price_type: sourceType === "auction_record" ? "realized" : "asking",
      price,
      currency,
      shipping_included: shippingIncluded,
      condition_raw: conditionRaw || null,
      condition_band: conditionBand,
      condition_confidence: "high",
      notes: notes || null,
    };
    await addEvidenceRecord(payload);
    setSource("");
    setUrl("");
    setPrice("");
    setConditionRaw("");
    setNotes("");
    await onSaved();
  }

  return (
    <form className="adminTool adminStack" onSubmit={submit}>
      <h2>{adminCopy.manualComp}</h2>
      <div className="adminFormGrid">
        <label>
          Source type
          <select
            className="adminSelect"
            value={sourceType}
            onChange={(event) => setSourceType(event.target.value as (typeof sourceTypes)[number])}
          >
            {sourceTypes.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </label>
        <label>
          Source
          <input className="adminInput" value={source} onChange={(event) => setSource(event.target.value)} />
        </label>
        <label>
          Observed date
          <input className="adminInput" type="date" value={observedAt} onChange={(event) => setObservedAt(event.target.value)} />
        </label>
        <label>
          Entered by
          <input className="adminInput" value={enteredBy} onChange={(event) => setEnteredBy(event.target.value)} />
        </label>
        <label>
          URL
          <input className="adminInput" value={url} onChange={(event) => setUrl(event.target.value)} />
        </label>
        <label>
          Price
          <input className="adminInput" value={price} onChange={(event) => setPrice(event.target.value)} />
        </label>
        <label>
          Currency
          <input className="adminInput" value={currency} onChange={(event) => setCurrency(event.target.value.toUpperCase())} />
        </label>
        <label>
          Condition
          <select
            className="adminSelect"
            value={conditionBand}
            onChange={(event) => setConditionBand(event.target.value as ConditionBand)}
          >
            {conditionBands.map((band) => (
              <option key={band} value={band}>
                {band}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label>
        Raw condition
        <input className="adminInput" value={conditionRaw} onChange={(event) => setConditionRaw(event.target.value)} />
      </label>
      <label>
        Notes
        <textarea className="adminInput adminTextarea" value={notes} onChange={(event) => setNotes(event.target.value)} />
      </label>
      <div className="adminActionRow">
        <label className="adminInlineCheck">
          <input checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} type="checkbox" />
          {adminCopy.confirmedClose}
        </label>
        <label className="adminInlineCheck">
          <input
            checked={shippingIncluded}
            onChange={(event) => setShippingIncluded(event.target.checked)}
            type="checkbox"
          />
          Shipping included
        </label>
      </div>
      <button className="adminButton" type="submit">
        {adminCopy.add}
      </button>
    </form>
  );
}

function ContextForm({ slug, onSaved }: { slug: string; onSaved: () => Promise<void> }) {
  const [noteDate, setNoteDate] = useState(new Date().toISOString().slice(0, 10));
  const [body, setBody] = useState("");
  const [createdBy, setCreatedBy] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    await addCulturalNote(slug, {
      note_date: noteDate,
      body,
      created_by: createdBy || null,
    });
    setBody("");
    await onSaved();
  }

  return (
    <form className="adminTool adminStack" onSubmit={submit}>
      <h2>{adminCopy.culturalContext}</h2>
      <input className="adminInput" type="date" value={noteDate} onChange={(event) => setNoteDate(event.target.value)} />
      <input className="adminInput" value={createdBy} onChange={(event) => setCreatedBy(event.target.value)} placeholder="Created by" />
      <textarea className="adminInput adminTextarea tall" value={body} onChange={(event) => setBody(event.target.value)} />
      <button className="adminButton" type="submit">
        {adminCopy.add}
      </button>
    </form>
  );
}

function RecordsTable({
  records,
  onDelete,
}: {
  records: EvidenceRecord[];
  onDelete: (id: number) => Promise<void>;
}) {
  if (records.length === 0) {
    return <p className="adminMuted">{adminCopy.noRows}</p>;
  }
  return (
    <section className="adminTool adminStack">
      <h2>Rows</h2>
      <table className="adminTable">
        <thead>
          <tr>
            <th>Source</th>
            <th>Type</th>
            <th>Condition</th>
            <th>Price</th>
            <th>Action</th>
          </tr>
        </thead>
        <tbody>
          {records.map((record) => (
            <tr key={record.id}>
              <td>{record.source}</td>
              <td>{record.source_type}</td>
              <td>{record.condition_band}</td>
              <td>
                {record.price} {record.currency}
              </td>
              <td>
                <button className="adminGhostButton small" type="button" onClick={() => onDelete(record.id)}>
                  {adminCopy.delete}
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function NotesList({
  notes,
  onDelete,
}: {
  notes: CulturalNote[];
  onDelete: (id: number) => Promise<void>;
}) {
  if (notes.length === 0) {
    return <p className="adminMuted">{adminCopy.noRows}</p>;
  }
  return (
    <section className="adminTool adminStack">
      <h2>Notes</h2>
      <ul className="adminTraceList">
        {notes.map((note) => (
          <li key={note.id}>
            {note.note_date}: {note.body}
            <button className="adminGhostButton small" type="button" onClick={() => onDelete(note.id)}>
              {adminCopy.delete}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
