"use client";

import { FormEvent, useEffect, useState } from "react";

import {
  BagOption,
  CatalogBag,
  RejectionReason,
  addCatalogAlias,
  addCatalogExclusion,
  addCatalogVariant,
  addGlobalExclusion,
  createCatalogBag,
  deleteCatalogAlias,
  deleteCatalogExclusion,
  deleteCatalogVariant,
  deleteGlobalExclusion,
  getCatalogBag,
  getCatalogBags,
  updateCatalogBag,
} from "@/lib/adminApi";
import { adminCopy, rejectionReasons } from "@/lib/adminVocabulary";

const variantKinds = ["size", "color_family", "edition"] as const;
const aliasTypes = ["alias", "misspelling", "marketplace_term"] as const;

export default function CatalogPage() {
  const [bags, setBags] = useState<BagOption[]>([]);
  const [selectedSlug, setSelectedSlug] = useState("chloe-paddington");
  const [bag, setBag] = useState<CatalogBag | null>(null);
  const [status, setStatus] = useState<string | null>(null);

  useEffect(() => {
    getCatalogBags()
      .then((response) => {
        setBags(response.items);
        if (response.items[0] && !selectedSlug) {
          setSelectedSlug(response.items[0].slug);
        }
      })
      .catch(() => setStatus("Catalog could not be loaded."));
  }, [selectedSlug]);

  useEffect(() => {
    if (!selectedSlug) {
      return;
    }
    getCatalogBag(selectedSlug)
      .then(setBag)
      .catch(() => setBag(null));
  }, [selectedSlug]);

  async function refresh() {
    const [bagResponse, listResponse] = await Promise.all([
      getCatalogBag(selectedSlug),
      getCatalogBags(),
    ]);
    setBag(bagResponse);
    setBags(listResponse.items);
  }

  return (
    <div className="adminStack">
      <header className="adminHeader">
        <h1>{adminCopy.catalog}</h1>
        <select
          className="adminSelect"
          value={selectedSlug}
          onChange={(event) => setSelectedSlug(event.target.value)}
        >
          {bags.map((item) => (
            <option key={item.slug} value={item.slug}>
              {item.brand} {item.model_name}
            </option>
          ))}
        </select>
      </header>

      {status ? <p className="adminMuted">{status}</p> : null}
      {bag?.recompute_required ? <RecomputeBanner bag={bag} /> : null}

      {bag ? (
        <div className="adminTwoColumn">
          <section className="adminStack">
            <IdentityEditor key={bag.slug} bag={bag} onSaved={refresh} />
            <CollectionEditor
              bag={bag}
              onSaved={refresh}
              setStatus={setStatus}
            />
          </section>
          <section className="adminStack">
            <CreateBagForm
              onCreated={async (slug) => {
                setSelectedSlug(slug);
                const [bagResponse, listResponse] = await Promise.all([
                  getCatalogBag(slug),
                  getCatalogBags(),
                ]);
                setBag(bagResponse);
                setBags(listResponse.items);
              }}
            />
            <GlobalExclusions bag={bag} onSaved={refresh} />
          </section>
        </div>
      ) : (
        <p className="adminMuted">{adminCopy.noRows}</p>
      )}
    </div>
  );
}

function RecomputeBanner({ bag }: { bag: CatalogBag }) {
  const since = bag.recompute_flagged_at?.slice(0, 10) ?? bag.tracking_since ?? "YYYY-MM-DD";
  return (
    <section className="adminTool adminStack adminWarning">
      <h2>{adminCopy.recomputeRequired}</h2>
      <p className="adminMuted">Matching inputs changed {since}. Run:</p>
      <code>make rematch &amp;&amp; make recompute SINCE={since} BAG={bag.slug}</code>
    </section>
  );
}

function IdentityEditor({ bag, onSaved }: { bag: CatalogBag; onSaved: () => Promise<void> }) {
  const [modelName, setModelName] = useState(bag.model_name);
  const [era, setEra] = useState(bag.era ?? "");
  const [summary, setSummary] = useState(bag.editorial_summary ?? "");
  const [history, setHistory] = useState(bag.editorial_history ?? "");
  const [conditionNotes, setConditionNotes] = useState(bag.editorial_condition_notes ?? "");
  const [queries, setQueries] = useState(bag.initial_queries.join("\n"));

  async function save(event: FormEvent) {
    event.preventDefault();
    await updateCatalogBag(bag.slug, {
      model_name: modelName,
      era: era || null,
      editorial_summary: summary || null,
      editorial_history: history || null,
      editorial_condition_notes: conditionNotes || null,
      initial_queries: queries.split("\n").map((item) => item.trim()).filter(Boolean),
    });
    await onSaved();
  }

  return (
    <form className="adminTool adminStack" onSubmit={save}>
      <h2>{adminCopy.editorial}</h2>
      <label>
        Model name
        <input className="adminInput" value={modelName} onChange={(event) => setModelName(event.target.value)} />
      </label>
      <label>
        Era
        <input className="adminInput" value={era} onChange={(event) => setEra(event.target.value)} />
      </label>
      <label>
        Summary
        <textarea className="adminInput adminTextarea" value={summary} onChange={(event) => setSummary(event.target.value)} />
      </label>
      <label>
        History capsule
        <textarea className="adminInput adminTextarea tall" value={history} onChange={(event) => setHistory(event.target.value)} />
        <span className="adminMuted">{wordCount(history)} words</span>
      </label>
      <label>
        Condition notes
        <textarea
          className="adminInput adminTextarea"
          value={conditionNotes}
          onChange={(event) => setConditionNotes(event.target.value)}
        />
      </label>
      <label>
        Initial queries
        <textarea className="adminInput adminTextarea" value={queries} onChange={(event) => setQueries(event.target.value)} />
      </label>
      <button className="adminButton" type="submit">
        {adminCopy.save}
      </button>
    </form>
  );
}

function CollectionEditor({
  bag,
  onSaved,
  setStatus,
}: {
  bag: CatalogBag;
  onSaved: () => Promise<void>;
  setStatus: (value: string | null) => void;
}) {
  const [alias, setAlias] = useState("");
  const [aliasType, setAliasType] = useState<(typeof aliasTypes)[number]>("alias");
  const [variantName, setVariantName] = useState("");
  const [variantKind, setVariantKind] = useState<(typeof variantKinds)[number]>("edition");
  const [variantSeparate, setVariantSeparate] = useState(false);
  const [term, setTerm] = useState("");
  const [reason, setReason] = useState<RejectionReason>("wrong_model");

  async function submitAlias(event: FormEvent) {
    event.preventDefault();
    await addCatalogAlias(bag.slug, { alias, type: aliasType });
    setAlias("");
    await onSaved();
  }

  async function submitVariant(event: FormEvent) {
    event.preventDefault();
    await addCatalogVariant(bag.slug, {
      name: variantName,
      kind: variantKind,
      is_separate_market: variantSeparate,
    });
    setVariantName("");
    setVariantSeparate(false);
    await onSaved();
  }

  async function submitExclusion(event: FormEvent) {
    event.preventDefault();
    await addCatalogExclusion(bag.slug, { term, reason });
    setTerm("");
    await onSaved();
  }

  async function removeVariant(id: number) {
    try {
      await deleteCatalogVariant(bag.slug, id);
      await onSaved();
    } catch {
      setStatus("Variant is referenced by market data.");
    }
  }

  return (
    <section className="adminTool adminStack">
      <h2>Matching inputs</h2>
      <form className="adminActionRow" onSubmit={submitAlias}>
        <input className="adminInput compact" value={alias} onChange={(event) => setAlias(event.target.value)} placeholder="Alias" />
        <select
          className="adminSelect compact"
          value={aliasType}
          onChange={(event) => setAliasType(event.target.value as (typeof aliasTypes)[number])}
        >
          {aliasTypes.map((type) => (
            <option key={type} value={type}>
              {type}
            </option>
          ))}
        </select>
        <button className="adminButton" type="submit">
          {adminCopy.add}
        </button>
      </form>
      <DataList
        rows={bag.aliases.map((row) => ({ id: row.id, label: `${row.alias} (${row.type})` }))}
        onDelete={(id) => deleteCatalogAlias(bag.slug, id).then(onSaved)}
      />

      <form className="adminActionRow" onSubmit={submitVariant}>
        <input
          className="adminInput compact"
          value={variantName}
          onChange={(event) => setVariantName(event.target.value)}
          placeholder="Variant"
        />
        <select
          className="adminSelect compact"
          value={variantKind}
          onChange={(event) => setVariantKind(event.target.value as (typeof variantKinds)[number])}
        >
          {variantKinds.map((kind) => (
            <option key={kind} value={kind}>
              {kind}
            </option>
          ))}
        </select>
        <label className="adminInlineCheck">
          <input checked={variantSeparate} onChange={(event) => setVariantSeparate(event.target.checked)} type="checkbox" />
          Separate
        </label>
        <button className="adminButton" type="submit">
          {adminCopy.add}
        </button>
      </form>
      <DataList
        rows={bag.variants.map((row) => ({
          id: row.id,
          label: `${row.name} (${row.kind}${row.is_separate_market ? ", separate" : ""})`,
        }))}
        onDelete={removeVariant}
      />

      <form className="adminActionRow" onSubmit={submitExclusion}>
        <input className="adminInput compact" value={term} onChange={(event) => setTerm(event.target.value)} placeholder="Exclusion" />
        <ReasonSelect value={reason} onChange={setReason} />
        <button className="adminButton" type="submit">
          {adminCopy.add}
        </button>
      </form>
      <DataList
        rows={bag.exclusions.map((row) => ({ id: row.id, label: `${row.term} (${row.reason})` }))}
        onDelete={(id) => deleteCatalogExclusion(bag.slug, id).then(onSaved)}
      />
    </section>
  );
}

function GlobalExclusions({ bag, onSaved }: { bag: CatalogBag; onSaved: () => Promise<void> }) {
  const [term, setTerm] = useState("");
  const [reason, setReason] = useState<RejectionReason>("wrong_model");

  async function submit(event: FormEvent) {
    event.preventDefault();
    await addGlobalExclusion({ term, reason });
    setTerm("");
    await onSaved();
  }

  return (
    <section className="adminTool adminStack">
      <h2>{adminCopy.globalExclusions}</h2>
      <form className="adminActionRow" onSubmit={submit}>
        <input className="adminInput compact" value={term} onChange={(event) => setTerm(event.target.value)} placeholder="Global term" />
        <ReasonSelect value={reason} onChange={setReason} />
        <button className="adminButton" type="submit">
          {adminCopy.add}
        </button>
      </form>
      <DataList
        rows={bag.global_exclusions.map((row) => ({ id: row.id, label: `${row.term} (${row.reason})` }))}
        onDelete={(id) => deleteGlobalExclusion(id).then(onSaved)}
      />
    </section>
  );
}

function CreateBagForm({ onCreated }: { onCreated: (slug: string) => Promise<void> }) {
  const [slug, setSlug] = useState("");
  const [brandSlug, setBrandSlug] = useState("");
  const [brandName, setBrandName] = useState("");
  const [modelName, setModelName] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    const response = await createCatalogBag({
      slug,
      brand: { slug: brandSlug, name: brandName },
      model_name: modelName,
      initial_queries: [],
      tracking_since: new Date().toISOString().slice(0, 10),
    });
    setSlug("");
    setBrandSlug("");
    setBrandName("");
    setModelName("");
    await onCreated(response.slug);
  }

  return (
    <form className="adminTool adminStack" onSubmit={submit}>
      <h2>{adminCopy.createBag}</h2>
      <input className="adminInput" value={slug} onChange={(event) => setSlug(event.target.value)} placeholder="bag-slug" />
      <input className="adminInput" value={brandSlug} onChange={(event) => setBrandSlug(event.target.value)} placeholder="brand-slug" />
      <input className="adminInput" value={brandName} onChange={(event) => setBrandName(event.target.value)} placeholder="Brand name" />
      <input className="adminInput" value={modelName} onChange={(event) => setModelName(event.target.value)} placeholder="Model name" />
      <button className="adminButton" type="submit">
        {adminCopy.createBag}
      </button>
    </form>
  );
}

function ReasonSelect({
  value,
  onChange,
}: {
  value: RejectionReason;
  onChange: (value: RejectionReason) => void;
}) {
  return (
    <select className="adminSelect compact" value={value} onChange={(event) => onChange(event.target.value as RejectionReason)}>
      {rejectionReasons.map((item) => (
        <option key={item} value={item}>
          {item}
        </option>
      ))}
    </select>
  );
}

function DataList({
  rows,
  onDelete,
}: {
  rows: Array<{ id: number; label: string }>;
  onDelete: (id: number) => Promise<void>;
}) {
  if (rows.length === 0) {
    return <p className="adminMuted">{adminCopy.noRows}</p>;
  }
  return (
    <ul className="adminTraceList">
      {rows.map((row) => (
        <li key={row.id}>
          {row.label}
          <button className="adminGhostButton small" type="button" onClick={() => onDelete(row.id)}>
            {adminCopy.delete}
          </button>
        </li>
      ))}
    </ul>
  );
}

function wordCount(value: string) {
  return value.trim().split(/\s+/).filter(Boolean).length;
}
