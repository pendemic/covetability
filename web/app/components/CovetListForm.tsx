"use client";

import { useState } from "react";

import { metricDisplayVocabulary } from "@/lib/vocabulary";

export function CovetListForm({ slug }: { slug: string }) {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setStatus("saving");
    const response = await fetch(`/api/watch/${slug}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ email }),
    });
    setStatus(response.ok ? "saved" : "error");
  }

  return (
    <form className="covetForm" onSubmit={onSubmit}>
      <div>
        <span className="kicker">{metricDisplayVocabulary.covetList}</span>
        <p className="muted">Get a weekly preview once public score updates are available.</p>
      </div>
      <input
        aria-label="Email"
        onChange={(event) => setEmail(event.target.value)}
        placeholder="you@example.com"
        required
        type="email"
        value={email}
      />
      <button className="btn" disabled={status === "saving"} type="submit">
        {status === "saving" ? "Saving" : `Add to ${metricDisplayVocabulary.covetList}`}
      </button>
      {status === "saved" ? <span className="muted">Added.</span> : null}
      {status === "error" ? <span className="muted">Could not add that email.</span> : null}
    </form>
  );
}
