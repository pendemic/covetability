"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { openAdminSession } from "@/lib/adminApi";
import { adminCopy } from "@/lib/adminVocabulary";
import "../admin.css";

export default function AdminLoginPage() {
  const router = useRouter();
  const [secret, setSecret] = useState("");
  const [error, setError] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const ok = await openAdminSession(secret);
    if (!ok) {
      setError(true);
      return;
    }
    router.replace("/admin");
  }

  return (
    <main className="adminLoginPage">
      <form className="adminLoginBox" onSubmit={submit}>
        <h1>{adminCopy.adminAccess}</h1>
        <label className="adminStack">
          <span>{adminCopy.secret}</span>
          <input
            className="adminInput"
            type="password"
            value={secret}
            onChange={(event) => {
              setSecret(event.target.value);
              setError(false);
            }}
            autoComplete="current-password"
          />
        </label>
        {error ? <p className="adminMuted">Secret rejected.</p> : null}
        <button className="adminButton" type="submit">
          {adminCopy.enter}
        </button>
      </form>
    </main>
  );
}
