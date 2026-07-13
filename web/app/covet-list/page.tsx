"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { SiteFooter, SiteHeader, Sparkline } from "@/app/components/MarketComponents";
import type { CovetModel } from "@/app/api/covet/route";
import { swatchColor } from "@/lib/swatch";
import { metricDisplayVocabulary } from "@/lib/vocabulary";

const STORE_KEY = "covetList.v1";

type Store = { slugs: string[]; targets: Record<string, number> };

function loadStore(): Store {
  if (typeof window === "undefined") return { slugs: [], targets: {} };
  try {
    const raw = window.localStorage.getItem(STORE_KEY);
    if (!raw) return { slugs: [], targets: {} };
    const parsed = JSON.parse(raw) as Store;
    return { slugs: parsed.slugs ?? [], targets: parsed.targets ?? {} };
  } catch {
    return { slugs: [], targets: {} };
  }
}

type Alert = { tone: "down" | "up" | "steady"; title: string; body: string };

function buildAlerts(model: CovetModel, target: number | undefined): Alert[] {
  const out: Alert[] = [];
  const name = `${model.brand} ${model.model_name}`.trim() || model.slug;
  if (target && model.typical != null) {
    if (model.typical < target) {
      out.push({
        tone: "down",
        title: `${name} · under target`,
        body: `Typical asking $${Math.round(model.typical).toLocaleString()} is below your $${target.toLocaleString()} target.`,
      });
    } else if (model.typical > target * 1.05) {
      out.push({
        tone: "up",
        title: `${name} · above target`,
        body: `Typical asking $${Math.round(model.typical).toLocaleString()} is above your $${target.toLocaleString()} target.`,
      });
    } else {
      out.push({
        tone: "steady",
        title: `${name} · near target`,
        body: `Typical asking is holding near your $${target.toLocaleString()} target.`,
      });
    }
  }
  if (model.classification) {
    out.push({
      tone: "steady",
      title: `${name} · ${metricDisplayVocabulary.score} ${model.classification}`,
      body: `Model-level ${metricDisplayVocabulary.score} is ${model.classification}.`,
    });
  }
  return out;
}

export default function CovetListPage() {
  const [store, setStore] = useState<Store>({ slugs: [], targets: {} });
  const [all, setAll] = useState<CovetModel[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [email, setEmail] = useState("");
  const [emailState, setEmailState] = useState<"idle" | "saving" | "saved" | "error">("idle");

  useEffect(() => {
    setStore(loadStore());
    fetch("/api/covet?all=1")
      .then((res) => res.json())
      .then((data: { models: CovetModel[] }) => setAll(data.models ?? []))
      .catch(() => setAll([]))
      .finally(() => setLoaded(true));
  }, []);

  function persist(next: Store) {
    setStore(next);
    if (typeof window !== "undefined") {
      window.localStorage.setItem(STORE_KEY, JSON.stringify(next));
    }
  }

  function toggle(slug: string) {
    const has = store.slugs.includes(slug);
    persist({
      slugs: has ? store.slugs.filter((s) => s !== slug) : [...store.slugs, slug],
      targets: store.targets,
    });
  }

  function setTarget(slug: string, value: number | null) {
    const targets = { ...store.targets };
    if (value == null || Number.isNaN(value)) {
      delete targets[slug];
    } else {
      targets[slug] = value;
    }
    persist({ slugs: store.slugs, targets });
  }

  async function sendEmail(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!email || store.slugs.length === 0) return;
    setEmailState("saving");
    try {
      const results = await Promise.all(
        store.slugs.map((slug) =>
          fetch(`/api/watch/${slug}`, {
            method: "POST",
            headers: { "content-type": "application/json" },
            body: JSON.stringify({ email }),
          }),
        ),
      );
      setEmailState(results.every((r) => r.ok) ? "saved" : "error");
    } catch {
      setEmailState("error");
    }
  }

  const bySlug = useMemo(() => new Map(all.map((m) => [m.slug, m])), [all]);
  const saved = store.slugs.map((slug) => bySlug.get(slug)).filter((m): m is CovetModel => !!m);
  const available = all.filter((m) => !store.slugs.includes(m.slug));
  const alerts = saved.flatMap((m) => buildAlerts(m, store.targets[m.slug]));

  return (
    <>
      <SiteHeader />
      <main className="page-wrap">
        <section className="brandHero covetHero">
          <div>
            <span className="kicker-lg">Your saved models</span>
            <h1>{metricDisplayVocabulary.covetList}</h1>
          </div>
          {alerts.length ? <span className="alertPill">{alerts.length} new alerts</span> : null}
        </section>

        <div className="covetBody">
          <section className="contentSection covetMain">
            {!loaded ? (
              <p className="muted">Loading your Covet List…</p>
            ) : saved.length === 0 ? (
              <p className="muted">
                Your Covet List is empty. Add a model below to track its typical asking range and
                {" "}
                {metricDisplayVocabulary.score}.
              </p>
            ) : (
              saved.map((model) => {
                const target = store.targets[model.slug];
                const name = `${model.brand} ${model.model_name}`.trim() || model.slug;
                const note = buildAlerts(model, target)[0];
                return (
                  <div className="covetCard" key={model.slug}>
                    <div className="covetCardRow">
                      <span
                        className="modelSwatch"
                        style={{ background: swatchColor(name) }}
                        aria-hidden="true"
                      />
                      <div className="covetCardMain">
                        <span className="kicker">
                          {model.brand}
                          {model.era ? ` · ${model.era}` : ""} · model level
                        </span>
                        <Link className="covetCardName" href={`/bags/${model.slug}`}>
                          {model.model_name || model.slug}
                        </Link>
                        <span className="kicker covetClass">
                          {metricDisplayVocabulary.score}{" "}
                          {model.classification ?? "not yet scored"} · model-level
                        </span>
                      </div>
                      <div className="covetPrices">
                        <span className="kicker">Typical / Target</span>
                        <div className="covetPriceVals">
                          <strong>
                            {model.typical != null ? `$${Math.round(model.typical).toLocaleString()}` : "—"}
                          </strong>
                          <span className="covetTargetWrap">
                            <span className="muted">/ $</span>
                            <input
                              aria-label={`Target price for ${name}`}
                              className="covetTargetInput"
                              inputMode="numeric"
                              onChange={(e) =>
                                setTarget(model.slug, e.target.value ? Number(e.target.value) : null)
                              }
                              placeholder="target"
                              value={target ?? ""}
                            />
                          </span>
                        </div>
                        {model.sparkline.length ? (
                          <div className="covetSpark">
                            <Sparkline values={model.sparkline} />
                          </div>
                        ) : null}
                      </div>
                      <button
                        aria-label={`Remove ${name}`}
                        className="covetRemove"
                        onClick={() => toggle(model.slug)}
                        type="button"
                      >
                        ×
                      </button>
                    </div>
                    {note ? <div className={`covetNote tone-${note.tone}`}>{note.body}</div> : null}
                  </div>
                );
              })
            )}

            {available.length ? (
              <div className="covetAdd">
                <span className="kicker">+ Add a model to your {metricDisplayVocabulary.covetList}</span>
                <div className="covetAddChips">
                  {available.map((model) => (
                    <button
                      className="compareChip"
                      key={model.slug}
                      onClick={() => toggle(model.slug)}
                      type="button"
                    >
                      {model.brand} {model.model_name || model.slug}
                    </button>
                  ))}
                </div>
              </div>
            ) : null}
          </section>

          <aside className="contentSection covetSide">
            <div className="sectionHeader">
              <h2>Alerts</h2>
              <span className="muted">latest aggregate day</span>
            </div>
            {alerts.length ? (
              <div className="alertList">
                {alerts.map((alert, index) => (
                  <div className={`alertRow tone-${alert.tone}`} key={`${alert.title}-${index}`}>
                    <span className="alertDot" aria-hidden="true" />
                    <div>
                      <strong>{alert.title}</strong>
                      <p className="muted">{alert.body}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="muted">
                No alerts yet — add a model and set a target to see status against it.
              </p>
            )}

            <div className="alertTypes">
              <span className="kicker">Alert types</span>
              <p className="muted">
                Band changes on the model-level {metricDisplayVocabulary.score}, typical-asking-range
                crossings of your threshold, and confidence upgrades. No price predictions are sent.
              </p>
            </div>

            {saved.length ? (
              <form className="covetEmail" onSubmit={sendEmail}>
                <span className="kicker">Get these alerts by email</span>
                <input
                  aria-label="Email"
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  type="email"
                  value={email}
                />
                <button className="btn" disabled={emailState === "saving"} type="submit">
                  {emailState === "saving" ? "Saving" : "Email me alerts"}
                </button>
                {emailState === "saved" ? <span className="muted">Subscribed.</span> : null}
                {emailState === "error" ? <span className="muted">Could not subscribe.</span> : null}
              </form>
            ) : null}
          </aside>
        </div>
      </main>
      <SiteFooter />
    </>
  );
}
