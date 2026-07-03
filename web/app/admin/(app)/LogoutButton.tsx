"use client";

import { useRouter } from "next/navigation";

import { closeAdminSession } from "@/lib/adminApi";
import { adminCopy } from "@/lib/adminVocabulary";

export function LogoutButton() {
  const router = useRouter();

  async function logout() {
    await closeAdminSession();
    router.replace("/admin/login");
  }

  return (
    <button className="adminGhostButton" type="button" onClick={logout}>
      {adminCopy.signOut}
    </button>
  );
}
