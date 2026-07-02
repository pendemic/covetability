import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: "Covetability",
  description: "Active-market intelligence for vintage designer handbags.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
