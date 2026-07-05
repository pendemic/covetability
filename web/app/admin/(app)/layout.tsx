import { cookies } from "next/headers";
import Link from "next/link";
import { redirect } from "next/navigation";
import { ReactNode } from "react";

import { adminCookieName, verifySessionToken } from "@/lib/adminAuth";
import { adminCopy } from "@/lib/adminVocabulary";
import "../admin.css";
import { LogoutButton } from "./LogoutButton";

export default async function AdminLayout({ children }: { children: ReactNode }) {
  const cookieStore = await cookies();
  const token = cookieStore.get(adminCookieName)?.value;
  if (!verifySessionToken(token)) {
    redirect("/admin/login");
  }

  return (
    <div className="adminShell">
      <header className="adminTopbar">
        <div className="adminBrand">
          <strong>Covetability</strong>
          <span>Operator tools</span>
        </div>
        <nav className="adminNav" aria-label="Admin">
          <Link href="/admin">{adminCopy.dashboard}</Link>
          <Link href="/admin/labeling">{adminCopy.labeling}</Link>
          <Link href="/admin/review">{adminCopy.review}</Link>
          <Link href="/admin/quality">{adminCopy.quality}</Link>
          <Link href="/admin/score">{adminCopy.score}</Link>
          <Link href="/admin/catalog">{adminCopy.catalog}</Link>
          <LogoutButton />
        </nav>
      </header>
      <main className="adminMain">{children}</main>
    </div>
  );
}
