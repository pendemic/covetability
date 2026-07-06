import type { Metadata } from "next";
import { Cormorant_Garamond, Hanken_Grotesk, IBM_Plex_Mono } from "next/font/google";
import Script from "next/script";

import "./globals.css";

const serif = Cormorant_Garamond({
  subsets: ["latin"],
  variable: "--font-serif",
  weight: ["500", "600"],
});

const sans = Hanken_Grotesk({
  subsets: ["latin"],
  variable: "--font-sans",
});

const mono = IBM_Plex_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "500"],
});

export const metadata: Metadata = {
  title: "Covetability",
  description: "Active-market intelligence for vintage designer handbags.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const analyticsDomain = process.env.NEXT_PUBLIC_ANALYTICS_DOMAIN;
  const analyticsSrc = process.env.NEXT_PUBLIC_ANALYTICS_SRC ?? "https://plausible.io/js/script.js";
  return (
    <html lang="en" className={`${serif.variable} ${sans.variable} ${mono.variable}`}>
      <body>
        {children}
        {analyticsDomain ? (
          <Script
            data-domain={analyticsDomain}
            defer
            src={analyticsSrc}
            strategy="afterInteractive"
          />
        ) : null}
      </body>
    </html>
  );
}
