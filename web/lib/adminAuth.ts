import { createHmac, timingSafeEqual } from "node:crypto";

export const adminCookieName = "admin_session";
const sessionMessage = "covetability-admin-v1";

export function sessionToken(secret = readAdminSecret()): string {
  return createHmac("sha256", secret).update(sessionMessage).digest("hex");
}

export function verifySessionToken(token: string | undefined, secret = readAdminSecret()): boolean {
  if (!token) {
    return false;
  }
  return safeEqual(token, sessionToken(secret));
}

export function verifySecret(candidate: string | undefined, secret = readAdminSecret()): boolean {
  if (!candidate) {
    return false;
  }
  return safeEqual(candidate, secret);
}

export function readAdminSecret(): string {
  return process.env.ADMIN_SECRET ?? "change-me";
}

export function safeEqual(left: string, right: string): boolean {
  const leftBuffer = Buffer.from(left);
  const rightBuffer = Buffer.from(right);
  if (leftBuffer.length !== rightBuffer.length) {
    return false;
  }
  return timingSafeEqual(leftBuffer, rightBuffer);
}
